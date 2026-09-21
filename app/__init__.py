"""Application factory and shared configuration."""
import os
import json
from pathlib import Path
from flask import Flask
from .db import close_db, init_db, get_db
from .services import seed_demo_data


def init_sample_papers():
    db = get_db()
    # 判断是否已经导入数据，避免重复插入
    count_row = db.execute("SELECT COUNT(*) AS cnt FROM online_papers").fetchone()
    if count_row["cnt"] > 5:
        print("数据库已有论文，跳过初始化")
        db.close()
        return

    json_path = Path(__file__).parent.parent / "papers_sample.json"
    with open(json_path, "r", encoding="utf-8") as f:
        paper_list = json.load(f)

    for item in paper_list:
        # 字段和online_papers表严格对齐
        db.execute("""
            INSERT OR IGNORE INTO online_papers
            (title, normalized_title, abstract, authors, conference, year,
             paper_number, original_url, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["title"],
            item["normalized_title"],
            item["abstract"],
            item["authors"],
            item["conference"],
            item["year"],
            item["paper_number"],
            item["original_url"],
            item["keywords"]
        ))
    db.commit()
    db.close()
    print(f"✅ 成功载入 {len(paper_list)} 篇样例论文")


def create_app(test_config=None):
    """Create a configured Flask application."""
    app = Flask(__name__)
    project_root = Path(app.root_path).parent
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "local-development-only"),
        DATABASE=os.environ.get(
            "PAPER_TRENDS_DATABASE",
            str(project_root / "instance" / "papers.sqlite3"),
        ),
    )

    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)

    from .routes import pages
    from .paper_routes import papers
    from .import_routes import imports
    from .analytics_routes import analytics
    app.register_blueprint(pages)
    app.register_blueprint(papers)
    app.register_blueprint(imports)
    app.register_blueprint(analytics)

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables and conference status records."""
        init_db()
        print("Initialized the database.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Insert the local prototype dataset used for interface verification."""
        result = seed_demo_data()
        print(
            f"Demo data ready: inserted={result['inserted']}, "
            f"skipped={result['skipped']}, total={result['total']}"
        )

    with app.app_context():
        init_db()
        init_sample_papers()

    return app
