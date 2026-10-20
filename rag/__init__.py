"""Reproducible, local passage retrieval."""

from extract import extract_registered
from pathlib import Path

import re

ROOT = Path(__file__).resolve().parents[1]

_STOP_WORDS = {
    "what", "which", "when", "where", "who", "whom", "whose", "how", "why", "is", "was", "were", "are",
    "the", "a", "an", "of", "for", "to", "in", "on", "at", "by", "from", "with", "and", "or", "about",
    "company", "companies", "financial", "finance", "show", "tell", "me", "give", "summarize", "summary",
    "compare", "between", "over", "during", "did", "does", "do", "has", "have", "had", "its", "their",
    "revenue", "sales", "growth", "profit", "loss", "eps", "ebitda", "ebit", "margin", "margins", "balance",
    "sheet", "cash", "flow", "debt", "liquidity", "working", "capital", "assets", "liabilities", "ratio", "ratios",
    "year", "year-on-year", "yoy", "historical", "performance", "trend", "trends", "segment", "segments", "geographic",
    "industry", "peer", "peers", "competitor", "competitors", "management", "ownership", "governance", "risk", "risks",
    "forecast", "forecasting", "assumption", "assumptions", "dcf", "wacc", "sensitivity", "scenario", "analysis",
    "explain", "explanation", "document", "documents", "report", "reports", "annual", "quarterly", "result", "results",
    "fiscal", "fy", "q1", "q2", "q3", "q4", "inr", "usd", "eur", "gbp", "crore", "crores", "million", "billion",
    "happened", "increased", "increase", "decreased", "decrease", "declined", "decline", "grown", "grew", "down", "up",
    "latest", "current", "previous", "prior", "reported", "reporting", "available", "all", "every", "each",
}
_METRIC_TERMS = {
    "revenue": ("revenue", "sales", "turnover"), "growth": ("growth", "yoy", "year-on-year"),
    "profit": ("profit", "loss", "net income", "pat"), "eps": ("eps", "earnings per share"),
    "ebitda": ("ebitda",), "ebit": ("ebit",), "margin": ("margin", "margins"),
    "balance_sheet": ("balance sheet",), "cash_flow": ("cash flow", "cash flows"),
    "debt": ("debt",), "liquidity": ("liquidity",), "working_capital": ("working capital",),
    "assets": ("assets",), "liabilities": ("liabilities",), "valuation": ("valuation", "dcf", "wacc"),
    "equity": ("equity", "shareholders equity", "shareholders' equity"),
    "leverage": ("leverage", "debt-to-equity", "gearing"),
    "current_ratio": ("current ratio",), "quick_ratio": ("quick ratio",),
    "segment": ("segment", "segments"), "governance": ("governance", "management", "ownership"),
}
_PERIOD_RE = re.compile(r"\b(?:Q[1-4]\s?FY\s?\d{2,4}(?:[-–/]\d{2,4})?|FY\s?\d{2,4}(?:[-–/]\d{2,4})?|\d{4}[-–/]\d{2,4}|\d{4})\b", re.I)
_UNIT_TERMS = ("INR", "₹", "USD", "$", "EUR", "GBP", "crore", "crores", "lakh", "million", "billion", "thousand", "share", "shares", "%")
_META_GENERIC = {"annual", "report", "reports", "limited", "ltd", "industries", "industry", "company", "plc", "inc", "corporation", "corp", "financial", "results", "investor", "presentation", "quarterly"}
_FINANCIAL_SECTION_HEADINGS = (
    "financial results", "financial highlights", "statement of profit and loss",
    "consolidated statement of profit and loss", "statement of profit or loss",
    "consolidated statement of profit or loss", "income statement",
)


def _alias_in_text(alias: str, text: str) -> bool:
    parts = re.findall(r"[a-zA-Z0-9]+", alias.lower())
    if not parts:
        return False
    pattern = r"\b" + r"[\s-]+".join(re.escape(part) for part in parts) + r"\b"
    return re.search(pattern, text, re.I) is not None


