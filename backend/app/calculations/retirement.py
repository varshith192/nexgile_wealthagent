"""Indian retirement planning: EPF, EPS, NPS, PPF, gratuity and readiness.

The Indian retirement picture is built from statutory pieces rather than a
single account, and each piece has its own rules:

  * EPF   - employee contributes 12% of basic pay; the employer matches 12%, of
            which 8.33% is diverted to EPS (capped at a Rs 15,000 wage) and the
            balance 3.67% goes to EPF. Interest is declared annually by the
            EPFO. Withdrawal is exempt after five years of continuous service.
  * EPS   - the pension component. Monthly pension is
            (pensionable salary x pensionable service) / 70, and a member needs
            ten years of service to qualify.
  * NPS   - Tier I is locked to age 60. At exit at least 40% of the corpus must
            buy an annuity; the remaining 60% is withdrawn tax free.
  * PPF   - Rs 1,50,000 a year, fifteen-year term, entirely tax exempt.
  * Gratuity - 15 days of last drawn salary for each completed year of service
            beyond five, statutorily capped at Rs 20,00,000.

There is no Social Security in India, so retirement income is the sum of the
EPS pension, the NPS annuity and drawdown from personal savings.
"""

from __future__ import annotations

import math
import random
from datetime import date
from typing import Any, Sequence

from app.calculations.base import CalcResult, money, pct, safe_div
from app.calculations.goals import future_value

# -- Withdrawal and replacement --------------------------------------------
SAFE_WITHDRAWAL_RATE = 0.04
TARGET_REPLACEMENT_RATIO = 0.75  # Indian households typically need less than 80%

# -- EPF / EPS --------------------------------------------------------------
EPF_EMPLOYEE_RATE = 0.12
EPF_EMPLOYER_RATE = 0.12
EPS_DIVERSION_RATE = 0.0833
EPS_WAGE_CEILING_MONTHLY = 15_000.0
EPS_PENSION_DIVISOR = 70
EPS_MINIMUM_SERVICE_YEARS = 10
EPS_MAX_PENSIONABLE_SERVICE = 35
EPF_INTEREST_RATE = 0.0825
EPF_TAX_FREE_SERVICE_YEARS = 5

# -- NPS --------------------------------------------------------------------
NPS_EXIT_AGE = 60
NPS_MIN_ANNUITY_SHARE = 0.40
NPS_TAX_FREE_LUMP_SHARE = 0.60
NPS_MAX_EQUITY_UNDER_50 = 0.75
TYPICAL_ANNUITY_RATE = 0.062  # indicative immediate annuity yield

# -- PPF --------------------------------------------------------------------
PPF_ANNUAL_LIMIT = 1_50_000.0
PPF_TERM_YEARS = 15
PPF_INTEREST_RATE = 0.071

# -- Gratuity ---------------------------------------------------------------
GRATUITY_DAYS_PER_YEAR = 15
GRATUITY_MONTH_DAYS = 26
GRATUITY_CAP = 20_00_000.0
GRATUITY_MIN_SERVICE_YEARS = 5

# -- Ages -------------------------------------------------------------------
EPF_RETIREMENT_AGE = 58
STANDARD_RETIREMENT_AGE = 60
DEFAULT_LIFE_EXPECTANCY = 85


# ---------------------------------------------------------------------------
# Statutory components
# ---------------------------------------------------------------------------

