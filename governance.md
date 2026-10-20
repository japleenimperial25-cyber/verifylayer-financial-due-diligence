# VerifyLayer governance and assumptions

## Intended use

VerifyLayer is an academic software prototype for examining citation-grounded verification. It is not investment research, financial advice, or a recommendation to buy, sell, or hold any security. Users must independently verify source filings and calculations.

## Evidence and verification

- A document is recorded only after a URL fetch succeeds or a local file is explicitly registered. The registry stores its supplied title, publisher, verified source URL when known, publication date when supplied, actual UTC retrieval time for successful URL fetches, recording time, reporting period, origin, local path, synthetic marker, and SHA-256 digest. A locally supplied file may carry its public source URL, but its retrieval timestamp remains blank because VerifyLayer did not fetch it. Files are limited to 50 MB and validated against the supported PDF/TXT/Markdown/CSV types before they are registered. Failed or invalid inputs are not recorded.
- Plain text, Markdown, CSV, and PDF are supported; PDF page references come from extracted page boundaries. OCR, table reconstruction, semantic entailment, and dynamic web discovery are not implemented.
- Retrieval is deterministic lexical overlap over extracted paragraphs. It may miss relevant passages or return irrelevant ones.
- When the optional server-side model is configured, it receives only retrieved passages and proposes verbatim claims and sourced calculation inputs. Free-form model prose is discarded. Claim text must pass the existing exact-span verifier; calculation inputs must match source ID, quote, metric, numeric value, period, and unit before Python computes a result. Model output selection is not independent semantic verification and can miss relevant evidence.
- A claim is supported only if the full claim text occurs in its cited extracted span. Numeric disagreements for a shared metric are flagged as contradicted by a simple lexical rule. Other claims without direct support are unsupported. This is not a complete contradiction detector.
- With verification ON, every unsupported or contradicted claim is withheld and its reason retained. Citations alone do not establish support.

## Calculations and evaluation

Financial arithmetic runs in plain Python with `Decimal`; a language model never performs arithmetic. The optional model is not configured in the current repository/deployment. Available operations are deliberately limited to sourced summation, percentage change, margin, and same-period ratios.

- **Summation:** `S = Σ xᵢ`. Every input must have a finite decimal value, a non-empty source ID, an exact evidence quote, a declared reporting period, and the same unit and period as the other inputs. Example: `125.50 INR crore + 24.50 INR crore = 150.00 INR crore` for FY2025. Hand-worked independently: 125 crore + 24 crore = 149 crore, plus 0.50 crore = 149.50; adding 0.50 crore to 149.50 gives 150.00.
- **Percentage change:** `((current − prior) / prior) × 100`. Both inputs must carry source IDs, evidence quotes, units, and distinct reporting periods; units must match exactly. Example: `(125 − 100) / 100 × 100 = 25.00%`. A zero prior value is undefined and raises an error. Negative values are allowed and use the same signed formula; when the prior value is negative, the result is a mathematical percentage change and must not be interpreted as ordinary growth without analyst context.
- **Margin:** `(sourced numerator / sourced denominator) × 100`. Inputs must share the same unit and reporting period and the denominator cannot be zero.
- **Ratio:** `sourced numerator / sourced denominator`. Inputs must share the same unit and reporting period and the denominator cannot be zero. The output unit is `x`.
- **Generated calculations:** Revenue/profit growth and EPS changes use percentage change; requested margins and comparable liquidity/leverage ratios use the corresponding formulas only when the model can provide individually traceable inputs. The metric labels and value-to-quote association are checked conservatively; ambiguous table extraction is rejected.
- **Units and periods:** no unit conversion, currency conversion, annualisation, or period alignment is performed. Inputs with mismatched units or periods are rejected. Negative inputs are retained because losses, net liabilities, and cash outflows can be negative.
- **Precision and rounding:** input strings are parsed as `Decimal`. Calculation operations use a local 34-significant-digit context with `ROUND_HALF_EVEN`; no currency quantisation is applied. Division may therefore round repeating decimals at that context precision. Evaluation rates in the report are formatted to two decimal places for display only. The original values and input evidence remain in the calculation record.
- **Traceability and limitations:** calculation outputs retain their full input mappings, including source ID and quoted evidence. A source ID and quote preserve the declared provenance but do not independently prove the quote was extracted correctly; the original filing and extraction location must be reviewed.

Evaluation claim records preserve both OFF and ON proposals. The denominator includes all proposed factual claims, including blocked claims. Hallucinated output claims are unsupported or contradicted claims that were shown as facts; blocked proposals remain counted in the denominator and are not treated as presented output. Rates are undefined when there are no evaluated claims. Relative reduction is undefined when the OFF rate is zero.

The bundled, reproducible evaluation uses explicitly synthetic demonstration text and is not an empirical LLM experiment. Model generation is disabled for OFF/ON evaluation; the evaluation demonstrates deterministic failure blocking only. No provider credentials are configured in the current checkout. Empirical claims require a declared question set, real source corpus, fixed model/prompt conditions, and human claim labels; those are not supplied in this repository.

## Regulatory context and human review

SEBI's official website publishes the Securities and Exchange Board of India (Investment Advisers) Regulations, 2013, with the current page in this project checked as last amended on 25 November 2025 ([official SEBI regulation page](https://www.sebi.gov.in/legal/regulations/nov-2025/securities-and-exchange-board-of-india-investment-advisers-regulations-2013-and-securities-last-amended-on-november-25-2025-_98246.html)). This is a reference for awareness, not a legal opinion about whether any activity or person is covered. VerifyLayer does not offer investment advice, recommendations, execution, or portfolio management, and makes no claim of SEBI registration or legal compliance. A qualified human must inspect the original report, its consolidated or standalone basis, accounting notes, restatements, units, and context before relying on a passage or calculation.

## Data limits

No course artifacts A1, A2, A7, A9, attached capstone file, or actual company financial filing was available in the inspected workspace. The source registry begins empty. During the compliance audit, DNS/network access from the repository runtime to the official issuer host was unavailable; no public document was downloaded or source record fabricated. Ingest a user-supplied authentic public filing from its issuer or official exchange URL/file and retain its source metadata before making company-specific claims. Do not represent the synthetic sample as a retrieved public source. Do not commit credentials or private filings.
