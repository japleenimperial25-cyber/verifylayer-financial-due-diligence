"""Deterministic financial arithmetic primitives using Decimal."""

from decimal import Decimal
from typing import Iterable

from .models import FinancialValue


def sum_values(values: Iterable[FinancialValue]) -> FinancialValue:
    """Sum compatible values without introducing floating-point rounding."""
    items = list(values)
    if not items:
        raise ValueError("at least one value is required")
    first = items[0]
    if any(item.unit != first.unit or item.period != first.period for item in items):
        raise ValueError("values must have matching units and periods")
    return FinancialValue(sum((item.value for item in items), Decimal("0")), first.unit, first.period)


def percentage_change(current: Decimal, prior: Decimal) -> Decimal:
    """Return percentage change; a zero prior value is undefined."""
    if prior == 0:
        raise ValueError("percentage change is undefined when prior is zero")
    return (current - prior) / prior * Decimal("100")