def analyze_question(question: str) -> dict:
    """Extract transparent query context; this is a heuristic, not entity recognition by an LLM."""
    cleaned = re.sub(r"['’]s\b", "", question)
    words = re.findall(r"[A-Za-z][A-Za-z&.-]*", cleaned)
    entities = []
    current = []
    for original in words:
        if original[:1].isupper() and original.lower() not in _STOP_WORDS and original.lower() not in {"q", "fy"}:
            current.append(original.lower())
        elif current:
            entities.append(" ".join(current))
            current = []
    if current:
        entities.append(" ".join(current))
    entity = next((item for item in entities if item not in {"fy", "q1", "q2", "q3", "q4"}), None)
    if entity is None:
        for match in re.finditer(r"\b(?:for|of|about|regarding|from)\s+([a-z][a-z&.-]*(?:\s+[a-z][a-z&.-]*){0,3})", cleaned, re.I):
            candidate_words = []
            for word in match.group(1).lower().split():
                if word in _STOP_WORDS:
                    break
                candidate_words.append(word)
            if candidate_words:
                entity = " ".join(candidate_words)
                break
    if entity is None:
        metric_words = {word for aliases in _METRIC_TERMS.values() for alias in aliases
                        for word in re.findall(r"[a-zA-Z0-9]+", alias.lower()) if len(word) > 2}
        residual = [word.lower() for word in re.findall(r"[a-zA-Z][a-zA-Z&.-]*", cleaned)
                    if word.lower() not in _STOP_WORDS and word.lower() not in metric_words]
        if residual:
            entity = " ".join(residual)
    metrics = [name for name, aliases in _METRIC_TERMS.items() if any(_alias_in_text(alias, question) for alias in aliases)]
    periods = _PERIOD_RE.findall(question)
    units = [unit for unit in _UNIT_TERMS if unit.lower() in question.lower()]
    return {"company_or_entity": entity, "metrics": metrics, "periods": periods, "units": units}


def _source_identity(source: dict) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9]+", f"{source.get('publisher', '')} {source.get('title', '')}".lower())
    return {word for word in words if len(word) > 2 and word not in _META_GENERIC}


def _matches_entity(entity: str, source: dict) -> bool:
    identity = _source_identity(source)
    entity_words = [word for word in re.findall(r"[a-zA-Z0-9]+", entity.lower()) if len(word) > 2 and word not in _META_GENERIC]
    return bool(entity_words) and all(any(meta == word or (len(word) >= 5 and meta.startswith(word)) or (len(meta) >= 5 and word.startswith(meta)) for meta in identity) for word in entity_words)


def ambiguous_entity_publishers(question: str, *, source_ids: list[str] | None = None) -> list[str]:
    """Return distinct matching publishers when a short entity name maps to multiple issuers."""
    entity = analyze_question(question)["company_or_entity"]
    entity_words = [word for word in re.findall(r"[a-zA-Z0-9]+", entity or "") if len(word) > 2 and word not in _META_GENERIC]
    if len(entity_words) != 1:
        return []
    import csv
    with (ROOT / "sources.csv").open(encoding="utf-8", newline="") as handle:
        sources = list(csv.DictReader(handle))
    sources = [source for source in sources if str(source.get("synthetic", "")).lower() != "true" and source.get("source_id") != "synthetic-demo"]
    if source_ids is not None:
        sources = [source for source in sources if source.get("source_id") in source_ids]
    matches = [source for source in sources if _matches_entity(entity, source)]
    publishers = {source.get("publisher", "").strip() for source in matches if source.get("publisher", "").strip()}
    return sorted(publishers) if len(publishers) > 1 else []


