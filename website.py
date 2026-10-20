"""Dependency-free browser website for the existing VerifyLayer engine."""

import csv
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from commentary import DEMO_QUESTION, run_experiment, run_workflow

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
HOST = "127.0.0.1"
HTTPS_PORT = 8443
CERT_DIR = ROOT / "local-dev-certs"
CERT_FILE = CERT_DIR / "verifylayer.pem"
KEY_FILE = CERT_DIR / "verifylayer-key.pem"
MAX_REQUEST_BYTES = 64 * 1024
STATIC_ASSETS = {"index.html", "styles.css", "app.js"}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sources() -> list[dict[str, str]]:
    with (ROOT / "sources.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def dashboard_data() -> dict:
    records_path = ROOT / "data" / "evaluation_records.json"
    records = _read_json(records_path) if records_path.exists() else None
    return {
        "title": "AI-Powered Investment Verification & Due Diligence: Evidence Behind Every Investment Decision",
        "system": "VerifyLayer — Citation-Grounded Verification",
        "layers": ["Ingest", "Extract", "Engine", "Commentary and verification", "Output"],
        "source_count": len(_sources()),
        "evaluation": ({
            "label": records.get("label"),
            "created_at_utc": records.get("created_at_utc"),
            "question_set": records.get("question_set", []),
            "question_count": len(records.get("question_set", [])),
            "metrics": records.get("metrics", {}),
        } if records else None),
        "report_available": (ROOT / "data" / "evaluation_report.md").exists(),
        "governance_available": (ROOT / "governance.md").exists(),
        "research_status": (
            "Synthetic data is included; this is not empirical research. No live LLM is connected."
            if records and "SYNTHETIC" in str(records.get("label", "")) else
            "Local corpus rule-based evaluation; not an LLM empirical study. No live LLM is connected."
            if records else "No saved evaluation record is available. No live LLM is connected."
        ),
    }


class VerifyLayerHandler(BaseHTTPRequestHandler):
    server_version = "VerifyLayer/1.0"
    sys_version = ""

    def _send(self, body: bytes, content_type: str = "application/json; charset=utf-8", status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: dict, status: int = 200) -> None:
        self._send(json.dumps(value, ensure_ascii=False).encode("utf-8"), status=status)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/dashboard":
                self._json(dashboard_data())
            elif path == "/api/sources":
                self._json({"sources": _sources()})
            elif path == "/api/evaluation":
                saved = _read_json(ROOT / "data" / "evaluation_records.json")
                questions = saved.get("question_set") or [DEMO_QUESTION]
                if str(saved.get("label", "")).startswith("SYNTHETIC CONTROLLED DEMONSTRATION"):
                    # Recompute the saved synthetic demo with the same deterministic source fixture.
                    result = run_experiment(questions)
                else:
                    result = run_experiment(questions, corpus=saved.get("corpus") or [])
                self._json(result)
            elif path == "/api/report":
                self._send((ROOT / "data" / "evaluation_report.md").read_bytes(), "text/markdown; charset=utf-8")
            elif path == "/api/records":
                self._send((ROOT / "data" / "evaluation_records.json").read_bytes(), "application/json; charset=utf-8")
            elif path == "/api/governance":
                self._send((ROOT / "governance.md").read_bytes(), "text/markdown; charset=utf-8")
            else:
                relative = "index.html" if path == "/" else path.lstrip("/")
                if relative not in STATIC_ASSETS:
                    self._json({"error": "Not found"}, 404)
                    return
                target = (WEB / relative).resolve()
                if WEB.resolve() not in target.parents or not target.is_file():
                    self._json({"error": "Not found"}, 404)
                    return
                content_type = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                                ".js": "text/javascript; charset=utf-8"}[target.suffix]
                self._send(target.read_bytes(), content_type)
        except Exception as exc:
            print(f"GET {path} failed: {type(exc).__name__}")
            self._json({"error": "Unable to load the requested VerifyLayer resource."}, 500)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/research":
            self._json({"error": "Not found"}, 404)
            return
        try:
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._json({"error": "Content-Type must be application/json."}, 415)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except (TypeError, ValueError):
                raise ValueError("Invalid Content-Length header.") from None
            if length < 0:
                raise ValueError("Invalid Content-Length header.")
            if length > MAX_REQUEST_BYTES:
                self._json({"error": "Request body is too large."}, 413)
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            raw_question = payload.get("question", "")
            if not isinstance(raw_question, str):
                raise ValueError("Question must be text.")
            question = raw_question.strip()
            if not question:
                raise ValueError("Enter a research question.")
            if len(question) > 2000:
                raise ValueError("Question must be 2,000 characters or fewer.")
            verify = payload.get("verify", True)
            if not isinstance(verify, bool):
                raise ValueError("Verification mode must be true or false.")
            mode = payload.get("mode", "registered")
            if not isinstance(mode, str) or mode not in {"registered", "synthetic"}:
                raise ValueError("Mode must be 'registered' or 'synthetic'.")
            demo = mode == "synthetic"
            result = run_workflow(question, verify=verify, demo=demo)
            self._json(result)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            print(f"POST /api/research failed: {type(exc).__name__}")
            self._json({"error": "The research workflow could not complete. Check the server terminal for details."}, 500)

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    if not CERT_FILE.is_file() or not KEY_FILE.is_file():
        raise SystemExit(
            "HTTPS certificate or private key is missing. Create them with mkcert: "
            f'"<mkcert.exe> -cert-file "{CERT_FILE}" -key-file "{KEY_FILE}" localhost 127.0.0.1"'
        )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    except (OSError, ssl.SSLError) as exc:
        raise SystemExit(f"Unable to load local HTTPS certificate/key: {exc}") from exc

    with ThreadingHTTPServer((HOST, HTTPS_PORT), VerifyLayerHandler) as server:
        server.socket = context.wrap_socket(server.socket, server_side=True)
        print(f"VerifyLayer website running at https://localhost:{HTTPS_PORT}", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("VerifyLayer website stopped.", flush=True)


if __name__ == "__main__":
    main()
