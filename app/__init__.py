"""Application factory and shared configuration."""

import os
from pathlib import Path

from flask import Flask

from .db import close_db, init_db
from .services import seed_demo_data


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
    return app
