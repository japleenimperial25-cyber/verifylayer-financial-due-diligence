import io
import json

import app
import website
from commentary import DEMO_QUESTION


def _call(monkeypatch, tmp_path, method, path, payload=None, content_type="application/json"):
    data = tmp_path / "data"
    web = tmp_path / "web"
    data.mkdir(exist_ok=True)
    web.mkdir(exist_ok=True)
    (tmp_path / "sources.csv").write_text(
        "source_id,title,source_url,publisher,retrieved_at_utc,recorded_at_utc,reporting_period,origin,stored_path,sha256,synthetic\n",
        encoding="utf-8",
    )
    (tmp_path / "governance.md").write_text("Governance fixture", encoding="utf-8")
    (data / "evaluation_records.json").write_text(
        json.dumps({"label": "SYNTHETIC CONTROLLED DEMONSTRATION - NOT EMPIRICAL RESEARCH",
                    "question_set": [DEMO_QUESTION], "corpus": []}),
        encoding="utf-8",
    )
    (data / "evaluation_report.md").write_text("Synthetic report fixture", encoding="utf-8")
    (web / "index.html").write_text("<!doctype html><title>VerifyLayer</title>", encoding="utf-8")
    (web / "styles.css").write_text("body{}", encoding="utf-8")
    (web / "app.js").write_text("void 0;", encoding="utf-8")
    monkeypatch.setattr(website, "ROOT", tmp_path)
    monkeypatch.setattr(website, "WEB", web)

    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    captured = {}
    response = b"".join(app.application(environ, lambda status, headers: captured.update(
        status=status, headers=dict(headers)
    )))
    return captured, response


def test_vercel_wsgi_serves_website_and_existing_dashboard(monkeypatch, tmp_path):
    page, html = _call(monkeypatch, tmp_path, "GET", "/")
    dashboard, body = _call(monkeypatch, tmp_path, "GET", "/api/dashboard")
    assert page["status"] == "200 OK"
    assert b"VerifyLayer" in html
    assert dashboard["status"] == "200 OK"
    assert json.loads(body)["source_count"] == 0


def test_vercel_wsgi_research_runs_existing_verification(monkeypatch, tmp_path):
    captured, body = _call(monkeypatch, tmp_path, "POST", "/api/research", {
        "question": DEMO_QUESTION, "verify": True, "mode": "synthetic"
    })
    result = json.loads(body)
    assert captured["status"] == "200 OK"
    assert result["condition"] == "on"
    assert result["claims"][0]["evidence_status"] == "supported"
    assert result["claims"][1]["blocked"] is True


def test_vercel_wsgi_rejects_invalid_research_content_type(monkeypatch, tmp_path):
    captured, body = _call(monkeypatch, tmp_path, "POST", "/api/research", {}, "text/plain")
    assert captured["status"] == "415 Unsupported Media Type"
    assert "Content-Type" in json.loads(body)["error"]
