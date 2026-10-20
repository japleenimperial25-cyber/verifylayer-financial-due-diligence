import csv
import io
from datetime import datetime, timezone
from urllib.error import URLError

import pytest

import ingest


def _configure(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "ROOT", tmp_path)
    monkeypatch.setattr(ingest, "DATA", tmp_path / "data")
    monkeypatch.setattr(ingest, "SOURCES", tmp_path / "sources.csv")


def test_local_source_records_publication_date_hash_and_actual_empty_retrieval(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    source = tmp_path / "annual-report.txt"
    source.write_text("Revenue was reported as INR 12 crore.", encoding="utf-8")
    row = ingest.register_document(title="Annual report", publisher="Issuer IR", published_on="2025-08-06",
                                   reporting_period="FY2025", local_path=source)
    assert row["published_on"] == "2025-08-06"
    assert row["retrieved_at_utc"] == ""
    assert row["source_url"] == ""
    assert row["sha256"]
    assert (tmp_path / row["stored_path"]).read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    with (tmp_path / "sources.csv").open(encoding="utf-8", newline="") as handle:
        persisted = next(csv.DictReader(handle))
    assert persisted["published_on"] == "2025-08-06"
    assert persisted["origin"].startswith("local:")


def test_offline_local_document_can_retain_its_verified_public_url(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    source = tmp_path / "issuer-filing.txt"
    source.write_text("Audited issuer disclosure.", encoding="utf-8")
    row = ingest.register_document(title="Issuer filing", publisher="Issuer Limited", local_path=source,
                                   source_url="https://issuer.example/filings/annual-report.pdf")
    assert row["source_url"] == "https://issuer.example/filings/annual-report.pdf"
    assert row["retrieved_at_utc"] == ""
    assert row["origin"].startswith("local:")


def test_ingestion_rejects_wrong_type_empty_and_invalid_publication_date(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    wrong_pdf = tmp_path / "filing.pdf"
    wrong_pdf.write_bytes(b"<html>not a PDF</html>")
    with pytest.raises(ValueError, match="not a PDF"):
        ingest.register_document(title="Wrong content", publisher="Issuer", local_path=wrong_pdf)
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        ingest.register_document(title="Empty", publisher="Issuer", local_path=empty)
    good = tmp_path / "document.txt"
    good.write_text("A real supplied passage.", encoding="utf-8")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        ingest.register_document(title="Document", publisher="Issuer", published_on="06/08/2025", local_path=good)
    assert not (tmp_path / "sources.csv").exists()


def test_failed_download_is_not_recorded_as_success(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)

    def fail(*_args, **_kwargs):
        raise URLError("offline")

    monkeypatch.setattr(ingest.urllib.request, "urlopen", fail)
    with pytest.raises(URLError):
        ingest.register_document(title="Report", publisher="Issuer", source_url="https://issuer.example/report.pdf")
    assert not (tmp_path / "sources.csv").exists()
    assert list((tmp_path / "data").iterdir()) == []


def test_download_checks_content_type_signature_and_records_retrieval(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)

    class Response(io.BytesIO):
        headers = {"Content-Type": "application/pdf"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

        def geturl(self):
            return "https://issuer.example/reports/annual.pdf"

    monkeypatch.setattr(ingest.urllib.request, "urlopen", lambda *_args, **_kwargs: Response(b"%PDF-1.4\nreport"))
    before = datetime.now(timezone.utc)
    row = ingest.register_document(title="Issuer annual report", publisher="Issuer Limited",
                                   published_on="2025-08-06", reporting_period="FY2025",
                                   source_url="https://issuer.example/report.pdf")
    retrieved = datetime.fromisoformat(row["retrieved_at_utc"])
    assert before <= retrieved <= datetime.now(timezone.utc)
    assert row["source_url"].endswith("annual.pdf")
    assert row["stored_path"].endswith(".pdf")


def test_old_registry_is_migrated_without_losing_existing_rows(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    registry = tmp_path / "sources.csv"
    registry.write_text(
        "source_id,title,source_url,publisher,retrieved_at_utc,recorded_at_utc,reporting_period,origin,stored_path,sha256,synthetic\n"
        "old-id,Old source,https://issuer.example/old.pdf,Issuer,2025-01-01T00:00:00+00:00,,FY2024,url,old.pdf,abc,false\n",
        encoding="utf-8",
    )
    document = tmp_path / "new.txt"
    document.write_text("New supplied material.", encoding="utf-8")
    ingest.register_document(title="New source", publisher="Issuer", local_path=document)
    with registry.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert "published_on" in reader.fieldnames
    old = next(row for row in rows if row["source_id"] == "old-id")
    assert old["title"] == "Old source"
    assert old["publisher"] == "Issuer"
    assert old["published_on"] == ""
