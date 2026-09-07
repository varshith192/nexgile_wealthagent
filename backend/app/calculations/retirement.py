"""Retirement readiness, income replacement and Monte-Carlo-style projections."""

from __future__ import annotations

import math
import random
from datetime import date
from typing import Any, Sequence

from app.calculations.base import CalcResult, money, pct, safe_div
from app.calculations.goals import future_value

SAFE_WITHDRAWAL_RATE = 0.04
TARGET_REPLACEMENT_RATIO = 0.80
# 402(g) elective deferral and catch-up limits used by the participant portal.
DEFERRAL_LIMIT = 24_500.0
CATCHUP_LIMIT = 8_000.0
CATCHUP_AGE = 50


def retirement_projection(
    *,
    current_age: int,
    retirement_age: int,
    current_savings: float,
    annual_contribution: float,
    employer_match: float,
    expected_return: float,
    current_income: float,
    social_security_annual: float,
    other_income_annual: float,
    healthcare_annual: float,
    inflation: float,
    as_of: date,
    life_expectancy: int = 92,
) -> CalcResult:
    """Project retirement income and compare it against the replacement target."""
    years = max(retirement_age - current_age, 0)
    months = years * 12
    monthly_contribution = (annual_contribution + employer_match) / 12

    projected_balance = future_value(current_savings, monthly_contribution, expected_return, months)
    portfolio_income = projected_balance * SAFE_WITHDRAWAL_RATE
    total_income = portfolio_income + social_security_annual + other_income_annual
    net_income = total_income - healthcare_annual

    # Income need expressed in future dollars at the retirement date.
    target_income_today = current_income * TARGET_REPLACEMENT_RATIO
    target_income_future = target_income_today * ((1 + inflation) ** years)

    gap = net_income - target_income_future
    replacement_ratio = safe_div(net_income, current_income * ((1 + inflation) ** years))

    required_balance = max((target_income_future + healthcare_annual - social_security_annual - other_income_annual), 0.0) / SAFE_WITHDRAWAL_RATE
    balance_gap = required_balance - projected_balance
    additional_annual = 0.0
    if balance_gap > 0 and months > 0:
        monthly_rate = expected_return / 12
        growth = (1 + monthly_rate) ** months
        additional_monthly = balance_gap * monthly_rate / (growth - 1) if monthly_rate else balance_gap / months
        additional_annual = additional_monthly * 12

    readiness_score = min(max(safe_div(net_income, target_income_future), 0.0), 1.5)

    return CalcResult(
        method=(
            "balance projected with monthly compounding, converted to income at a 4% withdrawal rate, "
            "then compared with 80% of inflation-adjusted pre-retirement income"
        ),
        as_of=as_of,
        inputs={
            "current_age": current_age,
            "retirement_age": retirement_age,
            "years_to_retirement": years,
            "current_savings": money(current_savings),
            "annual_contribution": money(annual_contribution),
            "employer_match": money(employer_match),
            "expected_return": expected_return,
            "current_income": money(current_income),
            "social_security_annual": money(social_security_annual),
            "other_income_annual": money(other_income_annual),
            "healthcare_annual": money(healthcare_annual),
            "inflation": inflation,
            "life_expectancy": life_expectancy,
        },
        assumptions=[
            f"A constant {expected_return:.2%} annual return until retirement.",
            f"A {SAFE_WITHDRAWAL_RATE:.0%} initial withdrawal rate, adjusted for inflation thereafter.",
            f"A target of {TARGET_REPLACEMENT_RATIO:.0%} income replacement.",
            f"Contributions grow with neither raises nor interruptions and continue to age {retirement_age}.",
            "Social Security is assumed payable as estimated with no benefit reduction.",
        ],
        limitations=[
            "A single average return ignores sequence-of-returns risk in the years around retirement.",
            "Long-term care costs, large one-off expenses and legacy objectives are not modelled.",
            "Tax treatment of withdrawals is simplified and varies by account type.",
            "This projection is educational and is not a guarantee of future income.",
        ],
        result={
            "projected_balance": money(projected_balance),
            "portfolio_income": money(portfolio_income),
            "social_security_income": money(social_security_annual),
            "other_income": money(other_income_annual),
            "healthcare_costs": money(healthcare_annual),
            "total_projected_income": money(net_income),
            "target_income": money(target_income_future),
            "income_gap": money(gap),
            "replacement_ratio": pct(replacement_ratio),
            "required_balance": money(required_balance),
            "balance_gap": money(max(balance_gap, 0.0)),
            "additional_annual_contribution": money(additional_annual),
            "readiness_score": pct(readiness_score),
            "status": "on_track" if gap >= 0 else ("monitor" if replacement_ratio >= 0.75 else "at_risk"),
            "years_to_retirement": years,
            "years_in_retirement": max(life_expectancy - retirement_age, 0),
        },
    )


