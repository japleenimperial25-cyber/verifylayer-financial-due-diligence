import json
from decimal import Decimal

import pytest

import extract
import ingest
from commentary import DEMO_QUESTION, classify_claim, run_experiment, run_workflow, save_experiment
from engine.calculations import percentage_change, sum_values
from engine.metrics import calculate_metrics
from report import generate_report


def test_engine_hand_worked_examples_and_input_traceability():
    sales_a = {"value": "125.50", "unit": "INR crore", "period": "FY2025", "source_id": "doc-1", "quote": "sales a"}
    sales_b = {"value": "24.50", "unit": "INR crore", "period": "FY2025", "source_id": "doc-2", "quote": "sales b"}
    total = sum_values([sales_a, sales_b])
    assert total.value == Decimal("150.00")
    assert total.inputs == (sales_a, sales_b)
    change = percentage_change({"value": "125", "unit": "INR", "period": "FY2025", "source_id": "current", "quote": "current revenue"},
                               {"value": "100", "unit": "INR", "period": "FY2024", "source_id": "prior", "quote": "prior revenue"})
    assert change.value == Decimal("25")
    assert change.inputs[0]["source_id"] == "current"


def test_engine_rejects_invalid_units_and_zero_denominator():
    with pytest.raises(ValueError, match="matching units"):
        sum_values([{"value": 1, "unit": "INR", "period": "FY2025", "source_id": "a", "quote": "1 INR"},
                    {"value": 1, "unit": "USD", "period": "FY2025", "source_id": "b", "quote": "1 USD"}])
    with pytest.raises(ValueError, match="prior is zero"):
        percentage_change({"value": 1, "unit": "INR", "period": "FY2025", "source_id": "current", "quote": "current"},
                          {"value": 0, "unit": "INR", "period": "FY2024", "source_id": "prior", "quote": "prior"})


def test_ingestion_and_extraction_preserve_source_identity(tmp_path, monkeypatch):
    source_file = tmp_path / "filing.txt"
    source_file.write_text("Section A\n\nA statement from the locally supplied document.", encoding="utf-8")
    registry = tmp_path / "sources.csv"
    monkeypatch.setattr(ingest, "ROOT", tmp_path)
    monkeypatch.setattr(ingest, "DATA", tmp_path / "data")
    monkeypatch.setattr(ingest, "SOURCES", registry)
    row = ingest.register_document(title="Supplied filing", publisher="User-supplied publisher",
                                   reporting_period="FY2025", published_on="2025-08-06", local_path=source_file)
    monkeypatch.setattr(extract, "ROOT", tmp_path)
    passages = extract.extract_registered(row["source_id"])
    assert all(passage["source_id"] == row["source_id"] for passage in passages)
    assert passages[1]["text"] == "A statement from the locally supplied document."
    assert row["origin"].startswith("local:")
    assert row["retrieved_at_utc"] == ""
    assert row["recorded_at_utc"]
    assert row["sha256"]
    assert passages[0]["published_on"] == "2025-08-06"
    assert passages[0]["sha256"] == row["sha256"]
    assert passages[0]["synthetic"] == "false"


def test_verifier_supports_flags_contradiction_and_blocks_missing_support():
    source = {"source_id": "demo", "title": "Synthetic", "source_url": "", "publisher": "Synthetic", "page": None,
              "text": "Synthetic demo company Alpha reported revenue of INR 120 crore for FY2025."}
    good = [{"source_id": "demo", "quote": source["text"]}]
    assert classify_claim(source["text"], good, [source])[0] == "supported"
    assert classify_claim("Alpha revenue was INR 999 crore in FY2025.", [], [source])[0] == "contradicted"
    assert classify_claim("Alpha opened a new factory.", [], [source])[0] == "unsupported"
    assert classify_claim("Alpha reported revenue of INR 999 crore.", [], []) == ("unsupported", "no cited extracted span directly supports this claim")
    verified = run_workflow(DEMO_QUESTION, verify=True, demo=True)
    assert verified["blocked_claim_count"] == 1
    assert verified["claims"][1]["blocked"] is True
    assert verified["claims"][1]["reason"]


