# VerifyLayer evaluation annexure

**Evaluation label:** SYNTHETIC CONTROLLED DEMONSTRATION - NOT EMPIRICAL RESEARCH
**Run time (UTC):** 2026-10-19T07:12:08.453217+00:00

## Research question

How much does a mandatory citation layer reduce hallucination in financial research output?

## Method and scope

This report is generated from the saved question, corpus, outputs, and claim-level records. A claim is supported only when its text is contained in the cited extracted source span; a numeric mismatch for the same metric is labelled contradicted; other unsupported claims are unsupported. Blocked claims stay in the denominator. Only unsupported or contradicted claims shown as factual output count as hallucinated output claims.

## Results

Rates are rounded to two decimal places for display; engine inputs and Decimal calculation outputs are not rounded.

| Measurement | Verification OFF | Verification ON |
|---|---:|---:|
| Hallucinated factual outputs (raw count) | 1 | 0 |
| Proposed factual claims (denominator) | 2 | 2 |
| Claims with citations (raw count) | 1 | 1 |
| Supported claims (raw count) | 1 | 1 |
| Unsupported claims (raw count) | 0 | 0 |
| Contradicted claims (raw count) | 1 | 1 |
| Hallucination rate | 50.00% | 0.00% |
| Citation coverage | 50.00% | 50.00% |
| Claim support rate | 50.00% | 50.00% |
| Blocked claim count | 0 | 1 |

Absolute reduction: 50.00 percentage points.
Relative reduction: 100.00%.

## Claim records

- **OFF / supported / blocked=False**: Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025. Reason: claim text is contained in the cited extracted span. Evidence: source_id=synthetic-demo; quote=Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025..
- **OFF / contradicted / blocked=False**: Synthetic demo company Alpha reported revenue of INR 999 crore for FY2025. Reason: retrieved passage reports a different numeric value for the same metric. Evidence: no citation attached.
- **ON / supported / blocked=False**: Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025. Reason: claim text is contained in the cited extracted span. Evidence: source_id=synthetic-demo; quote=Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025..
- **ON / contradicted / blocked=True**: Synthetic demo company Alpha reported revenue of INR 999 crore for FY2025. Reason: retrieved passage reports a different numeric value for the same metric. Evidence: no citation attached.

## Source and calculation records

Source dates and URLs below are taken from the saved passage/provenance records; missing values remain explicitly unrecorded.

- **synthetic-demo: Synthetic demonstration passage**; publisher: Synthetic example (not a real publisher); published: not recorded; retrieved UTC: not recorded; origin: No public URL (synthetic/local demonstration passage); synthetic: yes; page: not available.
  - Extracted evidence: Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025.
No financial calculation was invoked for this claim-blocking demonstration; the calculation engine is available separately.

## Assumptions, limitations, and intended use

Synthetic data is included in this evaluation; these results do not establish real-world LLM hallucination reduction. Synthetic and authentic financial values must be interpreted separately.
The lexical retrieval and exact-span checks are conservative prototype rules, not semantic entailment. No live language model is connected, and the system does not provide investment advice or buy, sell, or hold recommendations. Financial formulas, input requirements, units, period handling, and rounding assumptions are documented in governance.md. A human reviewer must verify original filings, context, consolidated/standalone basis, restatements, and reported units before using any result.

## Regulatory scope

This educational prototype makes no claim of registration, legal compliance, or regulatory status. The SEBI Investment Advisers Regulations are available from the [official SEBI regulations page](https://www.sebi.gov.in/legal/regulations/nov-2025/securities-and-exchange-board-of-india-investment-advisers-regulations-2013-and-securities-last-amended-on-november-25-2025-_98246.html). This reference is not a legal determination of applicability to any person or activity.
