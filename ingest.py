"""Register local financial documents or explicitly fetch a supplied public URL."""

import argparse
import csv
import hashlib
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SOURCES = ROOT / "sources.csv"
FIELDS = ["source_id", "title", "source_url", "publisher", "retrieved_at_utc", "recorded_at_utc", "reporting_period", "origin", "stored_path", "sha256", "synthetic"]


def register_document(*, title: str, publisher: str, reporting_period: str = "", local_path: str | Path | None = None, source_url: str = "", synthetic: bool = False) -> dict[str, str]:
    """Persist a supplied local document or fetch a supplied URL and record provenance."""
    if not title.strip() or not publisher.strip():
        raise ValueError("title and publisher must be supplied")
    if bool(local_path) == bool(source_url):
        raise ValueError("provide exactly one of local_path or source_url")
    DATA.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(timezone.utc).isoformat()
    retrieved_at = ""
    if local_path:
        source_file = Path(local_path).expanduser().resolve(strict=True)
        if not source_file.is_file():
            raise ValueError("local_path must be a file")
        content = source_file.read_bytes()
        origin = f"local:{source_file}"
    else:
        parsed_url = urlsplit(source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("source_url must be an http(s) public document URL")
        request = urllib.request.Request(source_url, headers={"User-Agent": "VerifyLayer academic prototype"})
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
            final_url = response.geturl()
        source_url = final_url
        retrieved_at = datetime.now(timezone.utc).isoformat()
        origin = f"url:{source_url}"
    if not content:
        raise ValueError("document is empty")
    digest = hashlib.sha256(content).hexdigest()
    source_id = digest[:16]
    suffix = Path(source_url.split("?")[0]).suffix if source_url else Path(local_path).suffix
    suffix = suffix if suffix and len(suffix) < 12 else ".bin"
    stored = DATA / f"{source_id}{suffix}"
    if not stored.exists():
        stored.write_bytes(content)
    row = {"source_id": source_id, "title": title, "source_url": source_url, "publisher": publisher,
           "retrieved_at_utc": retrieved_at, "recorded_at_utc": recorded_at, "reporting_period": reporting_period,
           "origin": origin, "stored_path": str(stored.relative_to(ROOT)), "sha256": digest,
           "synthetic": str(bool(synthetic)).lower()}
    exists = SOURCES.exists()
    with SOURCES.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--period", default="")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--local-path")
    source.add_argument("--url")
    parser.add_argument("--synthetic", action="store_true", help="Mark a supplied demo document as synthetic")
    args = parser.parse_args()
    print(register_document(title=args.title, publisher=args.publisher, reporting_period=args.period,
                            local_path=args.local_path, source_url=args.url, synthetic=args.synthetic))


if __name__ == "__main__":
    main()
