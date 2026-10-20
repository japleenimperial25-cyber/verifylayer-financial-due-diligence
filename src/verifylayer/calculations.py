"""Deterministic financial arithmetic primitives using Decimal."""

from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Iterable

from .models import FinancialCalculation, FinancialValue

DECIMAL_PRECISION = 34


def _validate_input(item: FinancialValue) -> None:
    if not isinstance(item, FinancialValue):
        raise ValueError("financial inputs must be FinancialValue instances")
    if not isinstance(item.source_id, str) or not item.source_id.strip():
        raise ValueError("each financial value must preserve a source_id")
    if not isinstance(item.quote, str) or not item.quote.strip():
        raise ValueError("each financial value must preserve its source evidence quote")
    if not isinstance(item.unit, str) or not item.unit.strip():
        raise ValueError("each financial value must declare a unit")
    if not isinstance(item.period, str) or not item.period.strip():
        raise ValueError("each financial value must declare a reporting period")
    if not isinstance(item.value, Decimal) or not item.value.is_finite():
        raise ValueError("financial inputs must be finite Decimal values")


def sum_values(values: Iterable[FinancialValue]) -> FinancialCalculation:
    """Sum compatible, sourced values and retain their provenance."""
    items = list(values)
    if not items:
        raise ValueError("at least one value is required")
    for item in items:
        _validate_input(item)
    first = items[0]
    if any(item.unit != first.unit or item.period != first.period for item in items):
        raise ValueError("values must have matching units and periods")
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        total = sum((item.value for item in items), Decimal("0"))
    return FinancialCalculation(total, first.unit, first.period, tuple(items))


def percentage_change(current: FinancialValue, prior: FinancialValue) -> FinancialCalculation:
    """Return sourced percentage change; a zero prior value is undefined."""
    _validate_input(current)
    _validate_input(prior)
    if current.unit != prior.unit:
        raise ValueError("current and prior values must use the same unit")
    if current.period == prior.period:
        raise ValueError("current and prior values must identify different reporting periods")
    if prior.value == 0:
        raise ValueError("percentage change is undefined when prior is zero")
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        change = (current.value - prior.value) / prior.value * Decimal("100")
    return FinancialCalculation(change, "percent", f"{current.period} vs {prior.period}", (current, prior))
