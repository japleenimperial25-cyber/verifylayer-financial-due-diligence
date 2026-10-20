import csv
import io
import json

import app
import rag
import website
import pytest
from commentary import DEMO_QUESTION, run_experiment, run_workflow


def _source(source_id, title, publisher, *, synthetic="false"):
    return {
        "source_id": source_id, "title": title, "publisher": publisher, "source_url": "https://example.invalid/report.pdf",
        "synthetic": synthetic, "stored_path": f"data/{source_id}.txt", "reporting_period": "FY2025",
    }


def test_retrieval_filters_company_metric_and_synthetic_evidence(tmp_path, monkeypatch):
    sources = [
        _source("tata", "FY2025 annual report", "Tata Steel Limited"),
        _source("sun", "FY2025 annual report", "Sun Pharmaceutical Industries Limited"),
        _source("fake", "Synthetic Tata revenue example", "Synthetic demo", synthetic="true"),
    ]
    registry = tmp_path / "sources.csv"
    with registry.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=sources[0].keys())
        writer.writeheader()
        writer.writerows(sources)
    passages = {
        "tata": [{"source_id": "tata", "page": 8, "text": "Tata Steel reported revenue of INR 100 crore in FY2025."}],
        "sun": [{"source_id": "sun", "page": 9, "text": "Sun Pharmaceutical reported revenue of INR 200 crore in FY2025."}],
        "fake": [{"source_id": "fake", "page": 1, "text": "Synthetic Tata revenue of INR 999 crore in FY2025."}],
    }
    monkeypatch.setattr(rag, "ROOT", tmp_path)
    monkeypatch.setattr(rag, "extract_registered", lambda source_id: passages[source_id])

    tata = rag.retrieve("What was TATA Steel revenue in FY2025?")
    sun = rag.retrieve("What was Sun Pharma revenue in FY2025?")
    missing_company = rag.retrieve("What was Reliance revenue in FY2025?")
    missing_metric = rag.retrieve("What was Tata Steel EBITDA in FY2025?")
    wrong_period = rag.retrieve("What was Tata Steel revenue in FY2024?")
    wrong_units = rag.retrieve("What was Tata Steel revenue in USD million?")
    assert [item["source_id"] for item in tata] == ["tata"]
    assert [item["source_id"] for item in sun] == ["sun"]
    assert missing_company == []
    assert missing_metric == []
    assert wrong_period == []
    assert wrong_units == []
    assert tata[0]["page"] == 8
    assert "fake" not in {item["source_id"] for item in rag.retrieve("What was Tata revenue in FY2025?")}


def test_financial_results_rank_above_operational_passages_for_revenue_query(tmp_path, monkeypatch):
    source = _source("tata", "Tata Steel Integrated Report FY2024-25", "Tata Steel Limited")
    source["reporting_period"] = "FY2024-25"
    registry = tmp_path / "sources.csv"
    with registry.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=source.keys())
        writer.writeheader()
        writer.writerow(source)
    passages = [
        {"source_id": "tata", "page": 53,
         "text": "Tata Steel FY2024-25 operations continued manufacturing improvement. "
                 "Revenue from operations is discussed in the nature-related strategy and supply-chain context."},
        {"source_id": "tata", "page": 130,
         "text": "BOARD'S REPORT\nA. Financial Results\n(H crore)\nTata Steel Standalone Tata Steel Group\n"
                 "2024-25 2023-24 2024-25 2023-24\nRevenue from operations 1,32,516.66 1,40,932.65 2,18,542.51 2,29,170.78"},
    ]
    monkeypatch.setattr(rag, "ROOT", tmp_path)
    monkeypatch.setattr(rag, "extract_registered", lambda _source_id: passages)

    query = "Tata Steel FY2024-25 revenue from operations financial results"
    assert rag.analyze_question(query)["periods"] == ["FY2024-25"]
    results = rag.retrieve(query, source_ids=["tata"])
    assert results[0]["page"] == 130
    assert "A. Financial Results" in results[0]["text"]


def test_explicit_corpus_selection_and_no_match_withhold_facts(monkeypatch):
    monkeypatch.setattr("commentary.retrieve", lambda question, **kwargs: [])
    result = run_workflow("What was Tata revenue in FY2025?", source_ids=[])
    assert result["passages"] == []
    assert result["claims"] == []
    assert result["evidence_status"] == "insufficient"
    assert "No live web" in result["insufficient_reason"]
    assert result["request_context"] == {
        "company_or_entity": "tata", "metrics": ["revenue"], "periods": ["FY2025"], "units": []
    }


