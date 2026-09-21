"""Analytics pages and ECharts data endpoints."""

from flask import Blueprint, jsonify, render_template, request

from .services import graph_data, top_keywords, trend_data

analytics = Blueprint("analytics", __name__)


@analytics.get("/trends")
def trends_page():
    return render_template("trends.html")


@analytics.get("/api/overview")
def overview_api():
    ranking, sample = top_keywords(request.args.get("conference"), request.args.get("year_from"), request.args.get("year_to"))
    return jsonify({"ranking": ranking, "sample_size": sample, "metric": "论文覆盖率（覆盖论文数 / 有效论文数）"})


@analytics.get("/api/keywords/graph")
def graph_api():
    return jsonify(graph_data(request.args.get("conference"), request.args.get("year_from"), request.args.get("year_to")))


@analytics.get("/api/trends")
def trends_api():
    conferences = [item.strip().upper() for item in request.args.get("conferences", "CVPR,ICCV,ECCV").split(",") if item.strip().upper() in {"CVPR", "ICCV", "ECCV"}]
    years = [int(item) for item in request.args.get("years", "2020,2021,2022,2023,2024").split(",") if item.strip().isdigit()]
    years = years or [2020, 2021, 2022, 2023, 2024]
    return jsonify(trend_data(conferences or ["CVPR"], min(years), max(years), request.args.get("keyword", "transformer")))
