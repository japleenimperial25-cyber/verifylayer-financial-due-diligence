"""Conservative citation checks against extracted source passages."""

from collections.abc import Sequence

from .models import CitationResult, Claim, ExtractedPassage


def verify_citation(claim: Claim, passages: Sequence[ExtractedPassage]) -> CitationResult:
    """Check citation identity and quoted passage presence; this is not semantic proof."""
    matching_source = [p for p in passages if p.source_id == claim.cited_source_id]
    if not matching_source:
        return CitationResult(False, "cited source is absent from retrieved passages")
    quote = claim.cited_passage.strip()
    if not quote:
        return CitationResult(False, "cited passage is empty")
    if not any(quote in passage.text for passage in matching_source):
        return CitationResult(False, "cited passage does not match extracted text")
    return CitationResult(True, "citation text matches an extracted passage; claim meaning remains unassessed")
