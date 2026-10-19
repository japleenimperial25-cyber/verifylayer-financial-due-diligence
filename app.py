"""Focused Streamlit interface for the five-layer verification demonstration."""

try:
    import streamlit as st
except ImportError as exc:
    raise SystemExit("Install dependencies with: python -m pip install -e '.[app,test]'") from exc

from commentary import DEMO_QUESTION, run_experiment, run_workflow, save_experiment
from report import generate_report

st.set_page_config(page_title="VerifyLayer", page_icon="🔎", layout="wide")
st.title("VerifyLayer — Citation-Grounded Verification")
st.caption("Academic prototype. Educational use only; not investment advice or a buy/sell recommendation.")
st.write("Enter a research question. The local demo uses explicitly synthetic text and no language model.")
question = st.text_input("Financial research question", value=DEMO_QUESTION)
condition = st.radio("Verification gate", ["OFF", "ON"], horizontal=True)
mode = st.radio("Evidence corpus", ["Synthetic failure demonstration", "Registered source documents"], horizontal=True)

if st.button("Run question", type="primary"):
    synthetic_demo = mode == "Synthetic failure demonstration"
    result = run_workflow(question, verify=condition == "ON", demo=synthetic_demo)
    st.subheader(f"Answer — verification {condition}")
    st.write(result["answer"])
    st.metric("Blocked claims", result["blocked_claim_count"])
    st.subheader("Claim review")
    for claim in result["claims"]:
        st.write({"claim": claim["claim"], "evidence_status": claim["evidence_status"],
                  "blocked": claim["blocked"], "reason": claim["reason"], "citations": claim["citations"]})
    st.subheader("Retrieved evidence")
    for passage in result["passages"]:
        st.write({"source": passage["title"], "source_id": passage["source_id"], "page": passage["page"],
                  "exact_text": passage["text"], "label": "SYNTHETIC — NOT A REAL FILING" if synthetic_demo else "Registered source"})

st.divider()
st.subheader("Controlled OFF vs. ON evaluation")
st.caption("Same question and same synthetic passage in both conditions. This is a failure demonstration, not empirical research.")
if st.button("Run evaluation and save records"):
    experiment = run_experiment([question or DEMO_QUESTION])
    path = save_experiment(experiment)
    st.session_state["experiment"] = experiment
    st.success(f"Saved claim-level records to {path.relative_to(path.parents[1])}")

experiment = st.session_state.get("experiment")
if experiment:
    metrics = experiment["metrics"]
    first, second = st.columns(2)
    for column, key, run in ((first, "off", experiment["runs"][0]), (second, "on", experiment["runs"][1])):
        with column:
            st.markdown(f"**Verification {key.upper()}**")
            st.json(metrics[key])
            st.write("Generated answer:", run["answer"])
            st.write("Claim decisions:", [{"claim": item["claim"], "status": item["evidence_status"],
                                           "blocked": item["blocked"], "reason": item["reason"]}
                                          for item in run["claims"]])
    st.write("Reduction (percentage points):", metrics["comparison"]["absolute_reduction_percentage_points"])
    st.write("Relative reduction (%; undefined when OFF is zero):", metrics["comparison"]["relative_reduction_percent"])
    st.write("Blocked-claim reasons are preserved in the claim-level records above and in `data/evaluation_records.json`.")
    if st.button("Generate report annexure"):
        report_path = generate_report()
        st.success(f"Report generated: {report_path.relative_to(report_path.parents[1])}")
        st.download_button("Download report", report_path.read_text(encoding="utf-8"), file_name=report_path.name)

st.divider()
st.subheader("Five layers")
st.write("L1 Ingest — local files or explicitly supplied public URLs, recorded in `sources.csv`.")
st.write("L2 Extract — paragraph extraction and local lexical retrieval with source identifiers and page locations when available.")
st.write("L3 Engine — deterministic Decimal arithmetic; no language model performs calculations.")
st.write("L4 Commentary and verification — claim-level citation checks, reasons, and blocking.")
st.write("L5 Output — this interface and a Markdown annexure generated from saved evaluation records.")
