"""Shared pages and health endpoint."""

from flask import Blueprint, render_template, request

from .services import top_keywords


pages = Blueprint("pages", __name__)


@pages.get("/")
def index():
    """Render the overview dashboard."""
    conference = request.args.get("conference") or None
    ranking, sample_size = top_keywords(
        conference=conference,
        year_from=request.args.get("year_from") or None,
        year_to=request.args.get("year_to") or None,
    )
    return render_template(
        "overview.html",
        ranking=ranking,
        sample_size=sample_size,
        filters=request.args,
    )


@pages.get("/about")
def about():
    """Render the statistics and data limitation explanation."""
    return render_template("about.html")


@pages.get("/health")
def health():
    """Report process availability, not data or external service health."""
    return {"status": "ok"}
