from decimal import Decimal

import pytest

from verifylayer.calculations import percentage_change, sum_values
from verifylayer.citations import verify_citation
from verifylayer.models import Claim, ExtractedPassage, FinancialValue


def test_sum_values_uses_decimal_and_preserves_unit_and_period():
    result = sum_values([
        FinancialValue(Decimal("10.25"), "INR crore", "FY2025", "annual-report-p1", "Sales: INR 10.25 crore"),
        FinancialValue(Decimal("0.75"), "INR crore", "FY2025", "annual-report-p2", "Sales: INR 0.75 crore"),
    ])
    assert result.value == Decimal("11.00")
    assert result.unit == "INR crore"
    assert result.period == "FY2025"
    assert [item.source_id for item in result.inputs] == ["annual-report-p1", "annual-report-p2"]


def test_sum_values_rejects_mixed_units():
    with pytest.raises(ValueError, match="matching units"):
        sum_values([FinancialValue(Decimal("1"), "INR", "FY2025", "src1", "one INR"),
                    FinancialValue(Decimal("1"), "USD", "FY2025", "src2", "one USD")])


def test_sum_values_rejects_mixed_periods_and_allows_negative_financial_values():
    with pytest.raises(ValueError, match="matching units and periods"):
        sum_values([FinancialValue(Decimal("1"), "INR crore", "FY2025", "src1", "FY2025 amount"),
                    FinancialValue(Decimal("1"), "INR crore", "FY2024", "src2", "FY2024 amount")])
    net = sum_values([FinancialValue(Decimal("-5"), "INR crore", "FY2025", "src1", "liability -5"),
                      FinancialValue(Decimal("8"), "INR crore", "FY2025", "src2", "asset 8")])
    assert net.value == Decimal("3")


def test_percentage_change_and_zero_prior_guard():
    current = FinancialValue(Decimal("125"), "INR crore", "FY2025", "annual-2025", "Revenue 125 crore")
    prior = FinancialValue(Decimal("100"), "INR crore", "FY2024", "annual-2024", "Revenue 100 crore")
    result = percentage_change(current, prior)
    assert result.value == Decimal("25.00")
    assert result.unit == "percent"
    assert result.inputs == (current, prior)
    with pytest.raises(ValueError, match="prior is zero"):
        percentage_change(FinancialValue(Decimal("1"), "INR crore", "FY2025", "src1", "current 1"),
                          FinancialValue(Decimal("0"), "INR crore", "FY2024", "src2", "prior 0"))


def test_percentage_change_with_negative_values_uses_documented_formula():
    current = FinancialValue(Decimal("-30"), "INR crore", "FY2025", "src-current", "loss 30")
    prior = FinancialValue(Decimal("-50"), "INR crore", "FY2024", "src-prior", "loss 50")
    result = percentage_change(current, prior)
    assert result.value == Decimal("-40.0")
    assert len(result.inputs) == 2


def test_percentage_change_rejects_mismatched_units_and_non_decimal_values():
    with pytest.raises(ValueError, match="same unit"):
        percentage_change(FinancialValue(Decimal("2"), "INR", "FY2025", "src1", "current"),
                          FinancialValue(Decimal("1"), "USD", "FY2024", "src2", "prior"))
    with pytest.raises(ValueError, match="finite Decimal"):
        sum_values([FinancialValue(Decimal("NaN"), "INR", "FY2025", "src1", "evidence")])


def test_percentage_change_uses_fixed_decimal_precision_without_changing_global_context():
    from decimal import getcontext

    original_precision = getcontext().prec
    result = percentage_change(
        FinancialValue(Decimal("2"), "INR crore", "FY2025", "src-current", "current 2"),
        FinancialValue(Decimal("3"), "INR crore", "FY2024", "src-prior", "prior 3"),
    )
    assert result.value == Decimal("-33.33333333333333333333333333333333")
    assert getcontext().prec == original_precision


def test_financial_calculations_require_source_evidence_and_period():
    with pytest.raises(ValueError, match="source_id"):
        sum_values([FinancialValue(Decimal("1"), "INR crore", "FY2025")])
    with pytest.raises(ValueError, match="reporting period"):
        sum_values([FinancialValue(Decimal("1"), "INR crore", None, "src", "evidence")])


def test_citation_requires_exact_extracted_passage():
    passage = ExtractedPassage("filing-1", "Revenue was reported for the period.", page=4)
    claim = Claim("Revenue was reported.", "filing-1", "Revenue was reported")
    assert verify_citation(claim, [passage]).verified
    wrong_source = Claim(claim.text, "other-filing", claim.cited_passage)
    assert not verify_citation(wrong_source, [passage]).verified