def epf_projection(
    *,
    current_balance: float,
    monthly_basic: float,
    years_to_retirement: int,
    salary_growth: float,
    interest_rate: float,
    as_of: date,
) -> CalcResult:
    """Project the EPF corpus, splitting employer contributions from EPS."""
    employee_monthly = monthly_basic * EPF_EMPLOYEE_RATE

    # The employer's 12% splits: 8.33% of the capped wage goes to EPS, the rest
    # lands in EPF.
    eps_monthly = min(monthly_basic, EPS_WAGE_CEILING_MONTHLY) * EPS_DIVERSION_RATE
    employer_to_epf_monthly = monthly_basic * EPF_EMPLOYER_RATE - eps_monthly

    balance = current_balance
    total_employee = total_employer = total_eps = total_interest = 0.0
    basic = monthly_basic

    for _year in range(max(years_to_retirement, 0)):
        annual_employee = basic * EPF_EMPLOYEE_RATE * 12
        annual_eps = min(basic, EPS_WAGE_CEILING_MONTHLY) * EPS_DIVERSION_RATE * 12
        annual_employer = basic * EPF_EMPLOYER_RATE * 12 - annual_eps

        opening = balance
        balance += annual_employee + annual_employer
        # Interest accrues on the opening balance plus roughly half a year of
        # contributions, which is close to the EPFO's monthly running balance.
        interest = (opening + (annual_employee + annual_employer) / 2) * interest_rate
        balance += interest

        total_employee += annual_employee
        total_employer += annual_employer
        total_eps += annual_eps
        total_interest += interest
        basic *= 1 + salary_growth

    return CalcResult(
        method=(
            "employee 12% and employer 12% of basic pay, less the 8.33% EPS diversion on the capped wage, "
            "compounded annually at the declared EPFO rate"
        ),
        as_of=as_of,
        inputs={
            "current_balance": money(current_balance),
            "monthly_basic": money(monthly_basic),
            "years_to_retirement": years_to_retirement,
            "salary_growth": salary_growth,
            "interest_rate": interest_rate,
            "eps_wage_ceiling": EPS_WAGE_CEILING_MONTHLY,
        },
        assumptions=[
            f"EPFO interest of {interest_rate:.2%} a year, held constant.",
            f"Basic pay grows {salary_growth:.1%} a year with no break in service.",
            f"EPS diversion is calculated on a wage ceiling of Rs {EPS_WAGE_CEILING_MONTHLY:,.0f} a month.",
            "Contributions continue uninterrupted to retirement.",
        ],
        limitations=[
            "The EPFO revises the interest rate each year; it is not guaranteed.",
            "Partial withdrawals for housing, medical treatment or marriage are not modelled.",
            "A break in service, or a transfer that is not completed, reduces the final corpus.",
        ],
        result={
            "projected_corpus": money(balance),
            "employee_contribution": money(total_employee),
            "employer_contribution": money(total_employer),
            "interest_earned": money(total_interest),
            "eps_diverted": money(total_eps),
            "monthly_employee_contribution": money(employee_monthly),
            "monthly_employer_to_epf": money(employer_to_epf_monthly),
            "monthly_eps_diversion": money(eps_monthly),
        },
    )


def eps_pension(*, pensionable_salary: float, pensionable_service: int, as_of: date) -> CalcResult:
    """Monthly EPS pension: (pensionable salary x service) / 70."""
    eligible = pensionable_service >= EPS_MINIMUM_SERVICE_YEARS
    capped_salary = min(pensionable_salary, EPS_WAGE_CEILING_MONTHLY)
    capped_service = min(pensionable_service, EPS_MAX_PENSIONABLE_SERVICE)
    monthly = (capped_salary * capped_service) / EPS_PENSION_DIVISOR if eligible else 0.0

    return CalcResult(
        method="monthly pension = (pensionable salary x pensionable service) / 70, subject to the wage ceiling",
        as_of=as_of,
        inputs={
            "pensionable_salary": money(pensionable_salary),
            "capped_salary": money(capped_salary),
            "pensionable_service": pensionable_service,
            "wage_ceiling": EPS_WAGE_CEILING_MONTHLY,
            "divisor": EPS_PENSION_DIVISOR,
        },
        assumptions=[
            f"Pensionable salary is the average of the last 60 months, capped at Rs {EPS_WAGE_CEILING_MONTHLY:,.0f}.",
            f"A minimum of {EPS_MINIMUM_SERVICE_YEARS} years of service is required to qualify.",
            f"Pensionable service is counted up to {EPS_MAX_PENSIONABLE_SERVICE} years.",
        ],
        limitations=[
            "Members who opted for pension on higher wages are computed differently.",
            "The pension is not indexed to inflation, so its real value falls every year of retirement.",
            "Commutation and the reduced pension on early exit at 50 are not modelled.",
        ],
        result={
            "monthly_pension": money(monthly),
            "annual_pension": money(monthly * 12),
            "is_eligible": eligible,
            "years_short_of_eligibility": max(EPS_MINIMUM_SERVICE_YEARS - pensionable_service, 0),
        },
    )


