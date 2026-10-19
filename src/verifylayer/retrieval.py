"""Extraction and retrieval contracts, intentionally independent of an LLM."""

from typing import Protocol, Sequence

from .models import Document, ExtractedPassage


class DocumentExtractor(Protocol):
    def extract(self, document: Document) -> Sequence[ExtractedPassage]:
        """Return passages with source identifiers and available locations."""


class PassageIndex(Protocol):
    def add(self, passages: Sequence[ExtractedPassage]) -> None: ...

    def search(self, query: str, *, limit: int = 5) -> Sequence[ExtractedPassage]: ...


def validate_passages(document: Document, passages: Sequence[ExtractedPassage]) -> None:
    """Ensure extraction output remains traceable to its input source."""
    for passage in passages:
        if passage.source_id != document.reference.source_id:
            raise ValueError("extracted passage source_id does not match document")
        if not passage.text.strip():
            raise ValueError("extracted passage text must not be empty")
        if passage.page is not None and passage.page < 1:
            raise ValueError("page numbers must be positive")
