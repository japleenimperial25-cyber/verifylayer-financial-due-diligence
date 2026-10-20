import json
import io
from decimal import Decimal
from urllib.error import HTTPError, URLError

import pytest

import answering
import app
import commentary
from engine.calculations import margin, ratio


def _passages():
    return [
        {"source_id": "issuer-fy25", "title": "Issuer FY2025 annual report", "publisher": "Example Industries Limited",
         "source_url": "https://issuer.example/report.pdf", "page": 11, "reporting_period": "FY2025",
         "text": "Revenue was INR 120 crore for FY2025."},
        {"source_id": "issuer-fy25", "title": "Issuer FY2025 annual report", "publisher": "Example Industries Limited",
         "source_url": "https://issuer.example/report.pdf", "page": 12, "reporting_period": "FY2025",
         "text": "Net profit was INR 12 crore in FY2025."},
    ]


def _margin_proposal():
    return {
        "status": "complete",
        "answer": "ignored unless its claims pass source validation",
        "claims": [{"text": "Revenue was INR 120 crore for FY2025.",
                    "citations": [{"evidence_id": "E1", "quote": "Revenue was INR 120 crore for FY2025."}]}],
        "calculations": [{"operation": "margin", "name": "Net profit margin", "inputs": [
            {"metric": "net profit", "value": "12", "unit": "INR crore", "period": "FY2025",
             "source_id": "issuer-fy25", "quote": "Net profit was INR 12 crore in FY2025."},
            {"metric": "revenue", "value": "120", "unit": "INR crore", "period": "FY2025",
             "source_id": "issuer-fy25", "quote": "Revenue was INR 120 crore for FY2025."},
        ]}],
        "missing_evidence": [], "limitations": [], "clarification_question": "",
    }


def test_server_side_provider_sends_only_retrieved_evidence(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "server-secret")
    monkeypatch.setenv("VERIFYLAYER_LLM_MODEL", "test-model")
    captured = {}
    proposal = _margin_proposal()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"choices": [{"message": {"content": json.dumps(proposal)}}]}).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(answering, "urlopen", fake_urlopen)
    result = answering.generate_proposal("What was revenue and net profit?", _passages())
    assert result == proposal
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["authorization"] == "Bearer server-secret"
    assert "Revenue was INR 120 crore for FY2025." in json.dumps(captured["body"])
    assert "No API key is sent" not in json.dumps(captured["body"])


@pytest.mark.parametrize(
    ("configured", "expected"),
    [(None, 180), ("240", 240)],
)
def test_provider_timeout_is_sensible_and_configurable(monkeypatch, configured, expected):
    monkeypatch.setenv("OPENAI_API_KEY", "server-secret")
    monkeypatch.setenv("VERIFYLAYER_LLM_MODEL", "test-model")
    if configured is None:
        monkeypatch.delenv("VERIFYLAYER_LLM_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("VERIFYLAYER_LLM_TIMEOUT_SECONDS", configured)
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"choices": [{"message": {"content": json.dumps(_margin_proposal())}}]}).encode()

    def fake_urlopen(_request, timeout):
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(answering, "urlopen", fake_urlopen)
    answering.generate_proposal("What was revenue?", _passages())
    assert captured["timeout"] == expected


@pytest.mark.parametrize("failure", [TimeoutError("slow"), URLError(TimeoutError("slow"))])
def test_provider_timeout_returns_actionable_error_without_unstructured_retry(monkeypatch, failure):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("VERIFYLAYER_LLM_MODEL", "llama3.2:3b")
    calls = []

    def fail(*_args, **_kwargs):
        calls.append(True)
        raise failure

    monkeypatch.setattr(answering, "urlopen", fail)
    with pytest.raises(answering.ProviderError, match="did not finish within 180 seconds") as caught:
        answering.generate_proposal("Question", _passages())
    assert caught.value.code == "timeout"
    assert "no unverified answer was used" in str(caught.value)
    assert len(calls) == 1