def nps_projection(
    *,
    current_balance: float,
    annual_contribution: float,
    current_age: int,
    exit_age: int,
    expected_return: float,
    annuity_rate: float,
    as_of: date,
) -> CalcResult:
    """Project the NPS corpus and split it at exit into lump sum and annuity."""
    years = max(exit_age - current_age, 0)
    corpus = future_value(current_balance, annual_contribution / 12, expected_return, years * 12)

    annuity_portion = corpus * NPS_MIN_ANNUITY_SHARE
    lump_sum = corpus * NPS_TAX_FREE_LUMP_SHARE
    annual_annuity = annuity_portion * annuity_rate

    return CalcResult(
        method=(
            "corpus compounded to the exit age, then split: at least 40% buys an annuity and up to 60% "
            "is withdrawn tax free"
        ),
        as_of=as_of,
        inputs={
            "current_balance": money(current_balance),
            "annual_contribution": money(annual_contribution),
            "current_age": current_age,
            "exit_age": exit_age,
            "expected_return": expected_return,
            "annuity_rate": annuity_rate,
            "minimum_annuity_share": NPS_MIN_ANNUITY_SHARE,
        },
        assumptions=[
            f"A constant {expected_return:.2%} return until exit at age {exit_age}.",
            f"An annuity yielding {annuity_rate:.2%} is purchased with the mandatory 40%.",
            "The 60% lump sum is exempt from tax under current rules.",
            f"Equity allocation is capped at {NPS_MAX_EQUITY_UNDER_50:.0%} under age 50 and tapers thereafter.",
        ],
        limitations=[
            "Annuity rates are set at the point of purchase and will differ from the rate assumed here.",
            "Annuity income is taxed at the slab rate in the year of receipt.",
            "Tier I is locked until 60; premature exit permits only 20% as a lump sum.",
        ],
        result={
            "projected_corpus": money(corpus),
            "lump_sum_tax_free": money(lump_sum),
            "annuity_purchase": money(annuity_portion),
            "annual_annuity_income": money(annual_annuity),
            "monthly_annuity_income": money(annual_annuity / 12),
            "years_to_exit": years,
        },
    )


def ppf_projection(
    *, current_balance: float, annual_contribution: float, years: int, interest_rate: float, as_of: date
) -> CalcResult:
    """PPF corpus. Entirely tax exempt, but capped and illiquid."""
    contribution = min(annual_contribution, PPF_ANNUAL_LIMIT)
    balance = current_balance
    total_interest = 0.0

    for _year in range(max(years, 0)):
        balance += contribution
        interest = balance * interest_rate
        balance += interest
        total_interest += interest

    return CalcResult(
        method="annual contribution added then compounded at the declared PPF rate",
        as_of=as_of,
        inputs={
            "current_balance": money(current_balance),
            "annual_contribution": money(contribution),
            "requested_contribution": money(annual_contribution),
            "annual_limit": PPF_ANNUAL_LIMIT,
            "years": years,
            "interest_rate": interest_rate,
        },
        assumptions=[
            f"Contributions are capped at the statutory Rs {PPF_ANNUAL_LIMIT:,.0f} a year.",
            f"Interest of {interest_rate:.2%}, held constant and credited annually.",
            "Contributions are made early in the financial year so they earn a full year of interest.",
        ],
        limitations=[
            "The rate is reset quarterly by the government and is not guaranteed.",
            f"The account has a {PPF_TERM_YEARS}-year term; withdrawals before then are restricted.",
        ],
        result={
            "projected_corpus": money(balance),
            "total_contributed": money(contribution * max(years, 0)),
            "interest_earned": money(total_interest),
            "contribution_capped": annual_contribution > PPF_ANNUAL_LIMIT,
        },
    )


