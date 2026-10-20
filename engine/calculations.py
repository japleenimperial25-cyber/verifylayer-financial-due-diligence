"""Small deterministic calculation primitives; inputs must be sourced by callers."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from typing import Sequence

DECIMAL_PRECISION = 34


@dataclass(frozen=True)
class CalculationResult:
    name: str
    value: Decimal
    unit: str
    inputs: tuple[dict, ...]


def _sourced_decimal(item: dict) -> Decimal:
    if not isinstance(item, dict):
        raise ValueError("each financial input must be a mapping")
    if not isinstance(item.get("source_id"), str) or not item["source_id"].strip():
        raise ValueError("each input must preserve a source_id")
    if not isinstance(item.get("quote"), str) or not item["quote"].strip():
        raise ValueError("each input must preserve its source evidence quote")
    if not isinstance(item.get("unit"), str) or not item["unit"].strip():
        raise ValueError("each input must declare a unit")
    if not isinstance(item.get("period"), str) or not item["period"].strip():
        raise ValueError("each input must declare a reporting period")
    try:
        value = Decimal(str(item["value"]))
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("financial input value must be a valid decimal") from exc
    if not value.is_finite():
        raise ValueError("financial input must be finite")
    return value


def sum_values(values: Sequence[dict]) -> CalculationResult:
    if not values:
        raise ValueError("at least one sourced value is required")
    parsed = [_sourced_decimal(item) for item in values]
    unit = values[0]["unit"]
    period = values[0]["period"]
    if any(item["unit"] != unit or item["period"] != period for item in values):
        raise ValueError("values must have matching units and periods")
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        total = sum(parsed, Decimal(0))
    return CalculationResult("sum", total, unit, tuple(dict(value) for value in values))


def percentage_change(current: dict, prior: dict) -> CalculationResult:
    _sourced_decimal(current)
    _sourced_decimal(prior)
    if current["unit"] != prior["unit"]:
        raise ValueError("current and prior values must use the same unit")
    if current["period"] == prior["period"]:
        raise ValueError("current and prior values must identify different reporting periods")
    current_value, prior_value = _sourced_decimal(current), _sourced_decimal(prior)
    if prior_value == 0:
        raise ValueError("percentage change is undefined when prior is zero")
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        change = (current_value - prior_value) / prior_value * Decimal("100")
    return CalculationResult("percentage_change", change, "percent", (dict(current), dict(prior)))


def _same_period_inputs(numerator: dict, denominator: dict) -> tuple[Decimal, Decimal]:
    numerator_value = _sourced_decimal(numerator)
    denominator_value = _sourced_decimal(denominator)
    if numerator["unit"] != denominator["unit"]:
        raise ValueError("ratio inputs must use matching units")
    if numerator["period"] != denominator["period"]:
        raise ValueError("ratio inputs must use the same reporting period")
    if denominator_value == 0:
        raise ValueError("ratio is undefined when denominator is zero")
    return numerator_value, denominator_value


def ratio(numerator: dict, denominator: dict) -> CalculationResult:
    """Calculate a sourced financial ratio (for example current or debt/equity)."""
    top, bottom = _same_period_inputs(numerator, denominator)
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        value = top / bottom
    return CalculationResult("ratio", value, "x", (dict(numerator), dict(denominator)))


def margin(numerator: dict, denominator: dict) -> CalculationResult:
    """Calculate a sourced margin as numerator divided by denominator times 100."""
    top, bottom = _same_period_inputs(numerator, denominator)
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        value = (top / bottom) * Decimal(100)
    return CalculationResult("margin", value, "percent", (dict(numerator), dict(denominator)))
