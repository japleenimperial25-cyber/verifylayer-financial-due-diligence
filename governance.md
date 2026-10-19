# VerifyLayer governance and assumptions

## Intended use

VerifyLayer is an academic software prototype for examining citation-grounded verification. It is not investment research, financial advice, or a recommendation to buy, sell, or hold any security. Users must independently verify source filings and calculations.

## Evidence and verification

- A document is recorded only after a URL fetch succeeds or a local file is explicitly registered. The registry stores its supplied title, publisher, URL when applicable, actual UTC retrieval time for successful URL fetches, recording time, reporting period, origin, local path, and SHA-256 digest. Local registration does not claim an online retrieval.
- Plain text, Markdown, CSV, and PDF are supported; PDF page references come from extracted page boundaries. OCR, table reconstruction, semantic entailment, and dynamic web discovery are not implemented.
- Retrieval is deterministic lexical overlap over extracted paragraphs. It may miss relevant passages or return irrelevant ones.
- A claim is supported only if the full claim text occurs in its cited extracted span. Numeric disagreements for a shared metric are flagged as contradicted by a simple lexical rule. Other claims without direct support are unsupported. This is not a complete contradiction detector.
- With verification ON, every unsupported or contradicted claim is withheld and its reason retained. Citations alone do not establish support.

## Calculations and evaluation

Financial arithmetic uses Python `Decimal`; callers must supply values, units, periods, and input references. The prototype implements only summation and percentage change, as available from the project specification; no data or metrics are populated automatically from filings.

Evaluation claim records preserve both OFF and ON proposals. The denominator includes all proposed factual claims, including blocked claims. Hallucinated output claims are unsupported or contradicted claims that were shown as facts; blocked proposals remain counted in the denominator and are not treated as presented output. Rates are undefined when there are no evaluated claims. Relative reduction is undefined when the OFF rate is zero.

The bundled, reproducible app example uses explicitly synthetic demonstration text and is not an empirical LLM experiment. No model is connected. It demonstrates deterministic failure blocking only. Empirical claims require a declared question set, real source corpus, fixed model/prompt conditions, and human claim labels; those are not supplied in this repository.

## Data limits

No course artifacts A1, A2, A7, A9, attached capstone file, or actual company financial filing was available in the inspected workspace. The source registry begins empty. Do not represent the synthetic sample as a retrieved public source. Do not commit credentials or private filings.