def gratuity_estimate(*, last_drawn_monthly: float, years_of_service: float, as_of: date) -> CalcResult:
    """Payment of Gratuity Act: 15 days of pay for each completed year."""
    eligible = years_of_service >= GRATUITY_MIN_SERVICE_YEARS
    completed = int(years_of_service)
    raw = (last_drawn_monthly * GRATUITY_DAYS_PER_YEAR * completed) / GRATUITY_MONTH_DAYS if eligible else 0.0
    payable = min(raw, GRATUITY_CAP)

    return CalcResult(
        method="gratuity = last drawn monthly salary x 15 / 26 x completed years of service, capped statutorily",
        as_of=as_of,
        inputs={
            "last_drawn_monthly": money(last_drawn_monthly),
            "years_of_service": round(years_of_service, 2),
            "completed_years": completed,
            "statutory_cap": GRATUITY_CAP,
        },
        assumptions=[
            f"A minimum of {GRATUITY_MIN_SERVICE_YEARS} years of continuous service is required.",
            "Salary means basic plus dearness allowance.",
            "Service beyond six months in the final year counts as a full year for many employers.",
        ],
        limitations=[
            f"Gratuity is exempt from tax up to Rs {GRATUITY_CAP:,.0f}; any excess is taxable.",
            "Employers may pay more than the statutory minimum under their own scheme.",
        ],
        result={
            "gratuity_payable": money(payable),
            "before_cap": money(raw),
            "is_eligible": eligible,
            "capped": raw > GRATUITY_CAP,
        },
    )


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

