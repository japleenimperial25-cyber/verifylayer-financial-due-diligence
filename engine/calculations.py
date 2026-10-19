"""Small deterministic calculation primitives; inputs must be sourced by callers."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True)
class CalculationResult:
    name: str
    value: Decimal
    unit: str
    inputs: tuple[dict, ...]


def _sourced_decimal(item: dict) -> Decimal:
    if not item.get("source_id"):
        raise ValueError("each input must preserve a source_id")
    value = Decimal(str(item["value"]))
    if not value.is_finite():
        raise ValueError("financial input must be finite")
    return value


def sum_values(values: Sequence[dict]) -> CalculationResult:
    if not values:
        raise ValueError("at least one sourced value is required")
    unit = values[0]["unit"]
    period = values[0].get("period")
    if any(item["unit"] != unit or item.get("period") != period for item in values):
        raise ValueError("values must have matching units and periods")
    parsed = [_sourced_decimal(item) for item in values]
    return CalculationResult("sum", sum(parsed, Decimal(0)), unit, tuple(dict(value) for value in values))


def percentage_change(current: dict, prior: dict) -> CalculationResult:
    if current["unit"] != prior["unit"]:
        raise ValueError("current and prior values must use the same unit")
    current_value, prior_value = _sourced_decimal(current), _sourced_decimal(prior)
    if prior_value == 0:
        raise ValueError("percentage change is undefined when prior is zero")
    return CalculationResult("percentage_change", (current_value - prior_value) / prior_value * 100,
                             "percent", (dict(current), dict(prior)))