def monte_carlo_projection(
    *,
    starting_balance: float,
    annual_contribution: float,
    years: int,
    expected_return: float,
    volatility: float,
    as_of: date,
    trials: int = 1000,
    seed: int = 42,
    annual_withdrawal: float = 0.0,
    success_threshold: float | None = None,
) -> CalcResult:
    """Distribution of outcomes from a seeded lognormal random walk.

    The seed is fixed so the same inputs always produce the same picture: an
    evaluator refreshing the page must not see the numbers move.
    """
    rng = random.Random(seed)
    endings: list[float] = []
    depleted = 0

    for _ in range(trials):
        balance = starting_balance
        for _year in range(years):
            drift = expected_return - 0.5 * volatility**2
            shock = rng.gauss(0.0, 1.0)
            balance = balance * math.exp(drift + volatility * shock) + annual_contribution - annual_withdrawal
            if balance <= 0:
                balance = 0.0
                depleted += 1
                break
        endings.append(balance)

    endings.sort()

    def percentile(p: float) -> float:
        if not endings:
            return 0.0
        index = min(int(p * (len(endings) - 1)), len(endings) - 1)
        return endings[index]

    median = percentile(0.50)
    deterministic = future_value(starting_balance, annual_contribution / 12, expected_return, years * 12)

    # During accumulation a balance rarely hits zero, so "success" must mean
    # reaching the balance the plan actually needs, not merely surviving.
    if success_threshold and success_threshold > 0:
        successes = sum(1 for balance in endings if balance >= success_threshold)
        success_rate = safe_div(successes, trials)
        success_basis = f"ending balance of at least {success_threshold:,.0f}"
    else:
        successes = trials - depleted
        success_rate = safe_div(successes, trials)
        success_basis = "portfolio not depleted before the end of the horizon"

    return CalcResult(
        method="seeded lognormal random walk; balances rolled forward annually with contributions and withdrawals",
        as_of=as_of,
        inputs={
            "starting_balance": money(starting_balance),
            "annual_contribution": money(annual_contribution),
            "annual_withdrawal": money(annual_withdrawal),
            "years": years,
            "expected_return": expected_return,
            "volatility": volatility,
            "trials": trials,
            "random_seed": seed,
        },
        assumptions=[
            "Returns are lognormally distributed and independent from year to year.",
            f"The simulation uses a fixed random seed ({seed}) so results are reproducible.",
            "Contributions and withdrawals occur once a year, at year end.",
            "Success is measured against the balance the plan requires, where one is supplied.",
        ],
        limitations=[
            "Real markets show fat tails and serial correlation that this model does not reproduce.",
            "Taxes, fees and changes in behaviour during a downturn are not modelled.",
            "A success probability is not a promise; it describes the model, not the market.",
        ],
        result={
            "trials": trials,
            "success_rate": pct(success_rate),
            "success_basis": success_basis,
            "success_threshold": money(success_threshold) if success_threshold else None,
            "successful_trials": successes,
            "depletion_count": depleted,
            "percentiles": {
                "p10": money(percentile(0.10)),
                "p25": money(percentile(0.25)),
                "p50": money(median),
                "p75": money(percentile(0.75)),
                "p90": money(percentile(0.90)),
            },
            "median_ending_balance": money(median),
            "deterministic_projection": money(deterministic),
        },
    )


def contribution_capacity(
    *, age: int, salary: float, deferral_rate: float, ytd_deferral: float, as_of: date
) -> CalcResult:
    """How much room is left under the elective deferral limit this year."""
    catchup_eligible = age >= CATCHUP_AGE
    limit = DEFERRAL_LIMIT + (CATCHUP_LIMIT if catchup_eligible else 0.0)
    projected = salary * deferral_rate
    remaining = max(limit - ytd_deferral, 0.0)

    return CalcResult(
        method="remaining capacity = statutory elective deferral limit (plus catch-up if eligible) - deferrals to date",
        as_of=as_of,
        inputs={
            "age": age,
            "salary": money(salary),
            "deferral_rate": deferral_rate,
            "ytd_deferral": money(ytd_deferral),
            "deferral_limit": DEFERRAL_LIMIT,
            "catchup_limit": CATCHUP_LIMIT,
        },
        assumptions=[
            f"Catch-up contributions become available at age {CATCHUP_AGE}.",
            "Limits shown are the plan-year figures configured for this demonstration dataset.",
        ],
        limitations=[
            "Deferrals to a plan at a previous employer this year are not visible to this platform.",
            "The overall annual additions limit and after-tax contributions are not modelled.",
        ],
        result={
            "annual_limit": money(limit),
            "catchup_eligible": catchup_eligible,
            "catchup_amount": money(CATCHUP_LIMIT if catchup_eligible else 0.0),
            "projected_deferral": money(projected),
            "ytd_deferral": money(ytd_deferral),
            "remaining_capacity": money(remaining),
            "on_pace_to_max": projected >= limit,
            "required_rate_to_max": pct(safe_div(limit, salary)),
        },
    )


def vesting_status(*, hire_date: date, schedule: str, as_of: date) -> CalcResult:
    """Vested percentage of employer contributions under a named schedule."""
    years_of_service = (as_of - hire_date).days / 365.25
    schedule_key = schedule.lower()

    if "cliff" in schedule_key:
        cliff_years = 3
        for token in schedule_key.split():
            if token[0].isdigit():
                cliff_years = int(token[0])
                break
        vested = 1.0 if years_of_service >= cliff_years else 0.0
        detail = f"{cliff_years}-year cliff"
    elif "graded" in schedule_key:
        steps = [(2, 0.20), (3, 0.40), (4, 0.60), (5, 0.80), (6, 1.00)]
        vested = 0.0
        for years_required, percentage in steps:
            if years_of_service >= years_required:
                vested = percentage
        detail = "6-year graded"
    else:
        vested = 1.0
        detail = "immediate"

    return CalcResult(
        method="years of service measured from hire date, mapped onto the plan vesting schedule",
        as_of=as_of,
        inputs={"hire_date": hire_date.isoformat(), "schedule": schedule, "years_of_service": round(years_of_service, 2)},
        assumptions=["Service is measured in elapsed years from the hire date with no breaks in service."],
        limitations=["Breaks in service, rehires and plan amendments can change the vested percentage."],
        result={
            "vested_percentage": pct(vested),
            "years_of_service": round(years_of_service, 2),
            "schedule": detail,
            "fully_vested": vested >= 1.0,
        },
    )
