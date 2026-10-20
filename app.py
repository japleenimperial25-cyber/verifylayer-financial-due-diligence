"""Vercel WSGI entry point for the existing VerifyLayer browser website."""

import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

import website
from commentary import DEMO_QUESTION, run_experiment, run_workflow


MAX_REQUEST_BYTES = website.MAX_REQUEST_BYTES
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


def _json_response(value: dict, status: int = 200) -> tuple[int, str, bytes]:
    return status, "application/json; charset=utf-8", json.dumps(value, ensure_ascii=False).encode("utf-8")


def _dispatch(method: str, path: str, environ: dict) -> tuple[int, str, bytes]:
    """Dispatch the same site pages and API operations used by website.py."""
    if method == "GET":
        if path == "/api/dashboard":
            return _json_response(website.dashboard_data())
        if path == "/api/sources":
            return _json_response({"sources": website._sources()})
        if path == "/api/evaluation":
            records = website._read_json(website.ROOT / "data" / "evaluation_records.json")
            questions = records.get("question_set") or [DEMO_QUESTION]
            if str(records.get("label", "")).startswith("SYNTHETIC CONTROLLED DEMONSTRATION"):
                result = run_experiment(questions)
            else:
                result = run_experiment(questions, corpus=records.get("corpus") or [])
            return _json_response(result)
        if path == "/api/report":
            return 200, "text/markdown; charset=utf-8", (website.ROOT / "data" / "evaluation_report.md").read_bytes()
        if path == "/api/records":
            return 200, "application/json; charset=utf-8", (website.ROOT / "data" / "evaluation_records.json").read_bytes()
        if path == "/api/governance":
            return 200, "text/markdown; charset=utf-8", (website.ROOT / "governance.md").read_bytes()

        relative = "index.html" if path == "/" else path.lstrip("/")
        if relative not in website.STATIC_ASSETS:
            return _json_response({"error": "Not found"}, 404)
        target = (website.WEB / relative).resolve()
        if website.WEB.resolve() not in target.parents or not target.is_file():
            return _json_response({"error": "Not found"}, 404)
        return 200, CONTENT_TYPES[target.suffix], target.read_bytes()

    if method != "POST" or path != "/api/research":
        return _json_response({"error": "Not found"}, 404)

    if environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json":
        return _json_response({"error": "Content-Type must be application/json."}, 415)
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except (TypeError, ValueError):
        return _json_response({"error": "Invalid Content-Length header."}, 400)
    if length < 0:
        return _json_response({"error": "Invalid Content-Length header."}, 400)
    if length > MAX_REQUEST_BYTES:
        return _json_response({"error": "Request body is too large."}, 413)
    try:
        payload = json.loads(environ["wsgi.input"].read(length))
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        question = payload.get("question", "")
        if not isinstance(question, str):
            raise ValueError("Question must be text.")
        question = question.strip()
        if not question:
            raise ValueError("Enter a research question.")
        if len(question) > 2000:
            raise ValueError("Question must be 2,000 characters or fewer.")
        verify = payload.get("verify", True)
        if not isinstance(verify, bool):
            raise ValueError("Verification mode must be true or false.")
        mode = payload.get("mode", "registered")
        if mode not in {"registered", "synthetic"}:
            raise ValueError("Mode must be 'registered' or 'synthetic'.")
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return _json_response({"error": str(exc)}, 400)

    try:
        return _json_response(run_workflow(question, verify=verify, demo=mode == "synthetic"))
    except Exception:
        return _json_response({"error": "The research workflow could not complete."}, 500)


def application(environ: dict, start_response) -> list[bytes]:
    """WSGI callable supported by Vercel's Python runtime."""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = urlsplit(environ.get("PATH_INFO", "/")).path
    try:
        status, content_type, body = _dispatch(method, path, environ)
    except Exception:
        status, content_type, body = _json_response(
            {"error": "Unable to load the requested VerifyLayer resource."}, 500
        )
    reason = HTTPStatus(status).phrase
    start_response(f"{status} {reason}", [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ])
    return [body]


# Vercel recognizes a top-level WSGI variable named `app` or `application`.
app = application
