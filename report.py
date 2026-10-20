"""Generate a Markdown annexure from actual saved evaluation records."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def generate_report(record_path: str | Path | None = None, output_path: str | Path | None = None) -> Path:
    source = Path(record_path) if record_path else ROOT / "data" / "evaluation_records.json"
    if not source.exists():
        raise FileNotFoundError("No evaluation records found. Run the experiment in the app first.")
    records = json.loads(source.read_text(encoding="utf-8"))
    metrics = records["metrics"]
    for condition in ("off", "on"):
        claims = [item for item in records.get("claim_records", []) if item.get("condition") == condition]
        metrics[condition].setdefault("cited_claim_count", sum(bool(item.get("citations")) for item in claims))
        metrics[condition].setdefault("supported_claim_count", sum(item.get("evidence_status") == "supported" for item in claims))
        metrics[condition].setdefault("unsupported_claim_count", sum(item.get("evidence_status") == "unsupported" for item in claims))
        metrics[condition].setdefault("contradicted_claim_count", sum(item.get("evidence_status") == "contradicted" for item in claims))
    fmt = lambda value: "undefined (no denominator)" if value is None else f"{value:.2f}%"
    lines = ["# VerifyLayer evaluation annexure", "", f"**Evaluation label:** {records['label']}",
             f"**Run time (UTC):** {records['created_at_utc']}", "", "## Research question", "",
             "How much does a mandatory citation layer reduce hallucination in financial research output?", "",
             "## Method and scope", "", "This report is generated from the saved question, corpus, outputs, and claim-level records. "
             "A claim is supported only when its text is contained in the cited extracted source span; a numeric mismatch for the same metric is labelled contradicted; other unsupported claims are unsupported. "
             "Blocked claims stay in the denominator. Only unsupported or contradicted claims shown as factual output count as hallucinated output claims.", "",
             "## Results", "", "Rates are rounded to two decimal places for display; engine inputs and Decimal calculation outputs are not rounded.", "",
             "| Measurement | Verification OFF | Verification ON |", "|---|---:|---:|"]
    for key, label in (("hallucinated_output_claims", "Hallucinated factual outputs (raw count)"),
                       ("total_evaluated_claims", "Proposed factual claims (denominator)"),
                       ("cited_claim_count", "Claims with citations (raw count)"),
                       ("supported_claim_count", "Supported claims (raw count)"),
                       ("unsupported_claim_count", "Unsupported claims (raw count)"),
                       ("contradicted_claim_count", "Contradicted claims (raw count)"),
                       ("hallucination_rate_percent", "Hallucination rate"),
                       ("citation_coverage_percent", "Citation coverage"),
                       ("claim_support_rate_percent", "Claim support rate"), ("blocked_claim_count", "Blocked claim count"),
                       ):
        a, b = metrics["off"][key], metrics["on"][key]
        lines.append(f"| {label} | {fmt(a) if isinstance(a, float) or a is None else a} | {fmt(b) if isinstance(b, float) or b is None else b} |")
    comparison = metrics["comparison"]
    point_value = comparison["absolute_reduction_percentage_points"]
    point_text = "undefined" if point_value is None else f"{point_value:.2f}"
    lines += ["", f"Absolute reduction: {point_text} percentage points.",
              f"Relative reduction: {fmt(comparison['relative_reduction_percent'])}.", "", "## Claim records", ""]
    for item in records["claim_records"]:
        citations = item.get("citations") or []
        citation_text = "; ".join(f"source_id={citation.get('source_id')}; quote={citation.get('quote')}"
                                   for citation in citations) or "no citation attached"
        lines.append(f"- **{item['condition'].upper()} / {item['evidence_status']} / blocked={item['blocked']}**: "
                     f"{item['claim']} Reason: {item['reason']}. Evidence: {citation_text}.")
    lines += ["", "## Source and calculation records", "",
              "Source dates and URLs below are taken from the saved passage/provenance records; missing values remain explicitly unrecorded.", ""]
    for source in records.get("corpus", []):
        origin = source.get("source_url") or "No public URL (synthetic/local demonstration passage)"
        lines.append(f"- **{source['source_id']}: {source['title']}**; publisher: {source.get('publisher') or 'not recorded'}; "
                     f"published: {source.get('published_on') or 'not recorded'}; retrieved UTC: {source.get('retrieved_at_utc') or 'not recorded'}; "
                     f"origin: {origin}; synthetic: {source.get('synthetic') or ('yes' if source.get('source_id') == 'synthetic-demo' else 'not recorded')}; "
                     f"page: {source.get('page') or 'not available'}.")
        lines.append(f"  - Extracted evidence: {source['text']}")
    calculations = records.get("calculation_records", [])
    if calculations:
        for calculation in calculations:
            formula = {"sum": "sum = Σ sourced inputs", "percentage_change": "((current − prior) / prior) × 100"}.get(
                calculation["name"], "formula not documented")
            lines.append(f"- **{calculation['name']}** = {calculation['value']} {calculation['unit']}; "
                         f"formula: {formula}; inputs: {calculation['inputs']}.")
    else:
        lines.append("No financial calculation was invoked for this claim-blocking demonstration; the calculation engine is available separately.")
    label = str(records.get("label", ""))
    synthetic = "SYNTHETIC" in label or any(
        str(item.get("synthetic", "")).lower() == "true" or item.get("source_id") == "synthetic-demo"
        for item in records.get("corpus", [])
    )
    limitation = ("Synthetic data is included in this evaluation; these results do not establish real-world LLM hallucination reduction. "
                  "Synthetic and authentic financial values must be interpreted separately." if synthetic else
                  "This is a deterministic local-corpus rule evaluation, not an empirical LLM hallucination study.")
    lines += ["", "## Assumptions, limitations, and intended use", "", limitation,
              "The lexical retrieval and exact-span checks are conservative prototype rules, not semantic entailment. "
              "No live language model is connected, and the system does not provide investment advice or buy, sell, or hold recommendations. "
              "Financial formulas, input requirements, units, period handling, and rounding assumptions are documented in governance.md. "
              "A human reviewer must verify original filings, context, consolidated/standalone basis, restatements, and reported units before using any result.",
              "", "## Regulatory scope", "", "This educational prototype makes no claim of registration, legal compliance, or regulatory status. "
              "The SEBI Investment Advisers Regulations are available from the [official SEBI regulations page](https://www.sebi.gov.in/legal/regulations/nov-2025/securities-and-exchange-board-of-india-investment-advisers-regulations-2013-and-securities-last-amended-on-november-25-2025-_98246.html). "
              "This reference is not a legal determination of applicability to any person or activity.", ""]
    destination = Path(output_path) if output_path else ROOT / "data" / "evaluation_report.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


if __name__ == "__main__":
    print(generate_report())