@pytest.mark.parametrize("value", ["abc", "9", "601"])
def test_invalid_provider_timeout_configuration_is_rejected(value):
    with pytest.raises(answering.ProviderNotConfigured, match="VERIFYLAYER_LLM_TIMEOUT_SECONDS"):
        answering.provider_timeout_seconds({"VERIFYLAYER_LLM_TIMEOUT_SECONDS": value})


def test_local_ollama_configuration_needs_no_api_key_and_omits_authorization(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("VERIFYLAYER_LLM_MODEL", "llama3.2:3b")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"choices": [{"message": {"content": json.dumps(_margin_proposal())}}]}).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(answering, "urlopen", fake_urlopen)
    assert answering.provider_is_configured()
    assert answering.generate_proposal("What was revenue?", _passages()) == _margin_proposal()
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["body"]["model"] == "llama3.2:3b"
    assert captured["body"]["max_tokens"] == answering.OLLAMA_MAX_OUTPUT_TOKENS
    assert "max_completion_tokens" not in captured["body"]
    assert captured["body"]["response_format"] == {"type": "json_object"}
    prompt = captured["body"]["messages"][0]["content"]
    assert '"claims":[' in prompt
    assert "adjacent column headings" in prompt
    assert "Use an empty claims array only when none" in prompt
    assert "every citation has evidence_id (string) and quote (string)" in prompt
    assert "missing_evidence: array of strings" in prompt
    assert not any(name.lower() == "authorization" for name in captured["headers"])


def test_local_ollama_never_sends_a_configured_remote_api_key(monkeypatch):
    settings = {"OPENAI_API_KEY": "remote-secret", "VERIFYLAYER_LLM_MODEL": "llama3.2:3b",
                "OPENAI_BASE_URL": "http://127.0.0.1:11434/v1"}
    key, model, base = answering._provider_settings(settings)
    assert key == ""
    assert model == "llama3.2:3b"
    assert base == "http://127.0.0.1:11434/v1"


def test_ollama_evidence_is_compact_relevant_and_keeps_original_citation_ids():
    irrelevant = {"source_id": "source", "page": 10, "reporting_period": "FY2024-25",
                  "text": "Tata Steel operational detail about suppliers and production. " * 40}
    long_table = {"source_id": "source", "page": 130, "reporting_period": "FY2024-25",
                  "text": ("Tata Steel annual report background. " * 80)
                          + "A. Financial Results (INR crore) Tata Steel Standalone 2024-25 2023-24 Revenue from operations 1,32,516.66 1,40,932.65"}
    highlights = {"source_id": "source", "page": 256, "reporting_period": "FY2024-25",
                  "text": "Tata Steel Financial Highlights FY2024-25 Revenue from operations 1,32,516.66 1,40,932.65"}
    unrelated_turnover = {"source_id": "source", "page": 182, "reporting_period": "FY2024-25",
                          "text": "Tata Steel subsidiary FY2024-25 Turnover 7,374 crore."}
    statement = {"source_id": "source", "page": 281, "reporting_period": "FY2024-25",
                 "text": "Tata Steel Statement of Profit and Loss FY2024-25 Revenue from operations 1,32,516.66"}
    passages = [long_table, highlights, unrelated_turnover, statement, irrelevant]

    evidence = answering._model_evidence("What was Tata Steel's revenue from operations in FY2024-25?", passages)

    assert [item["evidence_id"] for item in evidence] == ["E1", "E2", "E4"]
    assert all(len(item["text"]) <= answering.MAX_MODEL_EVIDENCE_CHARS for item in evidence)
    assert "Revenue from operations 1,32,516.66" in evidence[0]["text"]
    assert all(item["text"] in passages[int(item["evidence_id"][1:]) - 1]["text"] for item in evidence)
    proposal = {"status": "complete", "answer": "", "claims": [{
        "text": "Revenue from operations 1,32,516.66",
        "citations": [{"evidence_id": "E4", "quote": "Revenue from operations 1,32,516.66"}],
    }], "calculations": [], "missing_evidence": [], "limitations": [], "clarification_question": ""}
    checked = answering.verify_proposal("Tata Steel revenue FY2024-25", proposal, passages, commentary.classify_claim)
    assert checked["claims"][0]["evidence_status"] == "supported"
    assert checked["claims"][0]["citations"][0]["source_id"] == "source"


