"""Shared data contracts. These models contain no bundled financial data."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class SourceReference:
    source_id: str
    uri: str
    publisher: str | None = None
    published_on: date | None = None


@dataclass(frozen=True)
class Document:
    reference: SourceReference
    media_type: str
    content: bytes


@dataclass(frozen=True)
class ExtractedPassage:
    source_id: str
    text: str
    page: int | None = None
    locator: str | None = None


@dataclass(frozen=True)
class FinancialValue:
    value: Decimal
    unit: str
    period: str | None = None


@dataclass(frozen=True)
class Claim:
    text: str
    cited_source_id: str
    cited_passage: str


@dataclass(frozen=True)
class CitationResult:
    verified: bool
    reason: str
