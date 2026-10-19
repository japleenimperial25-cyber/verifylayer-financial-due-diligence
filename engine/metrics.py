"""Research evaluation metrics calculated from claim-level records."""


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator * 100 if denominator else None


def calculate_metrics(records: list[dict]) -> dict:
    """Count blocked claims in denominator; only unblocked unsupported claims count as output hallucinations."""
    result = {}
    for condition in ("off", "on"):
        claims = [record for record in records if record["condition"] == condition]
        total = len(claims)
        cited = sum(bool(claim.get("citations")) for claim in claims)
        supported = sum(claim["evidence_status"] == "supported" for claim in claims)
        hallucinated_output = sum(claim["evidence_status"] in {"unsupported", "contradicted"} and not claim.get("blocked") for claim in claims)
        blocked = sum(bool(claim.get("blocked")) for claim in claims)
        result[condition] = {
            "total_evaluated_claims": total,
            "hallucinated_output_claims": hallucinated_output,
            "hallucination_rate_percent": _rate(hallucinated_output, total),
            "citation_coverage_percent": _rate(cited, total),
            "claim_support_rate_percent": _rate(supported, total),
            "blocked_claim_count": blocked,
        }
    off, on = result["off"]["hallucination_rate_percent"], result["on"]["hallucination_rate_percent"]
    absolute = off - on if off is not None and on is not None else None
    result["comparison"] = {
        "absolute_reduction_percentage_points": absolute,
        "relative_reduction_percent": (absolute / off * 100) if absolute is not None and off else None,
    }
    return result