def retirement_projection(
    *,
    current_age: int,
    retirement_age: int,
    current_savings: float,
    annual_contribution: float,
    employer_contribution: float,
    expected_return: float,
    current_income: float,
    eps_pension_annual: float,
    nps_annuity_annual: float,
    rental_income_annual: float,
    healthcare_annual: float,
    inflation: float,
    as_of: date,
    life_expectancy: int = DEFAULT_LIFE_EXPECTANCY,
) -> CalcResult:
    """Project retirement income against the replacement target."""
    years = max(retirement_age - current_age, 0)
    months = years * 12
    monthly_contribution = (annual_contribution + employer_contribution) / 12

    projected_corpus = future_value(current_savings, monthly_contribution, expected_return, months)
    drawdown_income = projected_corpus * SAFE_WITHDRAWAL_RATE
    total_income = drawdown_income + eps_pension_annual + nps_annuity_annual + rental_income_annual
    net_income = total_income - healthcare_annual

    target_today = current_income * TARGET_REPLACEMENT_RATIO
    target_future = target_today * ((1 + inflation) ** years)

    gap = net_income - target_future
    replacement_ratio = safe_div(net_income, current_income * ((1 + inflation) ** years))

    guaranteed = eps_pension_annual + nps_annuity_annual + rental_income_annual
    required_corpus = max(target_future + healthcare_annual - guaranteed, 0.0) / SAFE_WITHDRAWAL_RATE
    corpus_gap = required_corpus - projected_corpus

    additional_annual = 0.0
    if corpus_gap > 0 and months > 0:
        monthly_rate = expected_return / 12
        growth = (1 + monthly_rate) ** months
        additional_monthly = corpus_gap * monthly_rate / (growth - 1) if monthly_rate else corpus_gap / months
        additional_annual = additional_monthly * 12

    readiness_score = min(max(safe_div(net_income, target_future), 0.0), 1.5)

    return CalcResult(
        method=(
            "personal corpus compounded monthly and drawn at 4%, added to the EPS pension, the NPS annuity and "
            f"any rental income, then compared with {TARGET_REPLACEMENT_RATIO:.0%} of inflation-adjusted "
            "pre-retirement income"
        ),
        as_of=as_of,
        inputs={
            "current_age": current_age,
            "retirement_age": retirement_age,
            "years_to_retirement": years,
            "current_savings": money(current_savings),
            "annual_contribution": money(annual_contribution),
            "employer_contribution": money(employer_contribution),
            "expected_return": expected_return,
            "current_income": money(current_income),
            "eps_pension_annual": money(eps_pension_annual),
            "nps_annuity_annual": money(nps_annuity_annual),
            "rental_income_annual": money(rental_income_annual),
            "healthcare_annual": money(healthcare_annual),
            "inflation": inflation,
            "life_expectancy": life_expectancy,
        },
        assumptions=[
            f"A constant {expected_return:.2%} annual return until retirement.",
            f"An initial withdrawal rate of {SAFE_WITHDRAWAL_RATE:.0%}, rising with inflation thereafter.",
            f"A target of {TARGET_REPLACEMENT_RATIO:.0%} income replacement.",
            f"Contributions continue uninterrupted to age {retirement_age}.",
            "The EPS pension is assumed payable in full and is not indexed to inflation.",
        ],
        limitations=[
            "A single average return ignores sequence-of-returns risk near retirement.",
            "Medical inflation in India runs well ahead of general inflation and is a material risk.",
            "There is no state old-age pension to fall back on beyond EPS.",
            "This projection is educational and is not a guarantee of future income.",
        ],
        result={
            "projected_corpus": money(projected_corpus),
            "drawdown_income": money(drawdown_income),
            "eps_pension": money(eps_pension_annual),
            "nps_annuity": money(nps_annuity_annual),
            "rental_income": money(rental_income_annual),
            "guaranteed_income": money(guaranteed),
            "healthcare_costs": money(healthcare_annual),
            "total_projected_income": money(net_income),
            "target_income": money(target_future),
            "income_gap": money(gap),
            "replacement_ratio": pct(replacement_ratio),
            "required_corpus": money(required_corpus),
            "corpus_gap": money(max(corpus_gap, 0.0)),
            "additional_annual_contribution": money(additional_annual),
            "readiness_score": pct(readiness_score),
            "status": "on_track" if gap >= 0 else ("monitor" if replacement_ratio >= 0.70 else "at_risk"),
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
    # reaching the corpus the plan actually needs.
    if success_threshold and success_threshold > 0:
        successes = sum(1 for balance in endings if balance >= success_threshold)
        success_rate = safe_div(successes, trials)
        success_basis = f"ending corpus of at least Rs {success_threshold:,.0f}"
    else:
        successes = trials - depleted
        success_rate = safe_div(successes, trials)
        success_basis = "corpus not depleted before the end of the horizon"

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
            "Success is measured against the corpus the plan requires, where one is supplied.",
        ],
        limitations=[
            "Real markets show fat tails and serial correlation that this model does not reproduce.",
            "Taxes, fees and changes in behaviour during a downturn are not modelled.",
            "A success probability describes the model, not the market.",
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
    *,
    age: int,
    monthly_basic: float,
    epf_rate: float,
    ppf_contributed: float,
    nps_contributed: float,
    elss_contributed: float,
    as_of: date,
) -> CalcResult:
    """Remaining room in each tax-advantaged wrapper this financial year."""
    epf_annual = monthly_basic * epf_rate * 12
    ppf_room = max(PPF_ANNUAL_LIMIT - ppf_contributed, 0.0)

    # Section 80C is shared: EPF, PPF and ELSS all draw on the same ceiling.
    eighty_c_used = epf_annual + ppf_contributed + elss_contributed
    eighty_c_room = max(1_50_000.0 - eighty_c_used, 0.0)

    # Section 80CCD(1B) is an additional Rs 50,000 for NPS only.
    nps_room = max(50_000.0 - nps_contributed, 0.0)

    return CalcResult(
        method=(
            "section 80C headroom = Rs 1,50,000 less EPF, PPF and ELSS already contributed; "
            "section 80CCD(1B) adds a separate Rs 50,000 for NPS"
        ),
        as_of=as_of,
        inputs={
            "age": age,
            "monthly_basic": money(monthly_basic),
            "epf_rate": epf_rate,
            "epf_annual": money(epf_annual),
            "ppf_contributed": money(ppf_contributed),
            "nps_contributed": money(nps_contributed),
            "elss_contributed": money(elss_contributed),
            "financial_year": f"{as_of.year if as_of.month >= 4 else as_of.year - 1}-"
            f"{str((as_of.year if as_of.month >= 4 else as_of.year - 1) + 1)[-2:]}",
        },
        assumptions=[
            "The employee's own EPF contribution counts toward section 80C; the employer's does not.",
            f"PPF is capped at Rs {PPF_ANNUAL_LIMIT:,.0f} a year across all accounts held by the taxpayer.",
            "These deductions are available only under the old tax regime.",
        ],
        limitations=[
            "ELSS carries a three-year lock-in and PPF a fifteen-year term.",
            "NPS Tier I is locked until age 60 and requires annuitisation of at least 40% at exit.",
        ],
        result={
            "section_80c_limit": 1_50_000.0,
            "section_80c_used": money(eighty_c_used),
            "section_80c_room": money(eighty_c_room),
            "section_80ccd_1b_limit": 50_000.0,
            "section_80ccd_1b_used": money(nps_contributed),
            "section_80ccd_1b_room": money(nps_room),
            "ppf_room": money(ppf_room),
            "epf_annual": money(epf_annual),
            "total_room": money(eighty_c_room + nps_room),
            "fully_used": eighty_c_room <= 0 and nps_room <= 0,
        },
    )


def vesting_status(*, hire_date: date, as_of: date, scheme: str = "eps") -> CalcResult:
    """Service-linked entitlements: EPS eligibility and gratuity eligibility.

    Indian statutory benefits do not vest on a graded schedule the way an
    employer match does elsewhere. The employee's own EPF contributions are
    theirs from day one; what service buys is *eligibility* for the EPS pension
    at ten years and for gratuity at five.
    """
    years_of_service = (as_of - hire_date).days / 365.25

    eps_eligible = years_of_service >= EPS_MINIMUM_SERVICE_YEARS
    gratuity_eligible = years_of_service >= GRATUITY_MIN_SERVICE_YEARS

    return CalcResult(
        method="years of service measured from the hire date against the statutory eligibility thresholds",
        as_of=as_of,
        inputs={
            "hire_date": hire_date.isoformat(),
            "years_of_service": round(years_of_service, 2),
            "eps_threshold": EPS_MINIMUM_SERVICE_YEARS,
            "gratuity_threshold": GRATUITY_MIN_SERVICE_YEARS,
        },
        assumptions=[
            "Service is measured in elapsed years from the hire date with no break.",
            "EPF contributions belong to the employee from the first contribution; only EPS and gratuity "
            "require qualifying service.",
        ],
        limitations=[
            "A break in service, or an EPF transfer that was never completed, can reset the clock.",
            "Service with previous employers counts only if the EPF account was transferred, not withdrawn.",
        ],
        result={
            # Kept for interface compatibility with the shared readiness views:
            # the employee's own corpus is always fully theirs.
            "vested_percentage": 1.0,
            "years_of_service": round(years_of_service, 2),
            "schedule": "EPF fully vested; EPS at 10 years; gratuity at 5 years",
            "fully_vested": True,
            "eps_eligible": eps_eligible,
            "gratuity_eligible": gratuity_eligible,
            "years_to_eps": max(EPS_MINIMUM_SERVICE_YEARS - years_of_service, 0.0),
            "years_to_gratuity": max(GRATUITY_MIN_SERVICE_YEARS - years_of_service, 0.0),
            "epf_tax_free": years_of_service >= EPF_TAX_FREE_SERVICE_YEARS,
        },
    )
