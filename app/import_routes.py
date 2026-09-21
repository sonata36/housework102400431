"""Single and batch paper import endpoints."""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .services import batch_import, fetch_paper_from_cvf

imports = Blueprint("imports", __name__, url_prefix="/import")


@imports.route("", methods=["GET", "POST"])
def import_page():
    results = None
    if request.method == "POST":
        if request.form.get("mode") == "cvf":
            result = fetch_paper_from_cvf(request.form.get("title", ""))
            if result.get("ok") and result.get("paper_id"):
                flash("已从 CVF Open Access 抓取并保存论文", "success")
                return redirect(url_for("papers.detail_page", paper_id=result["paper_id"]))
            results = [{"title": request.form.get("title", ""), "status": "failed", "message": result.get("message", "抓取失败")}]
            return render_template("import.html", results=results)
        titles = request.form.get("titles", "").splitlines() if request.form.get("mode") == "batch" else [request.form.get("title", "")]
        common = {"conference": request.form.get("conference", "CVPR"), "year": request.form.get("year", "2024"), "source": "manual"}
        results = batch_import([{**common, "title": title} for title in titles])
        if request.form.get("save_success") == "1":
            flash("成功项已保存；失败项仍保留在本批次结果中", "success")
    return render_template("import.html", results=results)


@imports.post("/api")
def import_api():
    payload = request.get_json(silent=True) or {}
    results = batch_import(payload.get("items", []))
    statuses = ("success", "duplicate", "missing_fields", "failed")
    return jsonify({"results": results, "summary": {status: sum(item["status"] == status for item in results) for status in statuses}})


@imports.post("/fetch-cvf")
def fetch_cvf_api():
    """Fetch one title from CVF Open Access and persist it."""
    payload = request.get_json(silent=True) or request.form
    result = fetch_paper_from_cvf(payload.get("title", ""))
    return jsonify(result), 200 if result.get("ok") else 502