def test_experiment_metrics_include_blocked_proposals_and_zero_denominators(tmp_path):
    experiment = run_experiment([DEMO_QUESTION])
    assert [run["condition"] for run in experiment["runs"]] == ["off", "on"]
    metrics = experiment["metrics"]
    assert metrics["off"]["total_evaluated_claims"] == 2
    assert metrics["on"]["total_evaluated_claims"] == 2
    assert metrics["on"]["blocked_claim_count"] == 1
    assert metrics["off"]["cited_claim_count"] == 1
    assert metrics["off"]["supported_claim_count"] == 1
    assert metrics["off"]["contradicted_claim_count"] == 1
    assert metrics["on"]["hallucinated_output_claims"] == 0
    assert metrics["off"]["hallucination_rate_percent"] == 50
    assert metrics["on"]["hallucination_rate_percent"] == 0
    assert metrics["comparison"]["absolute_reduction_percentage_points"] == 50
    assert metrics["comparison"]["relative_reduction_percent"] == 100
    assert experiment["runs"][0]["passages"] == experiment["runs"][1]["passages"]
    empty = calculate_metrics([])
    assert empty["off"]["hallucination_rate_percent"] is None
    assert empty["comparison"]["relative_reduction_percent"] is None
    empty_run = run_experiment(["question"], corpus=[])
    empty_records = save_experiment(empty_run, tmp_path / "empty-records.json")
    empty_report = generate_report(empty_records, tmp_path / "empty-report.md").read_text(encoding="utf-8")
    assert "undefined (no denominator)" in empty_report
    saved = save_experiment(experiment, tmp_path / "records.json")
    report = generate_report(saved, tmp_path / "report.md")
    report_text = report.read_text(encoding="utf-8")
    assert "SYNTHETIC CONTROLLED DEMONSTRATION" in report_text
    assert "Synthetic demo company Alpha" in report_text
    assert "No financial calculation was invoked" in report_text
    assert json.loads(saved.read_text(encoding="utf-8"))["claim_records"]
    assert "Hallucinated factual outputs (raw count)" in report_text
    assert "Evidence: source_id=synthetic-demo" in report_text
    assert "Assumptions, limitations, and intended use" in report_text
    assert "Claims with citations (raw count)" in report_text


def test_experiment_runs_each_question_in_both_conditions():
    experiment = run_experiment(["Question one", "Question two"])
    assert len(experiment["runs"]) == 4
    assert [run["question"] for run in experiment["runs"]] == ["Question one", "Question one", "Question two", "Question two"]


def test_empty_explicit_corpus_stays_empty_and_is_not_labelled_synthetic():
    experiment = run_experiment(["What is the revenue?"], corpus=[])
    assert experiment["label"] == "LOCAL CORPUS RULE-BASED EVALUATION - NOT LLM EMPIRICAL RESEARCH"
    assert all(run["passages"] == [] and run["claims"] == [] for run in experiment["runs"])
    assert experiment["metrics"]["off"]["total_evaluated_claims"] == 0
    assert experiment["metrics"]["off"]["hallucination_rate_percent"] is None


def test_explicit_synthetic_corpus_is_labeled_and_kept_in_both_conditions():
    passage = {"source_id": "demo-file", "title": "Synthetic input", "publisher": "Synthetic test",
               "synthetic": "true", "page": 1, "text": "Synthetic revenue was INR 10 crore."}
    experiment = run_experiment(["What was synthetic revenue?"], corpus=[passage])
    assert "SYNTHETIC" in experiment["label"]
    assert experiment["runs"][0]["passages"] == experiment["runs"][1]["passages"] == [passage]


def test_financial_engine_rejects_missing_nonfinite_and_mismatched_inputs():
    with pytest.raises(ValueError, match="reporting period"):
        sum_values([{"value": "2", "unit": "INR crore", "source_id": "doc", "quote": "revenue 2"}])
    with pytest.raises(ValueError, match="matching units and periods"):
        sum_values([{"value": "2", "unit": "INR crore", "period": "FY2025", "source_id": "a", "quote": "FY2025 value"},
                    {"value": "1", "unit": "INR crore", "period": "FY2024", "source_id": "b", "quote": "FY2024 value"}])
    with pytest.raises(ValueError, match="valid decimal"):
        sum_values([{"value": "not-a-number", "unit": "INR crore", "period": "FY2025", "source_id": "doc", "quote": "revenue"}])
    with pytest.raises(ValueError, match="finite"):
        sum_values([{"value": "NaN", "unit": "INR crore", "period": "FY2025", "source_id": "doc", "quote": "revenue"}])
    with pytest.raises(ValueError, match="evidence quote"):
        percentage_change({"value": "2", "unit": "INR crore", "period": "FY2025", "source_id": "doc"},
                          {"value": "1", "unit": "INR crore", "period": "FY2024", "source_id": "doc2", "quote": "prior"})
    with pytest.raises(ValueError, match="different reporting periods"):
        percentage_change({"value": "2", "unit": "INR crore", "period": "FY2025", "source_id": "doc", "quote": "current"},
                          {"value": "1", "unit": "INR crore", "period": "FY2025", "source_id": "doc2", "quote": "prior"})
    recurring = percentage_change(
        {"value": "2", "unit": "INR crore", "period": "FY2025", "source_id": "current", "quote": "current 2"},
        {"value": "3", "unit": "INR crore", "period": "FY2024", "source_id": "prior", "quote": "prior 3"},
    )
    assert recurring.value == Decimal("-33.33333333333333333333333333333333")
