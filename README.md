# VerifyLayer — Citation-Grounded Verification

**Researchers:** Rashmi Sanjay Chate and Japleen Kaur

**Research question:** How much does a mandatory citation layer reduce hallucination in financial research output?

VerifyLayer is an academic capstone prototype that records document provenance, extracts and retrieves source passages, performs deterministic financial arithmetic, checks claim support, and presents an OFF/ON verification demonstration.

## Five-layer architecture

1. **L1 Ingest** — `ingest.py` registers a local document or fetches a user-supplied public URL. Successful inputs are stored under `data/` and recorded in `sources.csv` with title, URL, publisher, actual UTC retrieval time for URL fetches, recording time, period, origin, and digest. The initial registry is empty.
2. **L2 Extract** — `extract.py` extracts paragraphs from TXT, Markdown, CSV, or PDF. `rag/` retrieves passages with deterministic lexical overlap and preserves source IDs and PDF pages where available.
3. **L3 Engine** — `engine/` performs Decimal summation and percentage change from explicit sourced inputs and calculates evaluation measures. Financial mathematics stays outside any language model.
4. **L4 Commentary and verification** — `commentary.py` checks exact cited spans, labels unsupported/contradicted claims, blocks claims when enabled, and retains claim-level records.
5. **L5 Output** — `app.py` provides the Streamlit interface. `report.py` generates a Markdown annexure from saved evaluation records.

## Install on Windows

From PowerShell in the repository directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[app,test]'
```

## Run

```powershell
streamlit run app.py
```

Use **Run question** to inspect OFF or ON results. Use **Run evaluation and save records** to execute both conditions on the same synthetic question and corpus. Use **Generate report annexure** after evaluation, or run `python report.py` after records exist.

To register a local document:

```powershell
python ingest.py --title "Document title" --publisher "Publisher from the document" --period "FY2025" --local-path "C:\path\to\document.pdf"
```

To fetch a known public filing URL (only after supplying a verified URL and publisher):

```powershell
python ingest.py --title "Document title" --publisher "Publisher" --period "FY2025" --url "https://verified.example/document.pdf"
```

No source is preloaded. A source is recorded only after registration/fetch succeeds. Extract a registered source with `python extract.py <source_id>`.

## Limitations and research status

No A1, A2, A7, or A9 course artifacts, attached capstone file, public financial filing, or empirical claim labels were present in the inspected repository. The demo corpus and example claims are synthetic and clearly labelled; there is no connected LLM. The OFF/ON run demonstrates deterministic claim blocking but is **not evidence of real-world hallucination reduction**. Retrieval is lexical; verification uses conservative exact-span and simple numeric-conflict rules, not semantic entailment or complete contradiction detection. See [governance.md](governance.md).

Educational prototype only. It does not produce investment recommendations or financial advice.
