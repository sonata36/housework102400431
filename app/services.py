"""Business services for papers, keywords, imports, and analytics."""

import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone

from .db import get_db
from .sources import get_cvf_adapter, get_source_adapter

STOPWORDS = {"a", "an", "and", "for", "in", "of", "on", "the", "with", "using", "based"}
ALIASES = {"cnn": "convolutional neural network", "cnns": "convolutional neural network", "vision transformer": "transformer"}
ALLOWED_CONFERENCES = {"CVPR", "ICCV", "ECCV"}

DEMO_PAPERS = [
    ("Efficient Transformer for Visual Recognition", "CVPR", 2020, "transformer, attention, recognition"),
    ("Robust Representation Learning for Images", "CVPR", 2021, "representation learning, self-supervised, recognition"),
    ("Vision Transformer for Dense Prediction", "CVPR", 2022, "transformer, segmentation, dense prediction"),
    ("Open Vocabulary Detection with Language Cues", "CVPR", 2023, "object detection, vision-language, transformer"),
    ("Multi-Modal Video Understanding", "CVPR", 2024, "video understanding, vision-language, transformer"),
    ("Self-Supervised Learning for Visual Features", "ICCV", 2020, "self-supervised, representation learning, contrastive learning"),
    ("Attention-Based Object Detection", "ICCV", 2021, "attention, object detection, transformer"),
    ("Neural Rendering for 3D Scenes", "ICCV", 2022, "neural rendering, 3d vision, representation learning"),
    ("Promptable Segmentation Models", "ICCV", 2023, "segmentation, foundation model, prompt learning"),
    ("Learning General Visual Embeddings", "ICCV", 2024, "representation learning, foundation model, vision-language"),
    ("Geometric Vision with Neural Fields", "ECCV", 2020, "3d vision, neural rendering, geometric vision"),
    ("Contrastive Learning for Fine-Grained Recognition", "ECCV", 2021, "contrastive learning, recognition, representation learning"),
    ("Transformer-Based Image Generation", "ECCV", 2022, "transformer, image generation, generative model"),
    ("Weakly Supervised Semantic Segmentation", "ECCV", 2023, "segmentation, weakly supervised, recognition"),
    ("Large Vision Models for Video", "ECCV", 2024, "video understanding, foundation model, transformer"),
]


def normalize_title(title):
    """Normalize whitespace and case for deterministic de-duplication."""
    return re.sub(r"\s+", " ", (title or "").strip()).casefold()


def normalize_keyword(keyword):
    """Normalize a keyword while retaining a display value."""
    value = re.sub(r"[^\w\s-]", "", (keyword or "").strip().casefold())
    value = re.sub(r"\s+", " ", value)
    return ALIASES.get(value, value)


def split_keywords(value):
    """Parse comma, semicolon, or newline separated keywords."""
    return [item.strip() for item in re.split(r"[,;\n]", value or "") if item.strip()]


