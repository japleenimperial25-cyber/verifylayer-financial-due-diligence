# VerifyLayer evaluation annexure

**Evaluation label:** SYNTHETIC CONTROLLED DEMONSTRATION - NOT EMPIRICAL RESEARCH
**Run time (UTC):** 2026-10-19T07:12:08.453217+00:00

## Research question

How much does a mandatory citation layer reduce hallucination in financial research output?

## Method and scope

This report is generated from the saved question, corpus, outputs, and claim-level records. A claim is supported only when its text is contained in the cited extracted source span; a numeric mismatch for the same metric is labelled contradicted; other unsupported claims are unsupported. Blocked claims stay in the denominator. Only unsupported or contradicted claims shown as factual output count as hallucinated output claims.

## Results

| Measurement | Verification OFF | Verification ON |
|---|---:|---:|
| Hallucination rate | 50.00% | 0.00% |
| Citation coverage | 50.00% | 50.00% |
| Claim support rate | 50.00% | 50.00% |
| Blocked claim count | 0 | 1 |
| Total evaluated claims | 2 | 2 |

Absolute reduction: 50.00 percentage points.
Relative reduction: 100.00%.

## Claim records

- **OFF / supported / blocked=False**: Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025. Reason: claim text is contained in the cited extracted span.
- **OFF / contradicted / blocked=False**: Synthetic demo company Alpha reported revenue of INR 999 crore for FY2025. Reason: retrieved passage reports a different numeric value for the same metric.
- **ON / supported / blocked=False**: Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025. Reason: claim text is contained in the cited extracted span.
- **ON / contradicted / blocked=True**: Synthetic demo company Alpha reported revenue of INR 999 crore for FY2025. Reason: retrieved passage reports a different numeric value for the same metric.

## Source and calculation records

- **synthetic-demo: Synthetic demonstration passage**; publisher: Synthetic example (not a real publisher); origin: No public URL (synthetic/local demonstration passage); page: not available.
  - Extracted evidence: Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025.
No financial calculation was invoked for this claim-blocking demonstration; the calculation engine is available separately.

## Limitations

A synthetic, controlled example demonstrates the gate and does not establish real-world LLM hallucination reduction. No public financial filing was included in this run. The lexical retrieval and exact-span checks are conservative prototype rules, not semantic entailment.