@pytest.mark.parametrize("base_url", ["http://example.com/v1", "http://192.168.1.20:11434/v1"])
def test_plain_http_is_rejected_for_non_loopback_provider(base_url):
    with pytest.raises(answering.ProviderNotConfigured, match="only for localhost/loopback"):
        answering._provider_settings({"VERIFYLAYER_LLM_MODEL": "llama3.2:3b", "OPENAI_BASE_URL": base_url})


def test_unsupported_json_mode_returns_safe_actionable_provider_error(monkeypatch):
    monkeypatch.setenv("VERIFYLAYER_LLM_MODEL", "llama3.2:3b")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    error_body = io.BytesIO(b'{"error":"response_format json_object is not supported"}')
    error = HTTPError("http://localhost:11434/v1/chat/completions", 400, "bad request", {}, error_body)
    monkeypatch.setattr(answering, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(error))
    with pytest.raises(answering.ProviderError, match="Update Ollama.*JSON mode") as caught:
        answering.generate_proposal("Question", _passages())
    assert caught.value.code == "unsupported_response_format"


@pytest.mark.parametrize("content", [
    "",
    "not JSON",
    "{}",
    '{"status":"insufficient"}',
    json.dumps({**_margin_proposal(), "status": []}),
    json.dumps({**_margin_proposal(), "claims": [{"text": "missing citations"}]}),
    json.dumps({**_margin_proposal(), "calculations": [{"operation": "sum", "name": "bad", "inputs": [{"value": "1"}]}]}),
])
def test_empty_or_malformed_json_answer_is_provider_error(monkeypatch, content):
    monkeypatch.setenv("VERIFYLAYER_LLM_MODEL", "llama3.2:3b")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    calls = []
    monkeypatch.setattr(answering, "urlopen", lambda *_args, **_kwargs: (calls.append(True) or Response()))
    with pytest.raises(answering.ProviderError) as caught:
        answering.generate_proposal("Question", _passages())
    expected_code = "empty_response" if content == "" else "invalid_json" if content == "not JSON" else "invalid_response"
    assert caught.value.code == expected_code
    assert len(calls) == 1


def test_truncated_json_completion_returns_specific_error_without_retry(monkeypatch):
    monkeypatch.setenv("VERIFYLAYER_LLM_MODEL", "llama3.2:3b")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"choices": [{"message": {"content": '{"status":'},
                                             "finish_reason": "length"}]}).encode()

    calls = []
    monkeypatch.setattr(answering, "urlopen", lambda *_args, **_kwargs: (calls.append(True) or Response()))
    with pytest.raises(answering.ProviderError, match="output was cut off") as caught:
        answering.generate_proposal("Question", _passages())
    assert caught.value.code == "truncated_response"
    assert len(calls) == 1


def test_missing_credentials_are_actionable_and_no_key_is_required_for_evidence_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("VERIFYLAYER_LLM_MODEL", raising=False)
    with pytest.raises(answering.ProviderNotConfigured, match="OPENAI_API_KEY"):
        answering.generate_proposal("Question", _passages())
    monkeypatch.setattr("commentary.retrieve", lambda _question: _passages())
    result = commentary.run_workflow("Example Industries FY2025 revenue")
    assert result["generation_status"] == "not_configured"
    assert result["answer_status"] == "partial"
    assert "OPENAI_API_KEY" in result["generation_error"]
    assert result["claims"][0]["citations"][0]["source_id"] == "issuer-fy25"


def test_provider_auth_rate_limit_and_network_errors_are_sanitized(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "never-show-this")
    monkeypatch.setenv("VERIFYLAYER_LLM_MODEL", "test-model")

    def fail(code):
        raise HTTPError("https://api.openai.com/v1/chat/completions", code, "private provider detail", {}, None)

    monkeypatch.setattr(answering, "urlopen", lambda *_args, **_kwargs: fail(429))
    with pytest.raises(answering.ProviderError, match="quota") as error:
        answering.generate_proposal("Question", _passages())
    assert error.value.code == "rate_limited"
    assert "never-show-this" not in str(error.value)
    monkeypatch.setattr(answering, "urlopen", lambda *_args, **_kwargs: fail(401))
    with pytest.raises(answering.ProviderError, match="Check OPENAI_API_KEY"):
        answering.generate_proposal("Question", _passages())


