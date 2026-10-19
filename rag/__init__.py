"""Reproducible, local passage retrieval."""

from extract import extract_registered


def retrieve(question: str, *, source_ids: list[str] | None = None, limit: int = 5) -> list[dict]:
    """Rank extracted paragraphs by lexical overlap; no model or embedding service is used."""
    if not question.strip() or limit < 1:
        return []
    import csv
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    with (root / "sources.csv").open(encoding="utf-8", newline="") as handle:
        sources = list(csv.DictReader(handle))
    if source_ids is not None:
        sources = [source for source in sources if source["source_id"] in source_ids]
    terms = {word.lower() for word in re.findall(r"[a-zA-Z0-9]+", question) if len(word) > 2}
    scored = []
    for source in sources:
        for passage in extract_registered(source["source_id"]):
            words = {word.lower() for word in re.findall(r"[a-zA-Z0-9]+", passage["text"]) if len(word) > 2}
            score = len(terms & words)
            if score:
                scored.append((score, passage))
    return [passage for _, passage in sorted(scored, key=lambda item: (-item[0], item[1]["source_id"], item[1]["page"] or 0))[:limit]]