def extract_keywords(title, abstract=""):
    """Provide a transparent lightweight fallback extractor."""
    words = re.findall(r"[A-Za-z][A-Za-z-]{2,}", f"{title} {abstract}".lower())
    counts = Counter(word for word in words if word not in STOPWORDS)
    return [word for word, _count in counts.most_common(8)]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def find_papers(args):
    """Search papers with exact-title or multi-field fuzzy semantics."""
    db = get_db()
    mode, q = args.get("mode", "fuzzy"), (args.get("q") or "").strip()
    clauses, params = [], []
    if q:
        if mode == "exact":
            clauses.append("p.normalized_title = ?")
            params.append(normalize_title(q))
        else:
            clauses.append("(p.title LIKE ? OR p.paper_number LIKE ? OR p.conference LIKE ? OR EXISTS (SELECT 1 FROM paper_keywords pk JOIN keywords k ON k.id=pk.keyword_id WHERE pk.paper_id=p.id AND k.display_name LIKE ?))")
            like = f"%{q}%"
            params.extend([like, like, like, like])
    if args.get("conference"):
        clauses.append("p.conference = ?")
        params.append(args["conference"].strip().upper())
    if args.get("year"):
        try:
            year = int(args["year"])
        except (TypeError, ValueError):
            year = None
        if year is not None:
            clauses.append("p.year = ?")
            params.append(year)
    else:
        for field, operator in (("year_from", ">="), ("year_to", "<=")):
            if args.get(field):
                try:
                    year = int(args[field])
                except (TypeError, ValueError):
                    continue
                clauses.append(f"p.year {operator} ?")
                params.append(year)
    if args.get("keyword"):
        clauses.append("EXISTS (SELECT 1 FROM paper_keywords pk JOIN keywords k ON k.id=pk.keyword_id WHERE pk.paper_id=p.id AND k.normalized = ?)")
        params.append(normalize_keyword(args["keyword"]))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    try:
        page = max(int(args.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    per_page = 10
    count = db.execute(f"SELECT COUNT(*) FROM papers p {where}", params).fetchone()[0]
    rows = db.execute(f"SELECT p.*, GROUP_CONCAT(DISTINCT k.display_name) keywords FROM papers p LEFT JOIN paper_keywords pk ON pk.paper_id=p.id LEFT JOIN keywords k ON k.id=pk.keyword_id {where} GROUP BY p.id ORDER BY p.year DESC, p.id DESC LIMIT ? OFFSET ?", [*params, per_page, (page - 1) * per_page]).fetchall()
    return rows, count, page, per_page


def get_paper(paper_id):
    """Return a paper and separated keyword lists."""
    db = get_db()
    paper = db.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if paper is None:
        return None
    keywords = db.execute("SELECT k.display_name, pk.source FROM paper_keywords pk JOIN keywords k ON k.id=pk.keyword_id WHERE pk.paper_id=? ORDER BY k.display_name", (paper_id,)).fetchall()
    return {**dict(paper), "author_keywords": [r[0] for r in keywords if r[1] == "author"], "extracted_keywords": [r[0] for r in keywords if r[1] == "extracted"]}


def save_paper(data, paper_id=None):
    """Create or update a paper and its keyword relations."""
    db = get_db()
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("标题不能为空")
    conference = (data.get("conference") or "CVPR").strip().upper()
    if conference not in ALLOWED_CONFERENCES:
        raise ValueError("会议必须是 CVPR、ICCV 或 ECCV")
    try:
        year = int(data.get("year") or 2024)
    except (TypeError, ValueError) as exc:
        raise ValueError("年份必须是整数") from exc
    normalized = normalize_title(title)
    duplicate = db.execute("SELECT id FROM papers WHERE normalized_title=? AND conference=? AND year=? AND id != COALESCE(?, -1)", (normalized, conference, year, paper_id)).fetchone()
    if duplicate:
        raise ValueError("同一会议和年份下已存在相同标题")
    values = (title, normalized, data.get("abstract") or None, data.get("authors") or None, conference, year, data.get("paper_number") or None, data.get("original_url") or None, data.get("source") or "manual", _now(), data.get("status") or "complete", data.get("error_message") or None)
    if paper_id:
        db.execute("UPDATE papers SET title=?, normalized_title=?, abstract=?, authors=?, conference=?, year=?, paper_number=?, original_url=?, source=?, fetched_at=?, status=?, error_message=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (*values, paper_id))
        pid = paper_id
        db.execute("DELETE FROM paper_keywords WHERE paper_id=?", (pid,))
    else:
        cursor = db.execute("INSERT INTO papers(title, normalized_title, abstract, authors, conference, year, paper_number, original_url, source, fetched_at, status, error_message) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", values)
        pid = cursor.lastrowid
    author_words = split_keywords(data.get("author_keywords"))
    extracted_words = split_keywords(data.get("extracted_keywords")) or extract_keywords(title, data.get("abstract"))
    for word, source in [(item, "author") for item in author_words] + [(item, "extracted") for item in extracted_words]:
        normalized_word = normalize_keyword(word)
        if not normalized_word:
            continue
        db.execute("INSERT OR IGNORE INTO keywords(normalized, display_name) VALUES (?, ?)", (normalized_word, word.strip()))
        kid = db.execute("SELECT id FROM keywords WHERE normalized=?", (normalized_word,)).fetchone()[0]
        db.execute("INSERT OR IGNORE INTO paper_keywords(paper_id, keyword_id, source) VALUES (?,?,?)", (pid, kid, source))
    db.execute("INSERT OR IGNORE INTO conferences(name, year, collected) VALUES (?,?,1)", (conference, year))
    db.execute("UPDATE conferences SET collected=1 WHERE name=? AND year=?", (conference, year))
    db.commit()
    return pid


def delete_paper(paper_id):
    """Delete a paper and cascade its keyword links."""
    db = get_db()
    cursor = db.execute("DELETE FROM papers WHERE id=?", (paper_id,))
    db.commit()
    return cursor.rowcount > 0


def batch_import(items):
    """Import each item independently so one failure cannot block others."""
    results = []
    for item in items:
        title = item.get("title", "").strip()
        if not title:
            results.append({"title": title, "status": "failed", "message": "标题为空"})
            continue
        try:
            conference = (item.get("conference") or "CVPR").strip().upper()
            existing = get_db().execute("SELECT id FROM papers WHERE normalized_title=? AND conference=? AND year=?", (normalize_title(title), conference, int(item.get("year", 2024)))).fetchone()
            if existing:
                results.append({"title": title, "status": "duplicate", "paper_id": existing[0]})
                continue
            if item.get("force_failure"):
                raise RuntimeError("来源适配器未配置，无法联网获取")
            pid = save_paper({**item, "conference": conference})
            status = "missing_fields" if not item.get("abstract") or not item.get("original_url") else "success"
            results.append({"title": title, "status": status, "paper_id": pid, "message": "摘要或原文链接缺失" if status == "missing_fields" else ""})
        except (ValueError, sqlite3.Error, RuntimeError) as exc:
            results.append({"title": title, "status": "failed", "message": str(exc)})
    return results


def seed_demo_data():
    """Insert deterministic local prototype samples without changing existing papers."""
    inserted = 0
    skipped = 0
    for index, (title, conference, year, keywords) in enumerate(DEMO_PAPERS, start=1):
        exists = get_db().execute(
            "SELECT id FROM papers WHERE normalized_title=? AND conference=? AND year=?",
            (normalize_title(title), conference, year),
        ).fetchone()
        if exists:
            skipped += 1
            continue
        save_paper(
            {
                "title": title,
                "abstract": "Prototype sample for interface and statistics verification.",
                "authors": "Demo Author",
                "conference": conference,
                "year": year,
                "paper_number": f"DEMO-{year}-{index:02d}",
                "original_url": "https://example.com/prototype-paper",
                "source": "prototype_sample",
                "author_keywords": keywords,
                "extracted_keywords": keywords,
            }
        )
        inserted += 1
    return {"inserted": inserted, "skipped": skipped, "total": len(DEMO_PAPERS)}


def lookup_online_paper(query):
    """Look up a paper in the configured online index."""
    result = get_source_adapter().lookup(query)
    return {
        "ok": result.ok,
        "message": result.message,
        "paper": result.paper,
        "papers": list(result.papers),
    }


def fetch_paper_from_cvf(query):
    """Fetch one paper from CVF Open Access and save it locally."""
    result = get_cvf_adapter().lookup(query)
    payload = {
        "ok": result.ok,
        "message": result.message,
        "paper": result.paper,
        "papers": list(result.papers),
    }
    if not result.ok or not result.paper:
        return payload
    try:
        paper_id = save_paper(result.paper)
    except ValueError as exc:
        payload["ok"] = False
        payload["message"] = f"抓取成功，但保存失败：{exc}"
        return payload
    payload["paper_id"] = paper_id
    payload["message"] = "已从 CVF Open Access 抓取并保存论文。"
    return payload


def scope_status(conference, year):
    """Return the status for a conference/year scope."""
    row = get_db().execute("SELECT held, collected FROM conferences WHERE name=? AND year=?", (conference, year)).fetchone()
    if row is None or not row[0]:
        return "not_held"
    if not row[1]:
        return "not_collected"
    return "collected"


def top_keywords(conference=None, year_from=None, year_to=None, limit=10):
    """Rank keyword coverage and return sample size."""
    db = get_db()
    clauses, params = ["p.status != 'failed'"], []
    if conference:
        conference = conference.strip().upper()
        clauses.append("p.conference=?")
        params.append(conference)
    if year_from:
        year_from = _parse_year(year_from)
    if year_to:
        year_to = _parse_year(year_to)
    if year_from is not None:
        clauses.append("p.year>=?")
        params.append(year_from)
    if year_to is not None:
        clauses.append("p.year<=?")
        params.append(year_to)
    where = " AND ".join(clauses)
    sample = db.execute(f"SELECT COUNT(*) FROM papers p WHERE {where}", params).fetchone()[0]
    rows = db.execute(f"SELECT k.display_name name, COUNT(DISTINCT p.id) papers, ROUND(COUNT(DISTINCT p.id)*100.0/NULLIF(?,0), 1) coverage FROM papers p JOIN paper_keywords pk ON pk.paper_id=p.id JOIN keywords k ON k.id=pk.keyword_id WHERE {where} GROUP BY k.id ORDER BY papers DESC, name LIMIT ?", [sample, *params, limit]).fetchall()
    return [dict(r) for r in rows], sample


def _parse_year(value):
    """Convert an optional year to an integer without raising from a route."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def graph_data(conference=None, year_from=None, year_to=None):
    """Return keyword nodes with paper coverage weights."""
    ranked, sample = top_keywords(conference, year_from, year_to, 30)
    names = {normalize_keyword(row["name"]) for row in ranked}
    db = get_db()
    clauses, params = ["p.status != 'failed'"], []
    if conference:
        clauses.append("p.conference=?")
        params.append(conference.upper())
    parsed_from, parsed_to = _parse_year(year_from), _parse_year(year_to)
    if parsed_from is not None:
        clauses.append("p.year>=?")
        params.append(parsed_from)
    if parsed_to is not None:
        clauses.append("p.year<=?")
        params.append(parsed_to)
    rows = db.execute(
        "SELECT pk.paper_id, k.normalized, k.display_name "
        "FROM papers p JOIN paper_keywords pk ON pk.paper_id=p.id "
        "JOIN keywords k ON k.id=pk.keyword_id WHERE " + " AND ".join(clauses),
        params,
    ).fetchall()
    by_paper = {}
    display = {}
    for row in rows:
        if row["normalized"] in names:
            by_paper.setdefault(row["paper_id"], set()).add(row["normalized"])
            display[row["normalized"]] = row["display_name"]
    pair_counts = Counter()
    for keywords in by_paper.values():
        ordered = sorted(keywords)
        pair_counts.update((ordered[index], ordered[other]) for index in range(len(ordered)) for other in range(index + 1, len(ordered)))
    links = [{"source": display[source], "target": display[target], "value": count} for (source, target), count in pair_counts.items()]
    return {"nodes": [{"name": row["name"], "value": row["papers"]} for row in ranked], "links": links, "sample_size": sample}


def trend_data(conferences, year_from, year_to, keyword):
    """Return coverage series and explicit missing-data statuses."""
    db = get_db()
    year_from = _parse_year(year_from) or 2020
    year_to = _parse_year(year_to) or year_from
    if year_to < year_from:
        year_from, year_to = year_to, year_from
    series = []
    for conference in conferences:
        data = []
        for year in range(year_from, year_to + 1):
            status = scope_status(conference, year)
            count = db.execute("SELECT COUNT(DISTINCT p.id) FROM papers p JOIN paper_keywords pk ON pk.paper_id=p.id JOIN keywords k ON k.id=pk.keyword_id WHERE p.conference=? AND p.year=? AND k.normalized=? AND p.status != 'failed'", (conference, year, normalize_keyword(keyword))).fetchone()[0]
            sample = db.execute("SELECT COUNT(*) FROM papers WHERE conference=? AND year=? AND status != 'failed'", (conference, year)).fetchone()[0]
            if status == "not_held":
                data.append({"year": year, "value": None, "status": "not_held", "label": "未举办"})
            elif status == "not_collected":
                data.append({"year": year, "value": None, "status": "not_collected", "label": "未采集"})
            else:
                data.append({"year": year, "value": round(count * 100 / sample, 1) if sample else 0, "status": "zero" if count == 0 else "ok", "label": "零出现" if count == 0 else "有数据", "sample_size": sample})
        series.append({"name": conference, "data": data})
    return {"years": list(range(year_from, year_to + 1)), "keyword": keyword, "series": series}
