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
    fmt = lambda value: "undefined (no evaluated claims)" if value is None else f"{value:.2f}%"
    lines = ["# VerifyLayer evaluation annexure", "", f"**Evaluation label:** {records['label']}",
             f"**Run time (UTC):** {records['created_at_utc']}", "", "## Research question", "",
             "How much does a mandatory citation layer reduce hallucination in financial research output?", "",
             "## Method and scope", "", "This report is generated from the saved question, corpus, outputs, and claim-level records. "
             "A claim is supported only when its text is contained in the cited extracted source span; a numeric mismatch for the same metric is labelled contradicted; other unsupported claims are unsupported. "
             "Blocked claims stay in the denominator. Only unsupported or contradicted claims shown as factual output count as hallucinated output claims.", "",
             "## Results", "", "| Measurement | Verification OFF | Verification ON |", "|---|---:|---:|"]
    for key, label in (("hallucination_rate_percent", "Hallucination rate"), ("citation_coverage_percent", "Citation coverage"),
                       ("claim_support_rate_percent", "Claim support rate"), ("blocked_claim_count", "Blocked claim count"),
                       ("total_evaluated_claims", "Total evaluated claims")):
        a, b = metrics["off"][key], metrics["on"][key]
        lines.append(f"| {label} | {fmt(a) if isinstance(a, float) or a is None else a} | {fmt(b) if isinstance(b, float) or b is None else b} |")
    comparison = metrics["comparison"]
    point_value = comparison["absolute_reduction_percentage_points"]
    point_text = "undefined" if point_value is None else f"{point_value:.2f}"
    lines += ["", f"Absolute reduction: {point_text} percentage points.",
              f"Relative reduction: {fmt(comparison['relative_reduction_percent'])}.", "", "## Claim records", ""]
    for item in records["claim_records"]:
        lines.append(f"- **{item['condition'].upper()} / {item['evidence_status']} / blocked={item['blocked']}**: {item['claim']} Reason: {item['reason']}.")
    lines += ["", "## Source and calculation records", ""]
    for source in records.get("corpus", []):
        origin = source.get("source_url") or "No public URL (synthetic/local demonstration passage)"
        lines.append(f"- **{source['source_id']}: {source['title']}**; publisher: {source.get('publisher') or 'not recorded'}; origin: {origin}; page: {source.get('page') or 'not available'}.")
        lines.append(f"  - Extracted evidence: {source['text']}")
    calculations = records.get("calculation_records", [])
    if calculations:
        for calculation in calculations:
            lines.append(f"- **{calculation['name']}** = {calculation['value']} {calculation['unit']}; inputs: {calculation['inputs']}.")
    else:
        lines.append("No financial calculation was invoked for this claim-blocking demonstration; the calculation engine is available separately.")
    lines += ["", "## Limitations", "", "A synthetic, controlled example demonstrates the gate and does not establish real-world LLM hallucination reduction. "
              "No public financial filing was included in this run. The lexical retrieval and exact-span checks are conservative prototype rules, not semantic entailment.", ""]
    destination = Path(output_path) if output_path else ROOT / "data" / "evaluation_report.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


if __name__ == "__main__":
    print(generate_report())
