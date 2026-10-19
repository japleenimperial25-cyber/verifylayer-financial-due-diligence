"""Claim-level evidence verification and controlled OFF/ON demonstration."""

import json
from pathlib import Path
from datetime import datetime, timezone

from engine.metrics import calculate_metrics
from rag import retrieve

ROOT = Path(__file__).resolve().parent
SYNTHETIC_SENTENCE = "Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025."
DEMO_QUESTION = "Summarize the synthetic demo company's FY2025 revenue."


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace(".", "").replace(",", "").split())


def _numbers(text: str) -> set[str]:
    import re
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def classify_claim(text: str, citations: list[dict], passages: list[dict]) -> tuple[str, str]:
    """Require a cited exact source span; detect a simple conflicting numeric value for the same metric."""
    for citation in citations:
        for passage in passages:
            if citation.get("source_id") == passage["source_id"] and citation.get("quote", "") in passage["text"]:
                if _normalize(text) in _normalize(citation["quote"]):
                    return "supported", "claim text is contained in the cited extracted span"
    text_numbers = _numbers(text)
    for passage in passages:
        if any(term in text.lower() and term in passage["text"].lower() for term in ("revenue", "profit", "debt", "assets", "cash flow")):
            if text_numbers and _numbers(passage["text"]) and not text_numbers.issubset(_numbers(passage["text"])):
                return "contradicted", "retrieved passage reports a different numeric value for the same metric"
    return "unsupported", "no cited extracted span directly supports this claim"


def run_workflow(question: str, *, verify: bool = True, passages: list[dict] | None = None, demo: bool = False) -> dict:
    if not question.strip():
        raise ValueError("research question must not be empty")
    if passages is None:
        passages = retrieve(question)
    if demo:
        claims = [
            {"text": SYNTHETIC_SENTENCE, "citations": [{"source_id": "synthetic-demo", "quote": SYNTHETIC_SENTENCE}]},
            {"text": "Synthetic demo company Alpha reported revenue of INR 999 crore for FY2025.", "citations": []},
        ]
        passages = [{"source_id": "synthetic-demo", "title": "Synthetic demonstration passage", "source_url": "",
                     "publisher": "Synthetic example (not a real publisher)", "page": None, "text": SYNTHETIC_SENTENCE}]
    else:
        claims = [{"text": p["text"], "citations": [{"source_id": p["source_id"], "quote": p["text"]}]} for p in passages[:3]]
    claim_records = []
    for claim in claims:
        evidence_status, reason = classify_claim(claim["text"], claim["citations"], passages)
        blocked = verify and evidence_status != "supported"
        claim_records.append({"condition": "on" if verify else "off", "question": question, "claim": claim["text"],
                             "citations": claim["citations"], "evidence_status": evidence_status,
                             "blocked": blocked, "reason": reason})
    shown = [record for record in claim_records if not record["blocked"]]
    answer = " ".join(record["claim"] for record in shown) if shown else "No factual claim passed verification; answer withheld."
    return {"condition": "on" if verify else "off", "question": question, "answer": answer, "claims": claim_records,
            "passages": passages, "blocked_claim_count": sum(record["blocked"] for record in claim_records)}


def run_experiment(questions: list[str] | None = None, *, corpus: list[dict] | None = None) -> dict:
    """Run identical questions and corpus under OFF and ON; defaults to labelled synthetic demo."""
    questions = questions or [DEMO_QUESTION]
    synthetic_demo = corpus is None
    corpus = corpus or [{"source_id": "synthetic-demo", "title": "Synthetic demonstration passage", "source_url": "",
                         "publisher": "Synthetic example (not a real publisher)", "page": None, "text": SYNTHETIC_SENTENCE}]
    results = [run_workflow(question, verify=verify, passages=corpus, demo=synthetic_demo)
               for question in questions for verify in (False, True)]
    records = [claim for result in results for claim in result["claims"]]
    experiment = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                  "label": "SYNTHETIC CONTROLLED DEMONSTRATION - NOT EMPIRICAL RESEARCH" if synthetic_demo else "LOCAL CORPUS RULE-BASED EVALUATION - NOT LLM EMPIRICAL RESEARCH",
                  "question_set": questions, "corpus": corpus, "calculation_records": [], "runs": results, "claim_records": records,
                  "metrics": calculate_metrics(records)}
    return experiment


def save_experiment(experiment: dict, path: str | Path | None = None) -> Path:
    destination = Path(path) if path else ROOT / "data" / "evaluation_records.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(experiment, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination
