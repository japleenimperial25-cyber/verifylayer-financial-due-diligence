"""Extract searchable text from registered plain-text or PDF documents."""

import csv
import argparse
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parent


def extract_registered(source_id: str) -> list[dict[str, Any]]:
    """Return source-linked paragraphs; PDF page numbers are retained when available."""
    with (ROOT / "sources.csv").open(encoding="utf-8", newline="") as handle:
        source = next((row for row in csv.DictReader(handle) if row["source_id"] == source_id), None)
    if source is None:
        raise KeyError(f"unknown source_id: {source_id}")
    path = ROOT / source["stored_path"]
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF extraction requires `pip install pypdf`") from exc
        pages = [(index + 1, page.extract_text() or "") for index, page in enumerate(PdfReader(path).pages)]
        output = []
        for page_num, text in pages:
            output.extend(_passages(source, text, page_num))
        return output
    if path.suffix.lower() in {".txt", ".md", ".csv"}:
        return _passages(source, path.read_text(encoding="utf-8", errors="replace"), None)
    raise ValueError("supported formats are PDF, TXT, MD, and CSV")


def _passages(source: dict[str, str], text: str, page: int | None) -> list[dict[str, Any]]:
    provenance_fields = ("published_on", "retrieved_at_utc", "recorded_at_utc", "reporting_period", "origin", "stored_path", "sha256", "synthetic")
    provenance = {field: source.get(field, "") for field in provenance_fields}
    return [{"source_id": source["source_id"], "title": source["title"], "source_url": source.get("source_url", ""),
             "publisher": source.get("publisher", ""), **provenance, "page": page, "text": paragraph.strip()}
            for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_id")
    args = parser.parse_args()
    print(json.dumps(extract_registered(args.source_id), indent=2, ensure_ascii=False))
