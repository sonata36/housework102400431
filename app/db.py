"""SQLite connection and repeatable schema initialization."""

import sqlite3

from flask import current_app, g

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS conferences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, year INTEGER NOT NULL,
  held INTEGER NOT NULL DEFAULT 1, collected INTEGER NOT NULL DEFAULT 0,
  UNIQUE(name, year)
);
CREATE TABLE IF NOT EXISTS papers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL, normalized_title TEXT NOT NULL,
  abstract TEXT, authors TEXT, conference TEXT NOT NULL, year INTEGER NOT NULL,
  paper_number TEXT, original_url TEXT, source TEXT, fetched_at TEXT,
  status TEXT NOT NULL DEFAULT 'complete', error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(normalized_title, conference, year)
);
CREATE TABLE IF NOT EXISTS keywords (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  normalized TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_keywords (
  paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
  source TEXT NOT NULL CHECK(source IN ('author', 'extracted')),
  PRIMARY KEY(paper_id, keyword_id, source)
);
CREATE TABLE IF NOT EXISTS online_papers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  normalized_title TEXT NOT NULL UNIQUE,
  abstract TEXT,
  authors TEXT,
  conference TEXT,
  year INTEGER,
  paper_number TEXT,
  original_url TEXT,
  keywords TEXT,
  source TEXT NOT NULL DEFAULT 'online-index'
);
CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(normalized_title);
CREATE INDEX IF NOT EXISTS idx_papers_scope ON papers(conference, year);
CREATE INDEX IF NOT EXISTS idx_paper_keywords_keyword ON paper_keywords(keyword_id);
"""


def get_db():
    """Return one row-factory SQLite connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    """Close the request-scoped connection."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the schema and conference status rows idempotently."""
    db = get_db()
    db.executescript(SCHEMA)
    for name in ("CVPR", "ICCV", "ECCV"):
        for year in range(2020, 2027):
            db.execute(
                "INSERT OR IGNORE INTO conferences(name, year) VALUES (?, ?)",
                (name, year),
            )
    online_samples = [
        (
            "Vision Transformer Image Retrieval",
            "vision transformer image retrieval",
            "A searchable paper record for testing the online lookup workflow.",
            "Online Index Author",
            "CVPR",
            2024,
            "ONLINE-001",
            "https://example.com/online/transformer-retrieval",
            "transformer, image retrieval, representation learning",
        ),
        (
            "Promptable Image Segmentation with Transformers",
            "promptable image segmentation with transformers",
            "A searchable paper record for testing title lookup and result display.",
            "Online Index Author",
            "ICCV",
            2023,
            "ONLINE-002",
            "https://example.com/online/promptable-segmentation",
            "transformer, segmentation, prompt learning, vision-language",
        ),
        (
            "Multimodal Video Understanding with Transformers",
            "multimodal video understanding with transformers",
            "A searchable paper record for testing an online result with metadata.",
            "Online Index Author",
            "ECCV",
            2022,
            "ONLINE-003",
            "https://example.com/online/video-understanding",
            "transformer, video understanding, multimodal learning",
        ),
        (
            "Swin Transformer for Hierarchical Visual Recognition",
            "swin transformer for hierarchical visual recognition",
            "A searchable paper record for testing multiple online matches.",
            "Online Index Author",
            "CVPR",
            2021,
            "ONLINE-004",
            "https://example.com/online/swin-transformer",
            "transformer, recognition, attention",
        ),
        (
            "Transformer-Based Object Detection",
            "transformer-based object detection",
            "A searchable paper record for testing a fuzzy title query.",
            "Online Index Author",
            "ECCV",
            2020,
            "ONLINE-005",
            "https://example.com/online/object-detection",
            "transformer, object detection, attention",
        ),
    ]
    legacy_names = {
        "demo vision transformer retrieval": online_samples[0],
        "demo promptable image segmentation": online_samples[1],
        "demo multimodal video understanding": online_samples[2],
    }
    for old_name, record in legacy_names.items():
        db.execute(
            """UPDATE online_papers SET title=?, normalized_title=?, abstract=?,
            authors=?, conference=?, year=?, paper_number=?, original_url=?, keywords=?
            WHERE normalized_title=?""",
            (*record, old_name),
        )
    db.executemany(
        """INSERT OR IGNORE INTO online_papers
        (title, normalized_title, abstract, authors, conference, year,
         paper_number, original_url, keywords)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        online_samples,
    )
    db.commit()
