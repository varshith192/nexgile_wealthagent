"""Goal funding, forecasting and scenario comparison.

Scenarios are read-only projections: they never write back to books of record.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from app.calculations.base import CalcResult, money, pct, safe_div

MONTHS_PER_YEAR = 12


def months_between(start: date, end: date) -> int:
    return max((end.year - start.year) * 12 + (end.month - start.month), 0)


def future_value(present_value: float, monthly_contribution: float, annual_return: float, months: int) -> float:
    """FV of a lump sum plus an ordinary annuity of monthly contributions."""
    if months <= 0:
        return present_value
    monthly_rate = annual_return / MONTHS_PER_YEAR
    if abs(monthly_rate) < 1e-12:
        return present_value + monthly_contribution * months
    growth = (1 + monthly_rate) ** months
    return present_value * growth + monthly_contribution * (growth - 1) / monthly_rate


def required_monthly_contribution(
    present_value: float, target: float, annual_return: float, months: int
) -> float:
    """Contribution needed to close the gap by the target date."""
    if months <= 0:
        return max(target - present_value, 0.0)
    monthly_rate = annual_return / MONTHS_PER_YEAR
    if abs(monthly_rate) < 1e-12:
        return max((target - present_value) / months, 0.0)
    growth = (1 + monthly_rate) ** months
    shortfall = target - present_value * growth
    if shortfall <= 0:
        return 0.0
    return shortfall * monthly_rate / (growth - 1)


def _status_for(funded_ratio: float) -> str:
    if funded_ratio >= 1.0:
        return "on_track"
    if funded_ratio >= 0.9:
        return "monitor"
    if funded_ratio >= 0.7:
        return "at_risk"
    return "off_track"


def project_goal(goal: dict[str, Any], as_of: date) -> CalcResult:
    """Forecast a goal to its target date and classify funding status."""
    current = float(goal.get("current_amount") or 0.0)
    target = float(goal.get("target_amount") or 0.0)
    contribution = float(goal.get("monthly_contribution") or 0.0)
    annual_return = float(goal.get("expected_return") or 0.06)
    inflation = float(goal.get("inflation_rate") or 0.0)
    target_date: date = goal["target_date"]

    months = months_between(as_of, target_date)
    years = months / MONTHS_PER_YEAR

    # A target expressed in today's dollars is grown to the target date.
    inflated_target = target * ((1 + inflation) ** years) if inflation else target
    projected = future_value(current, contribution, annual_return, months)
    gap = projected - inflated_target
    funded_ratio = safe_div(projected, inflated_target)
    required = required_monthly_contribution(current, inflated_target, annual_return, months)

    return CalcResult(
        method=(
            "future_value = pv x (1+r/12)^n + pmt x ((1+r/12)^n - 1) / (r/12); "
            "target inflated at the stated rate over the horizon"
        ),
        as_of=as_of,
        inputs={
            "current_amount": money(current),
            "target_amount": money(target),
            "monthly_contribution": money(contribution),
            "expected_return": annual_return,
            "inflation_rate": inflation,
            "months_to_target": months,
            "target_date": target_date.isoformat(),
        },
        assumptions=[
            f"A constant {annual_return:.2%} nominal annual return, compounded monthly.",
            f"Contributions of {contribution:,.0f} per month continue uninterrupted until the target date.",
            f"The target grows with {inflation:.2%} annual inflation." if inflation else "The target is a nominal amount.",
        ],
        limitations=[
            "This is a deterministic projection, not a guarantee, and assumes no sequence-of-returns risk.",
            "Taxes, fees and withdrawals before the target date are not modelled here.",
            "Actual markets vary year to year; a single average return understates the range of outcomes.",
        ],
        result={
            "projected_value": money(projected),
            "inflation_adjusted_target": money(inflated_target),
            "gap": money(gap),
            "funded_ratio": pct(min(funded_ratio, 5.0)),
            "progress_percent": pct(min(safe_div(current, inflated_target), 1.0)),
            "status": _status_for(funded_ratio),
            "required_monthly_contribution": money(required),
            "additional_monthly_needed": money(max(required - contribution, 0.0)),
            "months_to_target": months,
            "years_to_target": round(years, 1),
        },
    )


SCENARIO_LIBRARY: dict[str, dict[str, Any]] = {
    "base_case": {
        "label": "Base Case",
        "description": "Current plan with no changes.",
        "adjustments": {},
    },
    "higher_savings": {
        "label": "Higher Savings",
        "description": "Monthly contribution increased by 20%.",
        "adjustments": {"contribution_multiplier": 1.20},
    },
    "lower_return": {
        "label": "Lower Return",
        "description": "Expected return reduced by 150 basis points.",
        "adjustments": {"return_delta": -0.015},
    },
    "earlier_retirement": {
        "label": "Earlier Retirement",
        "description": "Target date pulled forward by three years.",
        "adjustments": {"years_earlier": 3},
    },
}


def _apply_adjustments(goal: dict[str, Any], adjustments: dict[str, Any]) -> dict[str, Any]:
    adjusted = dict(goal)
    if "contribution_multiplier" in adjustments:
        adjusted["monthly_contribution"] = float(goal.get("monthly_contribution") or 0.0) * adjustments[
            "contribution_multiplier"
        ]
    if "return_delta" in adjustments:
        adjusted["expected_return"] = max(float(goal.get("expected_return") or 0.06) + adjustments["return_delta"], 0.0)
    if "years_earlier" in adjustments:
        target: date = goal["target_date"]
        adjusted["target_date"] = date(target.year - int(adjustments["years_earlier"]), target.month, target.day)
    if "target_multiplier" in adjustments:
        adjusted["target_amount"] = float(goal.get("target_amount") or 0.0) * adjustments["target_multiplier"]
    return adjusted


def compare_scenarios(
    goal: dict[str, Any], as_of: date, scenario_keys: Sequence[str] | None = None
) -> CalcResult:
    """Run the standard scenario set side by side against the base case."""
    keys = list(scenario_keys or SCENARIO_LIBRARY.keys())
    base = project_goal(goal, as_of)
    rows = []

    for key in keys:
        definition = SCENARIO_LIBRARY.get(key)
        if not definition:
            continue
        adjusted_goal = _apply_adjustments(goal, definition["adjustments"])
        projection = project_goal(adjusted_goal, as_of)
        rows.append(
            {
                "key": key,
                "label": definition["label"],
                "description": definition["description"],
                "is_baseline": key == "base_case",
                "projected_value": projection.result["projected_value"],
                "gap": projection.result["gap"],
                "funded_ratio": projection.result["funded_ratio"],
                "status": projection.result["status"],
                "target_date": adjusted_goal["target_date"].isoformat(),
                "monthly_contribution": money(float(adjusted_goal.get("monthly_contribution") or 0.0)),
                "expected_return": round(float(adjusted_goal.get("expected_return") or 0.0), 4),
                "delta_vs_base": money(
                    projection.result["projected_value"] - base.result["projected_value"]
                ),
                "assumptions": projection.assumptions,
            }
        )

    return CalcResult(
        method="each scenario re-runs the deterministic goal projection with one input changed",
        as_of=as_of,
        inputs={"goal": goal.get("name"), "scenarios": keys},
        assumptions=[
            "Only the inputs named by each scenario change; everything else matches the current plan.",
            "Scenarios are illustrative and are never written back to the books of record.",
        ],
        limitations=[
            "A single average return is used per scenario; real returns vary and order matters.",
            "Scenario results should be reviewed with an advisor before acting.",
        ],
        result={"base": base.result, "scenarios": rows},
    )


def household_goal_summary(goals: Sequence[dict[str, Any]], as_of: date) -> CalcResult:
    """Roll every goal up into a single funding picture."""
    rows = []
    total_target = 0.0
    total_current = 0.0
    off_track = 0

    for goal in goals:
        projection = project_goal(goal, as_of)
        total_target += float(goal.get("target_amount") or 0.0)
        total_current += float(goal.get("current_amount") or 0.0)
        if projection.result["status"] in {"at_risk", "off_track"}:
            off_track += 1
        rows.append(
            {
                "id": goal.get("id"),
                "name": goal.get("name"),
                "goal_type": goal.get("goal_type"),
                "priority": goal.get("priority"),
                "target_amount": money(float(goal.get("target_amount") or 0.0)),
                "current_amount": money(float(goal.get("current_amount") or 0.0)),
                "target_date": goal["target_date"].isoformat(),
                **projection.result,
            }
        )

    return CalcResult(
        method="per-goal deterministic projection, aggregated across the household",
        as_of=as_of,
        inputs={"goal_count": len(rows)},
        assumptions=["Each goal keeps its own return and contribution assumptions."],
        limitations=["Goals are treated independently; shared funding sources are not netted."],
        result={
            "goals": rows,
            "total_target": money(total_target),
            "total_current": money(total_current),
            "overall_progress": pct(safe_div(total_current, total_target)),
            "goals_off_track": off_track,
            "goal_count": len(rows),
        },
    )
