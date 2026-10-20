"""Register supplied public financial documents with reproducible provenance."""

import argparse
import csv
import hashlib
import os
import tempfile
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SOURCES = ROOT / "sources.csv"
FIELDS = ["source_id", "title", "source_url", "publisher", "published_on", "retrieved_at_utc",
          "recorded_at_utc", "reporting_period", "origin", "stored_path", "sha256", "synthetic"]
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".csv"}
MIME_SUFFIXES = {"application/pdf": ".pdf", "text/plain": ".txt", "text/markdown": ".md",
                 "text/csv": ".csv", "application/csv": ".csv"}


def _suffix_for_document(uri: str, media_type: str) -> str:
    suffix = Path(urlsplit(uri).path).suffix.lower() if uri else ""
    if not suffix:
        suffix = MIME_SUFFIXES.get(media_type.split(";", 1)[0].strip().lower(), "")
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("supported document types are PDF, TXT, Markdown, and CSV")
    return suffix


def _validate_content(content: bytes, suffix: str, media_type: str = "") -> None:
    if not content:
        raise ValueError("document is empty")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"document exceeds the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit")
    normalized_type = media_type.split(";", 1)[0].strip().lower()
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("file extension or response type says PDF, but the content is not a PDF")
        if normalized_type and normalized_type not in {"application/pdf", "application/octet-stream", "binary/octet-stream"}:
            raise ValueError(f"unexpected content type for PDF: {normalized_type}")
        return
    if b"\x00" in content:
        raise ValueError("text documents must not contain binary data")
    if normalized_type and normalized_type not in {
        "text/plain", "text/markdown", "text/csv", "application/csv", "application/octet-stream",
        "binary/octet-stream",
    }:
        raise ValueError(f"unsupported content type for a text document: {normalized_type}")
    try:
        content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("text documents must be UTF-8 encoded") from exc


def _append_source(row: dict[str, str]) -> None:
    existing_rows: list[dict[str, str]] = []
    existing_fields: list[str] = []
    if SOURCES.exists():
        with SOURCES.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            existing_fields = reader.fieldnames or []
            existing_rows = list(reader)
    fields = list(dict.fromkeys(FIELDS + existing_fields))
    if existing_fields and existing_fields != fields:
        # Preserve every existing row/column while adding the current provenance schema.
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=SOURCES.parent,
                                             prefix=f"{SOURCES.name}.", suffix=".tmp", delete=False) as handle:
                temp_name = handle.name
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(existing_rows)
            os.replace(temp_name, SOURCES)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
    mode = "a" if SOURCES.exists() and SOURCES.stat().st_size else "w"
    with SOURCES.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if mode == "w":
            writer.writeheader()
        writer.writerow(row)


def register_document(*, title: str, publisher: str, reporting_period: str = "",
                      published_on: str = "", local_path: str | Path | None = None,
                      source_url: str = "", synthetic: bool = False) -> dict[str, str]:
    """Persist a supplied local document or fetch a supplied URL and record provenance."""
    if not isinstance(title, str) or not title.strip() or not isinstance(publisher, str) or not publisher.strip():
        raise ValueError("title and publisher must be supplied")
    if not local_path and not source_url:
        raise ValueError("provide a local_path, a source_url, or both for a locally supplied public document")
    if source_url:
        parsed_url = urlsplit(source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("source_url must be an http(s) public document URL")
    if published_on:
        try:
            published_on = date.fromisoformat(published_on).isoformat()
        except (TypeError, ValueError) as exc:
            raise ValueError("published_on must use YYYY-MM-DD format") from exc

    DATA.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(timezone.utc).isoformat()
    retrieved_at = ""
    media_type = ""
    if local_path:
        source_file = Path(local_path).expanduser().resolve(strict=True)
        if not source_file.is_file():
            raise ValueError("local_path must be a file")
        if source_file.stat().st_size > MAX_DOCUMENT_BYTES:
            raise ValueError(f"document exceeds the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit")
        suffix = _suffix_for_document(str(source_file), "")
        content = source_file.read_bytes()
        _validate_content(content, suffix)
        origin = f"local:{source_file}"
    else:
        parsed_url = urlsplit(source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("source_url must be an http(s) public document URL")
        request = urllib.request.Request(source_url, headers={"User-Agent": "VerifyLayer academic prototype"})
        with urllib.request.urlopen(request, timeout=30) as response:
            media_type = response.headers.get("Content-Type", "")
            suffix = _suffix_for_document(response.geturl(), media_type)
            content = response.read(MAX_DOCUMENT_BYTES + 1)
            if len(content) > MAX_DOCUMENT_BYTES:
                raise ValueError(f"document exceeds the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit")
            source_url = response.geturl()
        _validate_content(content, suffix, media_type)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        origin = f"url:{source_url}"

    digest = hashlib.sha256(content).hexdigest()
    source_id = digest[:16]
    stored = DATA / f"{source_id}{suffix}"
    if not stored.exists():
        stored.write_bytes(content)
    row = {"source_id": source_id, "title": title.strip(), "source_url": source_url, "publisher": publisher.strip(),
           "published_on": published_on, "retrieved_at_utc": retrieved_at,
           "recorded_at_utc": recorded_at, "reporting_period": reporting_period,
           "origin": origin, "stored_path": str(stored.relative_to(ROOT)), "sha256": digest,
           "synthetic": str(bool(synthetic)).lower()}
    _append_source(row)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--period", default="")
    parser.add_argument("--published-on", default="", help="Source publication date in YYYY-MM-DD format, if known")
    parser.add_argument("--local-path")
    parser.add_argument("--url", help="Public source URL; with --local-path, records provenance without a network fetch")
    parser.add_argument("--synthetic", action="store_true", help="Mark a supplied demo document as synthetic")
    args = parser.parse_args()
    print(register_document(title=args.title, publisher=args.publisher, reporting_period=args.period,
                            published_on=args.published_on, local_path=args.local_path, source_url=args.url,
                            synthetic=args.synthetic))


if __name__ == "__main__":
    main()
