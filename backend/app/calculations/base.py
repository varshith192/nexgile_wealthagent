"""Disclosure envelope for every financial calculation.

§4 of the product spec: the intelligence layer is never the source of truth.
Numbers come from these pure functions, and every one of them publishes its
as-of date, inputs, assumptions, method, result and limitations so the UI can
show its work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class CalcResult:
    """A verified number plus everything needed to defend it."""

    method: str
    result: Any
    as_of: date
    inputs: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    source: str = "nexgile_calculation_engine"
    computed_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "result": self.result,
            "as_of": self.as_of.isoformat(),
            "inputs": self.inputs,
            "assumptions": self.assumptions,
            "limitations": self.limitations,
            "source": self.source,
            "computed_at": self.computed_at.isoformat(),
        }


DEFAULT_LIMITATIONS = [
    "Figures are based on the most recent positions available and are not a custodial statement.",
    "Projections are illustrative, not guaranteed, and do not account for every fee, tax or market event.",
]


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division that returns `default` instead of raising on a zero base."""
    if not denominator:
        return default
    return numerator / denominator


def pct(value: float, digits: int = 4) -> float:
    return round(value, digits)


def money(value: float) -> float:
    """Round to cents. Money is never displayed at full float precision."""
    return round(value + 0.0, 2)