def test_ambiguous_short_company_name_returns_clarification_before_retrieval(tmp_path, monkeypatch):
    sources = [_source("tata-steel", "Tata Steel FY2025 annual report", "Tata Steel Limited"),
               _source("tata-motors", "Tata Motors FY2025 annual report", "Tata Motors Limited")]
    registry = tmp_path / "sources.csv"
    with registry.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=sources[0].keys())
        writer.writeheader()
        writer.writerows(sources)
    monkeypatch.setattr(rag, "ROOT", tmp_path)
    monkeypatch.setattr("commentary.retrieve", lambda *_args, **_kwargs: pytest.fail("ambiguous query should not retrieve"))
    result = run_workflow("What was Tata revenue?")
    assert result["answer_status"] == "clarification"
    assert result["generation_status"] == "clarification_required"
    assert result["ambiguity_candidates"] == ["Tata Motors Limited", "Tata Steel Limited"]


def test_saved_evaluation_never_calls_optional_model(monkeypatch):
    monkeypatch.setattr("commentary.generate_proposal", lambda *_args: pytest.fail("evaluation must stay deterministic"))
    experiment = run_experiment([DEMO_QUESTION])
    assert "SYNTHETIC CONTROLLED DEMONSTRATION" in experiment["label"]
    assert all(run["generation_status"] == "not_applicable" for run in experiment["runs"])


def _website_post(monkeypatch, payload):
    handler = object.__new__(website.VerifyLayerHandler)
    handler.path = "/api/research"
    body = json.dumps(payload).encode()
    handler.rfile = io.BytesIO(body)
    handler.headers = {"Content-Length": str(len(body)), "Content-Type": "application/json"}
    response = {}
    handler._json = lambda value, status=200: response.update(value=value, status=status)
    handler.do_POST()
    return response


def test_synthetic_demo_rejects_arbitrary_research_question(monkeypatch, tmp_path):
    (tmp_path / "sources.csv").write_text(
        "source_id,title,source_url,publisher,published_on,retrieved_at_utc,recorded_at_utc,reporting_period,origin,stored_path,sha256,synthetic\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(website, "ROOT", tmp_path)
    response = _website_post(monkeypatch, {"question": "What was Tata revenue?", "mode": "synthetic"})
    assert response["status"] == 400
    assert "fixed, clearly labeled demo question" in response["value"]["error"]


def test_synthetic_demo_remains_available_only_for_its_fixed_question(monkeypatch, tmp_path):
    (tmp_path / "sources.csv").write_text(
        "source_id,title,source_url,publisher,published_on,retrieved_at_utc,recorded_at_utc,reporting_period,origin,stored_path,sha256,synthetic\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(website, "ROOT", tmp_path)
    response = _website_post(monkeypatch, {"question": DEMO_QUESTION, "mode": "synthetic"})
    assert response["status"] == 200
    assert response["value"]["evidence_status"] == "demo"
    assert response["value"]["passages"][0]["synthetic"] == "true"


def test_source_selection_api_rejects_unknown_ids(monkeypatch, tmp_path):
    (tmp_path / "sources.csv").write_text(
        "source_id,title,source_url,publisher,published_on,retrieved_at_utc,recorded_at_utc,reporting_period,origin,stored_path,sha256,synthetic\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(website, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="unknown registered source ID"):
        website._selected_source_ids({"source_ids": ["not-registered"]})


def test_vercel_wsgi_rejects_arbitrary_synthetic_company_question(monkeypatch, tmp_path):
    (tmp_path / "sources.csv").write_text(
        "source_id,title,source_url,publisher,published_on,retrieved_at_utc,recorded_at_utc,reporting_period,origin,stored_path,sha256,synthetic\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(website, "ROOT", tmp_path)
    payload = json.dumps({"question": "What was Tata revenue?", "mode": "synthetic"}).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/api/research", "CONTENT_TYPE": "application/json",
               "CONTENT_LENGTH": str(len(payload)), "wsgi.input": io.BytesIO(payload)}
    captured = {}
    body = b"".join(app.application(environ, lambda status, headers: captured.update(status=status)))
    assert captured["status"] == "400 Bad Request"
    assert "fixed, clearly labeled demo question" in json.loads(body)["error"]


def test_frontend_uses_registered_corpus_for_research_and_separates_fixed_demo():
    html = (website.WEB / "index.html").read_text(encoding="utf-8")
    script = (website.WEB / "app.js").read_text(encoding="utf-8")
    assert 'id="source-ids" multiple' in html
    assert 'id="run-synthetic-demo"' in html
    assert 'mode: "registered", source_ids: sourceIds' in script
    assert 'mode: "synthetic"' in script
    assert 'id="source-mode"' not in html
