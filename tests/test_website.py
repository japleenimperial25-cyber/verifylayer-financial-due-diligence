import io
import json
from pathlib import Path

import website
from commentary import DEMO_QUESTION, run_experiment


def _request(monkeypatch, method, path, payload=None, content_type="application/json"):
    handler = object.__new__(website.VerifyLayerHandler)
    handler.path = path
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8") if payload is not None else b""
    handler.rfile = io.BytesIO(body)
    handler.headers = {"Content-Length": str(len(body)), "Content-Type": content_type}
    response = {}
    handler._json = lambda value, status=200: response.update(json=value, status=status)
    handler._send = lambda value, content_type="application/json", status=200: response.update(body=value, content_type=content_type, status=status)
    getattr(handler, f"do_{method}")()
    return response


def _project(tmp_path, monkeypatch):
    data = tmp_path / "data"
    web = tmp_path / "web"
    data.mkdir()
    web.mkdir()
    (tmp_path / "sources.csv").write_text("source_id,title,source_url,publisher,retrieved_at_utc,recorded_at_utc,reporting_period,origin,stored_path,sha256,synthetic\n", encoding="utf-8")
    (tmp_path / "governance.md").write_text("Governance fixture", encoding="utf-8")
    (data / "evaluation_report.md").write_text("Synthetic report fixture", encoding="utf-8")
    experiment = run_experiment([DEMO_QUESTION])
    (data / "evaluation_records.json").write_text(json.dumps(experiment), encoding="utf-8")
    (web / "index.html").write_text("<!doctype html><title>VerifyLayer</title>", encoding="utf-8")
    (web / "styles.css").write_text("body{}", encoding="utf-8")
    (web / "app.js").write_text("void 0;", encoding="utf-8")
    monkeypatch.setattr(website, "ROOT", tmp_path)
    monkeypatch.setattr(website, "WEB", web)
    return experiment


def test_static_routes_serve_only_approved_assets(monkeypatch, tmp_path):
    _project(tmp_path, monkeypatch)
    page = _request(monkeypatch, "GET", "/")
    css = _request(monkeypatch, "GET", "/styles.css")
    script = _request(monkeypatch, "GET", "/app.js")
    traversal = _request(monkeypatch, "GET", "/../sources.csv")
    assert page["status"] == css["status"] == script["status"] == 200
    assert page["content_type"] == "text/html; charset=utf-8"
    assert css["body"] == b"body{}"
    assert script["content_type"] == "text/javascript; charset=utf-8"
    assert traversal["status"] == 404


def test_frontend_has_http_assets_file_open_notice_and_no_remote_font_dependency():
    html = (website.WEB / "index.html").read_text(encoding="utf-8")
    css = (website.WEB / "styles.css").read_text(encoding="utf-8")
    assert 'href="/styles.css"' in html
    assert 'src="/app.js"' in html
    assert 'location.protocol === "file:"' in html
    assert "fonts.googleapis.com" not in css
    assert "https://" not in css
    script_text = (website.WEB / "app.js").read_text(encoding="utf-8")
    assert "https://localhost:8443" in script_text
    assert 'if (typeof value !== "string" || !value.trim()) return "";' in script_text
    assert "const url = new URL(value);" in script_text
    assert 'id="report-disclosure-text"' in html
    assert 'Calculated chart unavailable:' in script_text
    assert "Evidence passages" in script_text
    assert "SYNTHETIC — NOT A REAL FILING" in script_text
    assert "providerTimeout + 60" in script_text
    assert "may take up to ${providerTimeout} seconds" in script_text
    assert 'id="research-provider-status"' in html
    assert "The Python server has answer-model settings" in script_text
    assert "Provider request completed." in script_text
    assert "response_received" in script_text
    assert "No live search or language model is connected." not in html


def test_dashboard_api_reads_project_records_and_empty_registry(monkeypatch, tmp_path):
    experiment = _project(tmp_path, monkeypatch)
    dashboard = _request(monkeypatch, "GET", "/api/dashboard")["json"]
    sources = _request(monkeypatch, "GET", "/api/sources")["json"]
    assert dashboard["source_count"] == 0
    assert dashboard["evaluation"]["label"] == experiment["label"]
    assert dashboard["evaluation"]["question_count"] == 1
    assert dashboard["evaluation"]["metrics"] == experiment["metrics"]
    assert dashboard["research_timeout_seconds"] == 180
    assert sources["sources"] == []


def test_research_endpoint_uses_verifier_and_blocks_synthetic_conflict(monkeypatch, tmp_path):
    _project(tmp_path, monkeypatch)
    response = _request(monkeypatch, "POST", "/api/research", {
        "question": DEMO_QUESTION, "verify": True, "mode": "synthetic"
    })
    assert response["status"] == 200
    result = response["json"]
    assert result["claims"][0]["evidence_status"] == "supported"
    assert result["claims"][0]["citations"][0]["source_id"] == "synthetic-demo"
    assert result["claims"][1]["evidence_status"] == "contradicted"
    assert result["claims"][1]["blocked"] is True


def test_registered_mode_returns_insufficient_evidence_when_retrieval_is_empty(monkeypatch, tmp_path):
    _project(tmp_path, monkeypatch)
    monkeypatch.setattr("commentary.retrieve", lambda _question: [])
    response = _request(monkeypatch, "POST", "/api/research", {
        "question": "What was the company's revenue?", "verify": True, "mode": "registered"
    })
    assert response["status"] == 200
    assert response["json"]["passages"] == []
    assert response["json"]["claims"] == []
    assert response["json"]["answer"] == "No factual claim passed verification; answer withheld."