def _matches_period(periods: list[str], source: dict, passage: dict) -> bool:
    if not periods:
        return True
    context = re.sub(r"[^a-z0-9]", "", f"{source.get('reporting_period', '')} {passage.get('text', '')}".lower())
    return any(re.sub(r"[^a-z0-9]", "", period.lower()) in context for period in periods)


def _matches_units(units: list[str], passage: dict) -> bool:
    if not units:
        return True
    text = passage.get("text", "").lower()
    tokens = set(re.findall(r"[a-zA-Z]+", text))
    aliases = {"₹": {"inr", "₹"}, "inr": {"inr", "₹"}, "$": {"usd", "$"}, "usd": {"usd", "$"},
               "%": {"%", "percent", "percentage"}}
    for unit in units:
        wanted = aliases.get(unit.lower(), {unit.lower()})
        if not any(symbol in text if symbol in {"₹", "$", "%"} else
                   any(token == symbol or token.startswith(symbol) for token in tokens) for symbol in wanted):
            return False
    return True


def retrieve(question: str, *, source_ids: list[str] | None = None, limit: int = 5) -> list[dict]:
    """Rank extracted paragraphs by lexical overlap; no model or embedding service is used."""
    if not question.strip() or limit < 1:
        return []
    import csv
    with (ROOT / "sources.csv").open(encoding="utf-8", newline="") as handle:
        sources = list(csv.DictReader(handle))
    sources = [source for source in sources if str(source.get("synthetic", "")).lower() != "true" and source.get("source_id") != "synthetic-demo"]
    if source_ids is not None:
        sources = [source for source in sources if source["source_id"] in source_ids]
    context = analyze_question(question)
    entity = context["company_or_entity"]
    if entity:
        sources = [source for source in sources if _matches_entity(entity, source)]
    elif source_ids is None and sources:
        # When capitalization did not identify a name, constrain retrieval to sources
        # whose distinctive metadata words are actually present in the query.
        terms_for_identity = {word for word in re.findall(r"[a-zA-Z0-9]+", question.lower()) if len(word) > 2}
        possible = [source for source in sources if _source_identity(source) & terms_for_identity]
        if possible:
            sources = possible
    # Periods and generic request language should filter/shape retrieval, not
    # contribute the same ranking weight as distinctive evidence terms.
    period_tokens = {word.lower() for period in context["periods"]
                     for word in re.findall(r"[a-zA-Z0-9]+", period)}
    terms = {word.lower() for word in re.findall(r"[a-zA-Z0-9]+", question)
             if len(word) > 2 and word.lower() not in _STOP_WORDS and word.lower() not in period_tokens}
    requested_metrics = context["metrics"]
    scored = []
    for source in sources:
        for passage in extract_registered(source["source_id"]):
            if not _matches_period(context["periods"], source, passage) or not _matches_units(context["units"], passage):
                continue
            words = {word.lower() for word in re.findall(r"[a-zA-Z0-9]+", passage["text"]) if len(word) > 2}
            if requested_metrics:
                metric_aliases = [alias for metric in requested_metrics for alias in _METRIC_TERMS[metric]]
                if not any(_alias_in_text(alias, passage["text"]) for alias in metric_aliases):
                    continue
            score = len(terms & words)
            # Annual reports often place a financial table under a heading
            # on the same extracted page passage. Prefer those contexts over
            # broad narrative passages that happen to repeat the metric.
            if requested_metrics:
                aliases = [alias for metric in requested_metrics for alias in _METRIC_TERMS[metric]]
                score += 3 * max((len(alias.split()) for alias in aliases
                                  if _alias_in_text(alias, passage["text"])), default=0)
                if any(_alias_in_text(heading, passage["text"])
                       for heading in _FINANCIAL_SECTION_HEADINGS):
                    score += 8
            if score:
                scored.append((score, passage))
    return [passage for _, passage in sorted(scored, key=lambda item: (-item[0], item[1]["source_id"], item[1]["page"] or 0))[:limit]]
