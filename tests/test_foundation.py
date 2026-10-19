from decimal import Decimal

import pytest

from verifylayer.calculations import percentage_change, sum_values
from verifylayer.citations import verify_citation
from verifylayer.models import Claim, ExtractedPassage, FinancialValue


def test_sum_values_uses_decimal_and_preserves_unit_and_period():
    result = sum_values([
        FinancialValue(Decimal("10.25"), "INR", "FY2025"),
        FinancialValue(Decimal("0.75"), "INR", "FY2025"),
    ])
    assert result == FinancialValue(Decimal("11.00"), "INR", "FY2025")


def test_sum_values_rejects_mixed_units():
    with pytest.raises(ValueError, match="matching units"):
        sum_values([FinancialValue(Decimal("1"), "INR"), FinancialValue(Decimal("1"), "USD")])


def test_percentage_change_and_zero_prior_guard():
    assert percentage_change(Decimal("125"), Decimal("100")) == Decimal("25.00")
    with pytest.raises(ValueError, match="prior is zero"):
        percentage_change(Decimal("1"), Decimal("0"))


def test_citation_requires_exact_extracted_passage():
    passage = ExtractedPassage("filing-1", "Revenue was reported for the period.", page=4)
    claim = Claim("Revenue was reported.", "filing-1", "Revenue was reported")
    assert verify_citation(claim, [passage]).verified
    wrong_source = Claim(claim.text, "other-filing", claim.cited_passage)
    assert not verify_citation(wrong_source, [passage]).verified

