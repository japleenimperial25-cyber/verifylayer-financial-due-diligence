"""Source ingestion boundary; concrete network and filing clients are adapters."""

from typing import Protocol

from .models import Document, SourceReference


class SourceConnector(Protocol):
    def fetch(self, reference: SourceReference) -> Document:
        """Fetch an identified source or raise an adapter-specific error."""


def validate_document(document: Document) -> None:
    """Reject incomplete source records before extraction."""
    if not document.reference.source_id.strip():
        raise ValueError("source_id must not be empty")
    if not document.reference.uri.strip():
        raise ValueError("source uri must not be empty")
    if not document.media_type.strip():
        raise ValueError("media_type must not be empty")
    if not document.content:
        raise ValueError("document content must not be empty")