def test_research_api_reports_model_abstention_when_evidence_was_retrieved(monkeypatch, tmp_path):
    _project(tmp_path, monkeypatch)
    passages = [
        {"source_id": "issuer-test", "title": "Annual report test fixture", "publisher": "Example Limited",
         "page": 120 + index, "text": f"Financial results passage {index}: revenue from operations."}
        for index in range(5)
    ]
    empty_proposal = {"status": "insufficient", "answer": "", "claims": [], "calculations": [],
                      "missing_evidence": ["No exact claim selected."], "limitations": [],
                      "clarification_question": ""}
    monkeypatch.setattr("commentary.retrieve", lambda _question: passages)
    monkeypatch.setattr("commentary.generate_proposal", lambda _question, _passages: empty_proposal)
    response = _request(monkeypatch, "POST", "/api/research", {
        "question": "What does the report say about revenue from operations?", "verify": True, "mode": "registered"
    })
    result = response["json"]
    assert response["status"] == 200
    assert len(result["passages"]) == 5
    assert result["generation_status"] == "generated"
    assert result["provider_status"]["request_attempted"] is True
    assert result["provider_status"]["response_received"] is True
    assert result["proposed_claim_count"] == 0
    assert result["answer_status"] == "insufficient"
    assert "model responded in JSON" in result["generation_note"]


def test_evaluation_recomputes_same_question_and_shared_passages(monkeypatch, tmp_path):
    experiment = _project(tmp_path, monkeypatch)
    result = _request(monkeypatch, "GET", "/api/evaluation")["json"]
    assert result["question_set"] == experiment["question_set"]
    assert len(result["runs"]) == 2
    assert result["runs"][0]["passages"] == result["runs"][1]["passages"]
    assert result["metrics"]["off"]["hallucination_rate_percent"] == 50
    assert result["metrics"]["on"]["hallucination_rate_percent"] == 0
    assert result["metrics"]["on"]["blocked_claim_count"] == 1


def test_report_records_and_governance_routes_return_approved_files(monkeypatch, tmp_path):
    experiment = _project(tmp_path, monkeypatch)
    report = _request(monkeypatch, "GET", "/api/report")
    records = _request(monkeypatch, "GET", "/api/records")
    governance = _request(monkeypatch, "GET", "/api/governance")
    assert report["status"] == records["status"] == governance["status"] == 200
    assert b"Synthetic report fixture" in report["body"]
    assert json.loads(records["body"])["label"] == experiment["label"]
    assert b"Governance fixture" in governance["body"]


def test_missing_report_returns_safe_error_without_traceback(monkeypatch, tmp_path):
    _project(tmp_path, monkeypatch)
    (tmp_path / "data" / "evaluation_report.md").unlink()
    response = _request(monkeypatch, "GET", "/api/report")
    assert response["status"] == 500
    assert response["json"] == {"error": "Unable to load the requested VerifyLayer resource."}
    assert "Traceback" not in json.dumps(response["json"])


def test_research_endpoint_validates_malformed_payloads(monkeypatch, tmp_path):
    _project(tmp_path, monkeypatch)
    malformed = _request(monkeypatch, "POST", "/api/research", b"{")
    wrong_type = _request(monkeypatch, "POST", "/api/research", {"question": 25})
    wrong_mode = _request(monkeypatch, "POST", "/api/research", {"question": "Revenue?", "mode": "other"})
    wrong_content_type = _request(monkeypatch, "POST", "/api/research", {"question": "Revenue?"}, "text/plain")
    too_large = _request(monkeypatch, "POST", "/api/research", b"x" * (website.MAX_REQUEST_BYTES + 1))
    assert malformed["status"] == 400
    assert wrong_type["status"] == wrong_mode["status"] == 400
    assert wrong_content_type["status"] == 415
    assert too_large["status"] == 413


def test_main_requires_local_certificate(monkeypatch, tmp_path):
    monkeypatch.setattr(website, "CERT_FILE", tmp_path / "missing.pem")
    monkeypatch.setattr(website, "KEY_FILE", tmp_path / "missing-key.pem")
    try:
        website.main()
    except SystemExit as exc:
        assert "HTTPS certificate or private key is missing" in str(exc)
    else:
        raise AssertionError("missing certificate should stop HTTPS startup")


def test_main_uses_tls_and_binds_loopback(monkeypatch, capsys, tmp_path):
    seen = {}
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.touch()
    key.touch()
    monkeypatch.setattr(website, "CERT_FILE", cert)
    monkeypatch.setattr(website, "KEY_FILE", key)

    class FakeContext:
        def __init__(self, protocol):
            seen["protocol"] = protocol

        def load_cert_chain(self, certfile, keyfile):
            seen["certfile"] = certfile
            seen["keyfile"] = keyfile

        def wrap_socket(self, sock, server_side):
            seen["server_side"] = server_side
            return "tls-socket"

    monkeypatch.setattr(website.ssl, "SSLContext", FakeContext)
    monkeypatch.setattr(website.ssl, "PROTOCOL_TLS_SERVER", "TLS")

    class FakeServer:
        def __init__(self, address, handler):
            seen["address"] = address
            seen["handler"] = handler
            self.socket = "plain-socket"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            seen["closed"] = True

        def serve_forever(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(website, "ThreadingHTTPServer", FakeServer)
    website.main()
    output = capsys.readouterr().out
    assert seen["address"] == ("127.0.0.1", 8443)
    assert seen["handler"] is website.VerifyLayerHandler
    assert seen["protocol"] == "TLS"
    assert seen["server_side"] is True
    assert seen["certfile"] == cert
    assert seen["keyfile"] == key
    assert seen["closed"] is True
    assert "https://localhost:8443" in output


def test_certificate_directory_is_git_ignored():
    import subprocess

    result = subprocess.run(
        ["git", "check-ignore", "local-dev-certs/localhost+1-key.pem"],
        cwd=website.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
