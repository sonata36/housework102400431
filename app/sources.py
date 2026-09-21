"""Paper lookup sources, including the CVF Open Access adapter."""

import re
from html.parser import HTMLParser
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen
from dataclasses import dataclass
from typing import Protocol

from .db import get_db


@dataclass(frozen=True)
class LookupResult:
    """Normalized outcome returned by a paper lookup source."""

    ok: bool
    message: str
    paper: dict | None = None
    papers: tuple[dict, ...] = ()


class PaperSourceAdapter(Protocol):
    """Interface used by the paper lookup route."""

    def lookup(self, query: str) -> LookupResult:
        """Look up one title without changing the local paper database."""


def _normalize(value):
    return re.sub(r"\s+", " ", (value or "").strip().casefold())


class OnlineDatabaseAdapter:
    """Search the preloaded online index used by the local application."""

    def lookup(self, query: str) -> LookupResult:
        normalized = _normalize(query)
        if not normalized:
            return LookupResult(False, "请输入论文标题后再查询。", papers=())
        rows = get_db().execute(
            """SELECT * FROM online_papers
            WHERE normalized_title = ? OR normalized_title LIKE ?
            ORDER BY normalized_title = ? DESC, title
            LIMIT 20""",
            (normalized, f"%{normalized}%", normalized),
        ).fetchall()
        if not rows:
            return LookupResult(False, "未找到匹配论文，请检查标题后重试。", papers=())
        papers = tuple(dict(row) for row in rows)
        return LookupResult(True, f"已找到 {len(papers)} 篇匹配论文。", papers[0], papers)


class _CvfPaperParser(HTMLParser):
    """Extract title, authors and abstract from one CVF HTML page."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.authors = ""
        self.abstract = ""
        self._section = None
        self._abstract_pending = False
        self._parts = {"title": [], "authors": [], "abstract": []}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if "papertitle" in classes:
            self._section = "title"
        elif "authors" in classes:
            self._section = "authors"
        elif tag == "dd" and self._abstract_pending:
            self._section = "abstract"
            self._abstract_pending = False
        elif tag == "dt":
            self._section = None

    def handle_data(self, data):
        if self._section in self._parts:
            self._parts[self._section].append(data)
        elif self._section is None and data.strip().lower() == "abstract":
            self._abstract_pending = True

    def handle_endtag(self, tag):
        if tag in {"div", "dd", "p"} and self._section in {"title", "authors", "abstract"}:
            value = " ".join("".join(self._parts[self._section]).split())
            if self._section == "title" and value:
                self.title = value
            elif self._section == "authors" and value:
                self.authors = value
            elif self._section == "abstract" and value:
                self.abstract = value
            self._section = None


def _parse_cvf_page(html, page_url):
    parser = _CvfPaperParser()
    parser.feed(html)
    if not parser.title:
        raise ValueError("CVF 页面未提供论文标题")
    conference_match = re.search(r"(CVPR|ICCV|ECCV)\s*,\s*(20\d{2})", html, re.I)
    conference = conference_match.group(1).upper() if conference_match else "CVPR"
    year = int(conference_match.group(2)) if conference_match else None
    abstract = parser.abstract or None
    extracted = ", ".join(re.findall(r"[A-Za-z][A-Za-z-]{3,}", f"{parser.title} {abstract or ''}")[:8])
    return {
        "title": parser.title,
        "authors": parser.authors or None,
        "abstract": abstract,
        "conference": conference,
        "year": year,
        "original_url": page_url,
        "source": "CVF Open Access",
        "extracted_keywords": extracted,
        "status": "complete" if abstract else "missing_fields",
    }


class CvfOpenAccessAdapter:
    """Fetch a paper page from CVF Open Access by an exact title search."""

    base_url = "https://openaccess.thecvf.com"

    def __init__(self, opener=None, timeout=4, years=range(2020, 2027)):
        self.opener = opener or urlopen
        self.timeout = timeout
        self.years = tuple(years)

    def lookup(self, query: str) -> LookupResult:
        normalized = _normalize(query)
        if not normalized:
            return LookupResult(False, "请输入论文标题后再查询。")
        try:
            page_url = None
            matched_title = None
            for conference in ("CVPR", "ICCV", "ECCV"):
                for year in self.years:
                    index_url = f"{self.base_url}/{conference}{year}?day=all"
                    request = Request(index_url, headers={"User-Agent": "CV-Hotspot-Research/1.1"})
                    try:
                        with self.opener(request, timeout=self.timeout) as response:
                            index_html = response.read().decode("utf-8", errors="replace")
                    except OSError:
                        continue
                    candidates = re.findall(
                        r'<a[^>]+href=["\']([^"\']+paper\.html)["\'][^>]*>(.*?)</a>',
                        index_html,
                        re.I | re.S,
                    )
                    for href, anchor_text in candidates:
                        candidate = re.sub(r"<[^>]+>", " ", anchor_text)
                        candidate = " ".join(candidate.split())
                        if _normalize(candidate) == normalized:
                            page_url = urljoin(self.base_url, href)
                            matched_title = candidate
                            break
                    if page_url:
                        break
                if page_url:
                    break
            if not page_url:
                return LookupResult(False, "CVF Open Access 未找到匹配论文。")
            request = Request(page_url, headers={"User-Agent": "CV-Hotspot-Research/1.1"})
            with self.opener(request, timeout=self.timeout) as response:
                page_html = response.read().decode("utf-8", errors="replace")
            paper = _parse_cvf_page(page_html, page_url)
            if _normalize(paper["title"]) != normalized and _normalize(matched_title) != normalized:
                return LookupResult(False, "CVF 返回的标题与查询不一致，请改用更完整的标题。")
            return LookupResult(True, "已从 CVF Open Access 获取论文信息。", paper, (paper,))
        except (OSError, ValueError, UnicodeError) as exc:
            return LookupResult(False, f"CVF Open Access 查询失败：{exc}")


def get_source_adapter() -> PaperSourceAdapter:
    """Return the configured local index source for backward-compatible lookup."""
    return OnlineDatabaseAdapter()


def get_cvf_adapter() -> PaperSourceAdapter:
    """Return the real CVF Open Access source adapter."""
    return CvfOpenAccessAdapter()
