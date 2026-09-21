import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.services import (
    batch_import,
    delete_paper,
    find_papers,
    graph_data,
    get_paper,
    normalize_keyword,
    save_paper,
    top_keywords,
    trend_data,
)
from app.sources import CvfOpenAccessAdapter, LookupResult, _parse_cvf_page
from app.services import fetch_paper_from_cvf


class CoreFeatureTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test.sqlite3")
        self.app = create_app({"TESTING": True, "DATABASE": database, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_duplicate_exact_and_fuzzy_search(self):
        with self.app.app_context():
            paper_id = save_paper({
                "title": "Vision Transformers for Detection",
                "conference": "CVPR",
                "year": "2024",
                "abstract": "A transformer method.",
                "author_keywords": "Transformer, Detection",
            })
            with self.assertRaises(ValueError):
                save_paper({"title": " vision   transformers for detection ", "conference": "CVPR", "year": "2024"})
            rows, total, _page, _size = find_papers({"mode": "exact", "q": "VISION TRANSFORMERS FOR DETECTION"})
            self.assertEqual(total, 1)
            self.assertEqual(rows[0]["id"], paper_id)
            _rows, fuzzy_total, _page, _size = find_papers({"mode": "fuzzy", "q": "Detection"})
            self.assertEqual(fuzzy_total, 1)

    def test_keyword_normalization_and_top_ten(self):
        self.assertEqual(normalize_keyword("CNN"), "convolutional neural network")
        with self.app.app_context():
            save_paper({"title": "A", "conference": "CVPR", "year": "2024", "author_keywords": "CNN"})
            ranking, sample = top_keywords("CVPR", "2024", "2024")
            self.assertEqual(sample, 1)
            self.assertEqual(ranking[0]["name"], "CNN")
            self.assertEqual(ranking[0]["papers"], 1)
            self.assertEqual(ranking[0]["coverage"], 100.0)

    def test_graph_contains_cooccurrence_links_and_invalid_inputs_are_safe(self):
        with self.app.app_context():
            save_paper({"title": "Linked Keywords", "conference": "CVPR", "year": "2024", "author_keywords": "CNN, Detection"})
            graph = graph_data("cvpr", "invalid", "2024")
            self.assertEqual(graph["sample_size"], 1)
            self.assertGreaterEqual(len(graph["links"]), 1)
            self.assertTrue(any({link["source"], link["target"]} == {"CNN", "Detection"} for link in graph["links"]))
            rows, total, page, _size = find_papers({"page": "invalid", "year": "invalid"})
            self.assertEqual(page, 1)
            self.assertEqual(total, 1)
            self.assertEqual(len(rows), 1)
            _rows, range_total, _page, _size = find_papers({"year_from": "2024", "year_to": "2024"})
            self.assertEqual(range_total, 1)

    def test_batch_import_keeps_partial_results(self):
        with self.app.app_context():
            results = batch_import([
                {"title": "Complete Item", "conference": "CVPR", "year": "2024", "abstract": "text", "original_url": "https://example.test/a"},
                {"title": "Complete Item", "conference": "CVPR", "year": "2024"},
                {"title": "Missing Abstract", "conference": "CVPR", "year": "2024"},
                {"title": "Failure", "conference": "CVPR", "year": "2024", "force_failure": True},
                {"title": "", "conference": "CVPR", "year": "2024"},
            ])
            self.assertEqual([item["status"] for item in results], ["success", "duplicate", "missing_fields", "failed", "failed"])

    def test_edit_and_delete_service_behavior(self):
        with self.app.app_context():
            paper_id = save_paper({"title": "Before Edit", "conference": "ICCV", "year": "2024", "author_keywords": "tracking"})
            save_paper({"title": "After Edit", "conference": "ICCV", "year": "2024", "author_keywords": "tracking"}, paper_id)
            self.assertEqual(get_paper(paper_id)["title"], "After Edit")
            self.assertTrue(delete_paper(paper_id))
            self.assertIsNone(get_paper(paper_id))
            self.assertFalse(delete_paper(paper_id))

    def test_trend_distinguishes_zero_from_uncollected(self):
        with self.app.app_context():
            save_paper({"title": "Other Paper", "conference": "CVPR", "year": "2023", "author_keywords": "segmentation"})
            save_paper({"title": "Transformer Paper", "conference": "CVPR", "year": "2024", "author_keywords": "Transformer"})
            data = trend_data(["CVPR"], 2023, 2024, "Transformer")
            points = {point["year"]: point for point in data["series"][0]["data"]}
            self.assertEqual(points[2023]["status"], "zero")
            self.assertEqual(points[2024]["status"], "ok")

    def test_trend_marks_unheld_scope(self):
        with self.app.app_context():
            get_db().execute("UPDATE conferences SET held=0 WHERE name='ECCV' AND year=2022")
            get_db().commit()
            data = trend_data(["ECCV"], 2022, 2022, "Transformer")
            self.assertEqual(data["series"][0]["data"][0]["status"], "not_held")

    def test_pages_and_online_failure(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/papers").status_code, 200)
        response = self.client.get("/papers/online-lookup?q=unknown")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["ok"])
        html_response = self.client.get(
            "/papers/online-lookup?q=unknown",
            headers={"Accept": "text/html"},
        )
        self.assertEqual(html_response.status_code, 503)
        self.assertIn("重试", html_response.get_data(as_text=True))
        online_response = self.client.get(
            "/papers/online-lookup?q=Vision%20Transformer%20Image%20Retrieval",
            headers={"Accept": "text/html"},
        )
        self.assertEqual(online_response.status_code, 200)
        self.assertIn("Vision Transformer Image Retrieval", online_response.get_data(as_text=True))
        online_json = self.client.get(
            "/papers/online-lookup?q=transformer&format=json",
        )
        self.assertEqual(online_json.status_code, 200)
        self.assertTrue(online_json.get_json()["ok"])
        self.assertGreaterEqual(len(online_json.get_json()["papers"]), 4)
        self.assertNotIn("Demo", online_response.get_data(as_text=True))
        self.assertNotIn("未配置来源适配器", online_response.get_data(as_text=True))
        self.assertNotIn("未配置外部来源适配器", self.client.get("/import").get_data(as_text=True))
        self.assertIn("暂停", self.client.get("/trends").get_data(as_text=True))

    def test_cvf_parser_and_adapter(self):
        html = """
        <div class='papertitle'>YOLO-World: Real-Time Open-Vocabulary Object Detection</div>
        <div class='authors'>Tianheng Cheng, Lin Song</div>
        <dt>Abstract</dt><dd>We introduce an open-vocabulary detector.</dd>
        <p>Proceedings of CVPR, 2024</p>
        """
        paper = _parse_cvf_page(html, "https://openaccess.thecvf.com/paper.html")
        self.assertEqual(paper["title"], "YOLO-World: Real-Time Open-Vocabulary Object Detection")
        self.assertEqual(paper["conference"], "CVPR")
        self.assertEqual(paper["year"], 2024)

        class Response:
            def __init__(self, body):
                self.body = body.encode("utf-8")
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self):
                return self.body

        calls = []
        def opener(request, timeout=0):
            calls.append(request.full_url)
            if len(calls) == 1:
                return Response('<a href="/content/CVPR2024/html/Cheng_paper.html">YOLO-World: Real-Time Open-Vocabulary Object Detection</a>')
            return Response(html)

        result = CvfOpenAccessAdapter(opener=opener).lookup("YOLO-World: Real-Time Open-Vocabulary Object Detection")
        self.assertTrue(result.ok)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.paper["year"], 2024)

    def test_cvf_fetch_saves_and_rejects_duplicate(self):
        paper = {
            "title": "Fetched CVF Paper",
            "conference": "CVPR",
            "year": 2024,
            "abstract": "An abstract.",
            "authors": "Author",
            "original_url": "https://openaccess.thecvf.com/paper.html",
            "source": "CVF Open Access",
            "extracted_keywords": "transformer, detection",
        }
        with self.app.app_context(), patch(
            "app.services.get_cvf_adapter"
        ) as adapter_factory:
            adapter_factory.return_value.lookup.return_value = LookupResult(
                True, "ok", paper, (paper,)
            )
            first = fetch_paper_from_cvf(paper["title"])
            second = fetch_paper_from_cvf(paper["title"])
        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertIn("保存失败", second["message"])

    def test_cvf_fetch_network_failure_is_explicit(self):
        with self.app.app_context(), patch(
            "app.services.get_cvf_adapter"
        ) as adapter_factory:
            adapter_factory.return_value.lookup.return_value = LookupResult(
                False, "CVF Open Access 查询失败：网络超时"
            )
            result = fetch_paper_from_cvf("Unavailable Paper")
        self.assertFalse(result["ok"])
        self.assertIn("网络超时", result["message"])
        self.assertIsNone(result["paper"])


if __name__ == "__main__":
    unittest.main()