def test_provider_http_failure_is_actionable_and_not_retried(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("VERIFYLAYER_LLM_MODEL", "llama3.2:3b")
    calls = []
    error = HTTPError("http://localhost:11434/v1/chat/completions", 503, "private server detail", {}, None)

    def fail(*_args, **_kwargs):
        calls.append(True)
        raise error

    monkeypatch.setattr(answering, "urlopen", fail)
    with pytest.raises(answering.ProviderError, match="HTTP 503") as caught:
        answering.generate_proposal("Question", _passages())
    assert caught.value.code == "provider_http"
    assert "private server detail" not in str(caught.value)
    assert len(calls) == 1


def test_research_surfaces_provider_timeout_and_keeps_verified_excerpt(monkeypatch):
    monkeypatch.setattr("commentary.retrieve", lambda _question: _passages())

    def timeout(_question, _passages):
        raise answering.ProviderError("timeout", "Ollama did not finish within 180 seconds.")

    monkeypatch.setattr("commentary.generate_proposal", timeout)
    result = commentary.run_workflow("What was issuer revenue in FY2025?")
    assert result["generation_status"] == "provider_error"
    assert result["provider_error_code"] == "timeout"
    assert "did not finish within 180 seconds" in result["generation_error"]
    assert result["claims"][0]["evidence_status"] == "supported"
    assert result["claims"][0]["citations"][0]["source_id"] == "issuer-fy25"


def test_five_retrieved_passages_and_empty_model_claims_are_reported_as_model_abstention(monkeypatch):
    passages = [
        {**_passages()[index % 2], "page": 130 + index, "text": f"Financial Results passage {index}: revenue from operations."}
        for index in range(5)
    ]
    empty_proposal = {
        "status": "insufficient", "answer": "", "claims": [], "calculations": [],
        "missing_evidence": ["No directly supported claim returned."], "limitations": [],
        "clarification_question": "",
    }
    monkeypatch.setattr("commentary.generate_proposal", lambda _question, _passages: empty_proposal)
    result = commentary.run_workflow(
        "What was Tata Steel revenue from operations in FY2024-25?", passages=passages,
    )
    assert len(result["passages"]) == 5
    assert result["answer_status"] == "insufficient"
    assert result["generation_status"] == "generated"
    assert result["proposed_claim_count"] == 0
    assert result["provider_status"] == {"configured": True, "request_attempted": True, "response_received": True}
    assert "responded in JSON but proposed no verifiable claims" in result["generation_note"]
    assert result["answer"] == "No factual answer passed evidence verification; answer withheld."
    assert result["claims"] == []


def test_generated_claims_require_exact_retrieved_quotes_and_calculations_use_python():
    result = answering.verify_proposal("What was revenue and margin?", _margin_proposal(), _passages(), commentary.classify_claim)
    assert result["answer_status"] == "complete"
    assert result["claims"][0]["evidence_status"] == "supported"
    assert result["calculations"][0]["value"] == "10.0"
    assert result["calculations"][0]["unit"] == "percent"
    assert result["calculations"][0]["formula"] == "(numerator / denominator) × 100"
    assert "10.0 percent" in result["answer"]

    forged = _margin_proposal()
    forged["claims"] = [{"text": "Tata revenue was INR 999 crore.",
                         "citations": [{"evidence_id": "E1", "quote": "Revenue was INR 120 crore for FY2025."}]}]
    forged["calculations"][0]["inputs"][0]["value"] = "2025"
    blocked = answering.verify_proposal("What was Tata revenue?", forged, _passages(), commentary.classify_claim)
    assert blocked["answer_status"] == "insufficient"
    assert blocked["rejected_claim_count"] == 1
    assert blocked["calculations"][0]["status"] == "blocked"
    assert blocked["answer"] == "No factual answer passed evidence verification; answer withheld."


def test_revenue_growth_uses_cited_current_and_prior_period_inputs():
    passages = [
        {"source_id": "report-2025", "page": 10, "reporting_period": "FY2025",
         "text": "Revenue was INR 120 crore for FY2025."},
        {"source_id": "report-2024", "page": 10, "reporting_period": "FY2024",
         "text": "Revenue was INR 100 crore for FY2024."},
    ]
    proposal = {"status": "complete", "claims": [], "calculations": [{
        "operation": "percentage_change", "name": "Revenue growth", "inputs": [
            {"metric": "revenue", "value": "120", "unit": "INR crore", "period": "FY2025",
             "source_id": "report-2025", "quote": passages[0]["text"]},
            {"metric": "revenue", "value": "100", "unit": "INR crore", "period": "FY2024",
             "source_id": "report-2024", "quote": passages[1]["text"]},
        ]}], "missing_evidence": [], "limitations": [], "clarification_question": ""}
    result = answering.verify_proposal("What was revenue growth?", proposal, passages, commentary.classify_claim)
    assert result["answer_status"] == "complete"
    assert result["calculations"][0]["value"] == "20.0"
    assert result["calculations"][0]["period"] == "comparison"
    assert len(result["calculations"][0]["citations"]) == 2


def test_missing_evidence_skips_model_and_returns_insufficient(monkeypatch):
    monkeypatch.setattr("commentary.retrieve", lambda _question: [])
    monkeypatch.setattr("commentary.generate_proposal", lambda *_args: pytest.fail("model should not run without evidence"))
    result = commentary.run_workflow("What was Example revenue?")
    assert result["answer_status"] == "insufficient"
    assert result["generation_status"] == "skipped_no_evidence"
    assert result["claims"] == []
    assert result["calculations"] == []


def test_research_workflow_integrates_model_proposal_with_verified_calculation(monkeypatch):
    monkeypatch.setattr("commentary.retrieve", lambda _question: _passages())
    monkeypatch.setattr("commentary.generate_proposal", lambda _question, _passages: _margin_proposal())
    result = commentary.run_workflow("What were revenue and net profit margin for Example in FY2025?")
    assert result["generation_status"] == "generated"
    assert result["answer_status"] == "complete"
    assert "Revenue was INR 120 crore for FY2025." in result["answer"]
    assert "10.0 percent" in result["answer"]
    assert result["calculations"][0]["citations"][0]["source_id"] == "issuer-fy25"


def test_vercel_research_api_returns_verified_answer_and_calculations(monkeypatch):
    monkeypatch.setattr("commentary.retrieve", lambda _question: _passages())
    monkeypatch.setattr("commentary.generate_proposal", lambda _question, _passages: _margin_proposal())
    request_body = json.dumps({"question": "What is net profit margin?", "verify": True, "mode": "registered"}).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/api/research", "CONTENT_TYPE": "application/json",
               "CONTENT_LENGTH": str(len(request_body)), "wsgi.input": io.BytesIO(request_body)}
    response = {}
    body = b"".join(app.application(environ, lambda status, headers: response.update(status=status)))
    result = json.loads(body)
    assert response["status"] == "200 OK"
    assert result["answer_status"] == "complete"
    assert result["calculations"][0]["value"] == "10.0"
    assert result["claims"][0]["citations"][0]["quote"] == "Revenue was INR 120 crore for FY2025."


def test_margin_and_ratio_calculators_require_comparable_sourced_inputs():
    numerator = {"value": "12", "unit": "INR crore", "period": "FY2025", "source_id": "a", "quote": "profit 12"}
    denominator = {"value": "120", "unit": "INR crore", "period": "FY2025", "source_id": "b", "quote": "revenue 120"}
    assert margin(numerator, denominator).value == Decimal("10")
    assert ratio(numerator, denominator).value == Decimal("0.1")
    with pytest.raises(ValueError, match="same reporting period"):
        margin(numerator, {**denominator, "period": "FY2024"})
    with pytest.raises(ValueError, match="denominator is zero"):
        ratio(numerator, {**denominator, "value": "0"})
