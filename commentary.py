"""Claim-level evidence verification and controlled OFF/ON demonstration."""

import json
from pathlib import Path
from datetime import datetime, timezone

from engine.metrics import calculate_metrics
from rag import ambiguous_entity_publishers, analyze_question, retrieve
from answering import ProviderError, ProviderNotConfigured, generate_proposal, provider_is_configured, verify_proposal

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


def run_workflow(question: str, *, verify: bool = True, passages: list[dict] | None = None,
                 source_ids: list[str] | None = None, demo: bool = False, generate: bool = True) -> dict:
    if not question.strip():
        raise ValueError("research question must not be empty")
    if demo and passages is None and _normalize(question.rstrip("?.! ")) != _normalize(DEMO_QUESTION.rstrip("?.! ")):
        raise ValueError("The synthetic demonstration only accepts its fixed, clearly labeled demo question.")
    if passages is None and not demo and generate:
        ambiguous_publishers = ambiguous_entity_publishers(question, source_ids=source_ids)
        if ambiguous_publishers:
            clarification = "Which issuer do you mean? Matching registered publishers: " + "; ".join(ambiguous_publishers)
            return {"condition": "on" if verify else "off", "question": question, "answer": clarification,
                    "claims": [], "passages": [], "blocked_claim_count": 0, "request_context": analyze_question(question),
                    "calculations": [], "missing_evidence": [], "limitations": [], "answer_status": "clarification",
                    "evidence_status": "clarification", "generation_status": "clarification_required",
                    "provider_status": {"configured": provider_is_configured(), "request_attempted": False,
                                        "response_received": False},
                    "clarification_question": clarification, "ambiguity_candidates": ambiguous_publishers}
    if passages is None:
        passages = retrieve(question) if source_ids is None else retrieve(question, source_ids=source_ids)
    if demo:
        claims = [
            {"text": SYNTHETIC_SENTENCE, "citations": [{"source_id": "synthetic-demo", "quote": SYNTHETIC_SENTENCE}]},
            {"text": "Synthetic demo company Alpha reported revenue of INR 999 crore for FY2025.", "citations": []},
        ]
        passages = [{"source_id": "synthetic-demo", "title": "Synthetic demonstration passage", "source_url": "",
                     "publisher": "Synthetic example (not a real publisher)", "synthetic": "true",
                     "page": None, "text": SYNTHETIC_SENTENCE}]
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
    result = {"condition": "on" if verify else "off", "question": question, "answer": answer, "claims": claim_records,
              "passages": passages, "blocked_claim_count": sum(record["blocked"] for record in claim_records),
              "request_context": analyze_question(question), "calculations": [], "missing_evidence": [],
              "limitations": [], "answer_status": "partial",
              "provider_status": {"configured": provider_is_configured(), "request_attempted": False,
                                  "response_received": False}}
    if not passages and not demo:
        result["evidence_status"] = "insufficient"
        result["answer_status"] = "insufficient"
        result["generation_status"] = "skipped_no_evidence"
        result["insufficient_reason"] = "No matching registered source passage was retrieved. No live web or financial-data provider is configured."
        result["next_step"] = "Register an authentic source document, then select it and ask a question about its contents."
    elif demo:
        result["evidence_status"] = "demo"
        result["answer_status"] = "demo"
        result["generation_status"] = "not_applicable"
        result["limitations"] = ["This is a fixed synthetic controlled demonstration, not financial evidence."]
    elif not generate:
        result["evidence_status"] = "retrieved"
        result["generation_status"] = "disabled_for_deterministic_evaluation"
        result["limitations"] = ["Saved evaluation runs the deterministic evidence workflow; model generation is intentionally disabled."]
    else:
        result["evidence_status"] = "retrieved"
        try:
            proposal = generate_proposal(question, passages)
            checked = verify_proposal(question, proposal, passages, classify_claim)
            result.update(checked)
            result["generation_status"] = "generated"
            result["provider_status"] = {"configured": True, "request_attempted": True, "response_received": True}
            raw_claims = proposal.get("claims", [])
            result["proposed_claim_count"] = len(raw_claims) if isinstance(raw_claims, list) else 0
            if not result["proposed_claim_count"] and not any(
                item.get("status") == "supported" for item in checked.get("calculations", [])
            ):
                result["generation_note"] = (
                    "The model responded in JSON but proposed no verifiable claims or calculations. "
                    "VerifyLayer withheld the answer; review the retrieved passages or refine the question."
                )
            result["blocked_claim_count"] = sum(bool(record.get("blocked")) for record in checked["claims"])
        except ProviderNotConfigured as exc:
            result["generation_status"] = "not_configured"
            result["provider_status"] = {"configured": False, "request_attempted": False,
                                          "response_received": False}
            result["generation_error"] = str(exc)
            result["limitations"] = ["Showing retrieved source excerpts only; no model-generated synthesis is available."]
        except ProviderError as exc:
            result["generation_status"] = "provider_error"
            result["provider_status"] = {
                "configured": True, "request_attempted": True,
                "response_received": exc.code not in {"timeout", "network"},
            }
            result["generation_error"] = str(exc)
            result["provider_error_code"] = exc.code
            result["limitations"] = ["Showing retrieved source excerpts only because answer generation failed."]
    return result


def run_experiment(questions: list[str] | None = None, *, corpus: list[dict] | None = None) -> dict:
    """Run identical questions and corpus under OFF and ON; defaults to labelled synthetic demo."""
    questions = questions or [DEMO_QUESTION]
    synthetic_fixture = corpus is None
    if synthetic_fixture:
        corpus = [{"source_id": "synthetic-demo", "title": "Synthetic demonstration passage", "source_url": "",
                   "publisher": "Synthetic example (not a real publisher)", "synthetic": "true",
                   "page": None, "text": SYNTHETIC_SENTENCE}]
    contains_synthetic = synthetic_fixture or any(
        str(item.get("synthetic", "")).lower() == "true" or item.get("source_id") == "synthetic-demo"
        for item in corpus
    )
    results = [run_workflow(question, verify=verify, passages=corpus, demo=synthetic_fixture, generate=False)
               for question in questions for verify in (False, True)]
    records = [claim for result in results for claim in result["claims"]]
    experiment = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                  "label": ("SYNTHETIC CONTROLLED DEMONSTRATION - NOT EMPIRICAL RESEARCH" if synthetic_fixture else
                            "LOCAL CORPUS CONTAINS SYNTHETIC DATA - NOT EMPIRICAL RESEARCH" if contains_synthetic else
                            "LOCAL CORPUS RULE-BASED EVALUATION - NOT LLM EMPIRICAL RESEARCH"),
                  "question_set": questions, "corpus": corpus, "calculation_records": [], "runs": results, "claim_records": records,
                  "metrics": calculate_metrics(records)}
    return experiment


def save_experiment(experiment: dict, path: str | Path | None = None) -> Path:
    destination = Path(path) if path else ROOT / "data" / "evaluation_records.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(experiment, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination
