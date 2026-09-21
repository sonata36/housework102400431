"""Paper management pages and JSON endpoints."""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .services import delete_paper, find_papers, get_paper, lookup_online_paper, save_paper

papers = Blueprint("papers", __name__, url_prefix="/papers")


@papers.get("")
def list_page():
    rows, total, page, per_page = find_papers(request.args)
    return render_template("papers.html", papers=rows, total=total, page=page, per_page=per_page, query=request.args)


@papers.route("/new", methods=["GET", "POST"])
@papers.route("/<int:paper_id>/edit", methods=["GET", "POST"])
def edit_page(paper_id=None):
    paper = get_paper(paper_id) if paper_id else None
    if request.method == "POST":
        try:
            save_paper(request.form.to_dict(), paper_id)
            flash("论文已保存", "success")
            return redirect(url_for("papers.list_page"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("paper_form.html", paper=paper)


@papers.get("/<int:paper_id>")
def detail_page(paper_id):
    paper = get_paper(paper_id)
    if paper is None:
        return render_template("empty.html", message="论文不存在"), 404
    return render_template("paper_detail.html", paper=paper)


@papers.post("/<int:paper_id>/delete")
def delete_page(paper_id):
    delete_paper(paper_id)
    flash("论文已删除", "success")
    return redirect(url_for("papers.list_page"))


@papers.get("/api")
def list_api():
    rows, total, page, per_page = find_papers(request.args)
    return jsonify({"items": [dict(row) for row in rows], "total": total, "page": page, "per_page": per_page})


@papers.get("/online-lookup")
def online_lookup():
    query = request.args.get("q", "").strip()
    result = lookup_online_paper(query)
    if request.args.get("format") == "json" or not request.accept_mimetypes.accept_html:
        return jsonify(result), 200 if result["ok"] else 503
    return render_template("online_lookup.html", query=query, result=result), 200 if result["ok"] else 503
