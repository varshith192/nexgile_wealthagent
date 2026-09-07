"""Plan health, nondiscrimination testing, fee benchmarking and estate math."""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from app.calculations.base import CalcResult, money, pct, safe_div

# 2026 planning figures used across the institutional workspace.
ANNUAL_GIFT_EXCLUSION = 19_000.0
LIFETIME_EXEMPTION = 15_000_000.0
FEDERAL_ESTATE_RATE = 0.40
TOP_HEAVY_THRESHOLD = 0.60


def plan_health(
    *,
    eligible_employees: int,
    participating_employees: int,
    average_deferral_rate: float,
    average_balance: float,
    participants_with_beneficiary: int,
    auto_enrollment: bool,
    auto_escalation: bool,
    as_of: date,
) -> CalcResult:
    """Composite plan health score from five weighted components."""
    participation = safe_div(participating_employees, eligible_employees)
    deferral_component = min(safe_div(average_deferral_rate, 0.10), 1.0)
    balance_component = min(safe_div(average_balance, 150_000.0), 1.0)
    beneficiary_component = safe_div(participants_with_beneficiary, max(participating_employees, 1))
    design_component = (0.5 if auto_enrollment else 0.0) + (0.5 if auto_escalation else 0.0)

    components = {
        "participation": {"value": pct(participation), "weight": 0.30, "score": participation},
        "deferral_rate": {"value": pct(average_deferral_rate), "weight": 0.25, "score": deferral_component},
        "average_balance": {"value": money(average_balance), "weight": 0.20, "score": balance_component},
        "beneficiary_coverage": {"value": pct(beneficiary_component), "weight": 0.15, "score": beneficiary_component},
        "plan_design": {"value": design_component, "weight": 0.10, "score": design_component},
    }
    score = sum(c["score"] * c["weight"] for c in components.values())

    if score >= 0.80:
        grade = "strong"
    elif score >= 0.65:
        grade = "healthy"
    elif score >= 0.50:
        grade = "needs_attention"
    else:
        grade = "at_risk"

    return CalcResult(
        method="weighted score across participation, deferral rate, average balance, beneficiary coverage and plan design",
        as_of=as_of,
        inputs={
            "eligible_employees": eligible_employees,
            "participating_employees": participating_employees,
            "average_deferral_rate": average_deferral_rate,
            "average_balance": money(average_balance),
            "auto_enrollment": auto_enrollment,
            "auto_escalation": auto_escalation,
        },
        assumptions=[
            "A 10% average deferral rate and a $150,000 average balance are treated as full marks.",
            "Component weights reflect the fiduciary review framework used for this demonstration.",
        ],
        limitations=[
            "The score is directional and does not replace an independent plan benchmarking study.",
            "Industry and demographic differences between plans are not adjusted for.",
        ],
        result={
            "score": pct(score),
            "grade": grade,
            "participation_rate": pct(participation),
            "components": components,
        },
    )


def adp_acp_test(
    *, hce_average: float, nhce_average: float, test_type: str, tax_year: int, as_of: date
) -> CalcResult:
    """IRS basic and alternative limits for the ADP/ACP nondiscrimination tests."""
    basic_limit = nhce_average * 1.25
    alternative_limit = min(nhce_average * 2, nhce_average + 0.02)
    limit = max(basic_limit, alternative_limit)
    passed = hce_average <= limit + 1e-9
    excess = max(hce_average - limit, 0.0)

    return CalcResult(
        method="HCE average must not exceed the greater of 1.25x the NHCE average or the lesser of 2x / NHCE + 2%",
        as_of=as_of,
        inputs={
            "test_type": test_type,
            "tax_year": tax_year,
            "hce_average": pct(hce_average),
            "nhce_average": pct(nhce_average),
            "basic_limit": pct(basic_limit),
            "alternative_limit": pct(alternative_limit),
        },
        assumptions=[
            "Current-year testing is used for the NHCE group.",
            "HCE status is determined from the compensation threshold configured in this dataset.",
        ],
        limitations=[
            "The test is illustrative; the recordkeeper's official results govern.",
            "Safe-harbour designs, otherwise-excludable employees and disaggregation are not modelled.",
        ],
        result={
            "result": "pass" if passed else "fail",
            "limit": pct(limit),
            "margin": pct(limit - hce_average),
            "excess_percentage": pct(excess),
            "corrective_action": None
            if passed
            else "Refund excess contributions to HCEs, or make a QNEC to NHCEs, within 2.5 months of plan year end.",
        },
    )


def top_heavy_test(*, key_employee_balances: float, total_plan_assets: float, tax_year: int, as_of: date) -> CalcResult:
    """A plan is top-heavy when key employees hold more than 60% of assets."""
    ratio = safe_div(key_employee_balances, total_plan_assets)
    top_heavy = ratio > TOP_HEAVY_THRESHOLD

    return CalcResult(
        method="top-heavy ratio = key employee account balances / total plan assets, tested against 60%",
        as_of=as_of,
        inputs={
            "key_employee_balances": money(key_employee_balances),
            "total_plan_assets": money(total_plan_assets),
            "threshold": TOP_HEAVY_THRESHOLD,
            "tax_year": tax_year,
        },
        assumptions=["Balances are measured at the prior plan-year determination date."],
        limitations=[
            "Rollover balances, terminated participants and related-employer aggregation are not adjusted for.",
            "The recordkeeper's determination governs.",
        ],
        result={
            "ratio": pct(ratio),
            "result": "fail" if top_heavy else "pass",
            "is_top_heavy": top_heavy,
            "corrective_action": "Employer must make a 3% minimum contribution for all non-key employees."
            if top_heavy
            else None,
        },
    )


def fee_benchmark(fees: Sequence[dict[str, Any]], plan_assets: float, participant_count: int, as_of: date) -> CalcResult:
    """All-in plan cost against the peer benchmark, by payer."""
    total = 0.0
    participant_paid = 0.0
    rows = []

    for fee in fees:
        annual = float(fee.get("annual_amount") or 0.0)
        total += annual
        if fee.get("payer") == "participant":
            participant_paid += annual
        bps = float(fee.get("basis_points") or 0.0)
        benchmark_bps = float(fee.get("benchmark_basis_points") or 0.0)
        rows.append(
            {
                "vendor": fee.get("vendor"),
                "fee_type": fee.get("fee_type"),
                "payer": fee.get("payer"),
                "annual_amount": money(annual),
                "basis_points": bps,
                "benchmark_basis_points": benchmark_bps,
                "variance_bps": round(bps - benchmark_bps, 2),
                "above_benchmark": bps > benchmark_bps,
                "annual_savings_opportunity": money(max(bps - benchmark_bps, 0.0) / 10_000 * plan_assets),
                "revenue_sharing": money(float(fee.get("revenue_sharing") or 0.0)),
            }
        )

    all_in_bps = safe_div(total, plan_assets) * 10_000
    rows.sort(key=lambda r: r["annual_savings_opportunity"], reverse=True)

    return CalcResult(
        method="all-in cost = sum(annual fees) / plan assets, expressed in basis points and compared with peer data",
        as_of=as_of,
        inputs={"plan_assets": money(plan_assets), "participant_count": participant_count, "fee_lines": len(rows)},
        assumptions=["Peer benchmarks reflect plans of similar asset size and participant count."],
        limitations=[
            "Indirect compensation and float income may not be fully captured.",
            "Service scope differs between providers; price alone is not a fiduciary conclusion.",
        ],
        result={
            "total_annual_cost": money(total),
            "all_in_basis_points": round(all_in_bps, 2),
            "per_participant_cost": money(safe_div(total, participant_count)),
            "participant_paid": money(participant_paid),
            "sponsor_paid": money(total - participant_paid),
            "total_savings_opportunity": money(sum(r["annual_savings_opportunity"] for r in rows)),
            "lines": rows,
        },
    )


def ips_monitor(options: Sequence[dict[str, Any]], as_of: date) -> CalcResult:
    """Screen the fund lineup against the investment policy statement."""
    rows = []
    for option in options:
        reasons = []
        three_year = float(option.get("three_year_return") or 0.0)
        benchmark = float(option.get("benchmark_three_year") or 0.0)
        percentile = int(option.get("peer_rank_percentile") or 50)
        expense = float(option.get("expense_ratio") or 0.0)
        median_expense = float(option.get("category_median_expense") or 0.0)

        if three_year < benchmark:
            reasons.append(f"Trailing 3-year return {three_year:.2%} is below the benchmark {benchmark:.2%}.")
        if percentile > 50:
            reasons.append(f"Peer rank in the {percentile}th percentile is below median.")
        if expense > median_expense:
            reasons.append(f"Expense ratio {expense:.2%} exceeds the category median {median_expense:.2%}.")

        status = "pass" if not reasons else ("watch" if len(reasons) < 3 else "replace")
        rows.append(
            {
                "id": option.get("id"),
                "name": option.get("name"),
                "ticker": option.get("ticker"),
                "asset_category": option.get("asset_category"),
                "three_year_return": three_year,
                "benchmark_three_year": benchmark,
                "excess_return": round(three_year - benchmark, 4),
                "peer_rank_percentile": percentile,
                "expense_ratio": expense,
                "category_median_expense": median_expense,
                "plan_assets": money(float(option.get("plan_assets") or 0.0)),
                "participants_invested": option.get("participants_invested"),
                "is_qdia": bool(option.get("is_qdia")),
                "ips_status": status,
                "reasons": reasons,
            }
        )

    watch = [r for r in rows if r["ips_status"] != "pass"]

    return CalcResult(
        method="each option is screened on trailing return vs benchmark, peer rank and expense ratio vs category median",
        as_of=as_of,
        inputs={"options_reviewed": len(rows), "criteria": ["3yr vs benchmark", "peer rank <= 50th", "expense <= median"]},
        assumptions=["The IPS criteria configured for this plan apply uniformly across asset categories."],
        limitations=[
            "Quantitative screens do not capture manager changes, strategy drift or capacity constraints.",
            "A watch status is a prompt for committee discussion, not an automatic replacement.",
        ],
        result={
            "options": rows,
            "pass_count": len(rows) - len(watch),
            "watch_count": sum(1 for r in watch if r["ips_status"] == "watch"),
            "replace_count": sum(1 for r in watch if r["ips_status"] == "replace"),
            "compliant": not watch,
        },
    )


def estate_projection(
    *,
    gross_estate: float,
    liabilities: float,
    lifetime_gifts_used: float,
    charitable_bequests: float,
    is_married: bool,
    as_of: date,
) -> CalcResult:
    """Federal estate tax estimate and the value passing to heirs."""
    net_estate = max(gross_estate - liabilities - charitable_bequests, 0.0)
    exemption = LIFETIME_EXEMPTION * (2 if is_married else 1) - lifetime_gifts_used
    taxable = max(net_estate - exemption, 0.0)
    federal_tax = taxable * FEDERAL_ESTATE_RATE

    return CalcResult(
        method="taxable estate = gross estate - liabilities - charitable bequests - available exemption; taxed at 40%",
        as_of=as_of,
        inputs={
            "gross_estate": money(gross_estate),
            "liabilities": money(liabilities),
            "charitable_bequests": money(charitable_bequests),
            "lifetime_gifts_used": money(lifetime_gifts_used),
            "exemption_per_person": LIFETIME_EXEMPTION,
            "is_married": is_married,
        },
        assumptions=[
            f"A federal exemption of ${LIFETIME_EXEMPTION:,.0f} per person applies, portable between spouses.",
            f"A flat {FEDERAL_ESTATE_RATE:.0%} federal rate is applied to the taxable estate.",
            "Charitable bequests are fully deductible.",
        ],
        limitations=[
            "State estate and inheritance taxes are not included and vary considerably by jurisdiction.",
            "The exemption is scheduled to change under current law; this uses the figure configured today.",
            "Valuation discounts, trust structures and generation-skipping tax are not modelled.",
            "This is a planning estimate. Consult your estate attorney before acting.",
        ],
        result={
            "gross_estate": money(gross_estate),
            "net_estate": money(net_estate),
            "available_exemption": money(max(exemption, 0.0)),
            "taxable_estate": money(taxable),
            "estimated_federal_tax": money(federal_tax),
            "net_to_heirs": money(net_estate - federal_tax),
            "effective_rate": pct(safe_div(federal_tax, net_estate)),
            "exemption_remaining": money(max(exemption - net_estate, 0.0)),
        },
    )


def charitable_deduction(
    *,
    cash_gifts: float,
    appreciated_gifts_fmv: float,
    appreciated_cost_basis: float,
    adjusted_gross_income: float,
    marginal_rate: float,
    ltcg_rate: float,
    as_of: date,
) -> CalcResult:
    """Deduction value and capital gain avoided by giving appreciated securities."""
    cash_limit = adjusted_gross_income * 0.60
    appreciated_limit = adjusted_gross_income * 0.30

    deductible_cash = min(cash_gifts, cash_limit)
    deductible_appreciated = min(appreciated_gifts_fmv, appreciated_limit)
    carryforward = (cash_gifts - deductible_cash) + (appreciated_gifts_fmv - deductible_appreciated)

    total_deduction = deductible_cash + deductible_appreciated
    tax_savings = total_deduction * marginal_rate
    gain_avoided = max(appreciated_gifts_fmv - appreciated_cost_basis, 0.0)
    capital_gains_saved = gain_avoided * ltcg_rate

    return CalcResult(
        method="deduction limited to 60% of AGI for cash and 30% for appreciated securities; excess carries forward 5 years",
        as_of=as_of,
        inputs={
            "cash_gifts": money(cash_gifts),
            "appreciated_gifts_fmv": money(appreciated_gifts_fmv),
            "appreciated_cost_basis": money(appreciated_cost_basis),
            "adjusted_gross_income": money(adjusted_gross_income),
            "marginal_rate": marginal_rate,
            "ltcg_rate": ltcg_rate,
        },
        assumptions=[
            "The household itemises deductions.",
            "Gifts go to public charities, including a donor-advised fund sponsor.",
            "Appreciated securities have been held longer than one year.",
        ],
        limitations=[
            "State tax benefits and the effect of the standard deduction are not modelled.",
            "Private foundation gifts face lower AGI limits than shown here.",
        ],
        result={
            "total_deduction": money(total_deduction),
            "deductible_cash": money(deductible_cash),
            "deductible_appreciated": money(deductible_appreciated),
            "carryforward": money(carryforward),
            "federal_tax_savings": money(tax_savings),
            "capital_gains_avoided": money(gain_avoided),
            "capital_gains_tax_saved": money(capital_gains_saved),
            "total_benefit": money(tax_savings + capital_gains_saved),
            "net_cost_of_giving": money(cash_gifts + appreciated_gifts_fmv - tax_savings - capital_gains_saved),
        },
    )


def gift_exclusion_usage(gifts: Sequence[dict[str, Any]], tax_year: int, is_married: bool, as_of: date) -> CalcResult:
    """Annual exclusion usage per recipient, and lifetime exemption consumed."""
    per_recipient: dict[str, float] = {}
    lifetime_used = 0.0
    exclusion = ANNUAL_GIFT_EXCLUSION * (2 if is_married else 1)

    for gift in gifts:
        if gift.get("tax_year") != tax_year or gift.get("is_charity"):
            continue
        recipient = str(gift.get("recipient"))
        per_recipient[recipient] = per_recipient.get(recipient, 0.0) + float(gift.get("amount") or 0.0)

    rows = []
    for recipient, amount in sorted(per_recipient.items(), key=lambda kv: kv[1], reverse=True):
        over = max(amount - exclusion, 0.0)
        lifetime_used += over
        rows.append(
            {
                "recipient": recipient,
                "gifted": money(amount),
                "annual_exclusion": money(exclusion),
                "remaining_exclusion": money(max(exclusion - amount, 0.0)),
                "uses_lifetime_exemption": money(over),
            }
        )

    return CalcResult(
        method="gifts per recipient netted against the annual exclusion; the excess consumes lifetime exemption",
        as_of=as_of,
        inputs={
            "tax_year": tax_year,
            "annual_exclusion_per_donor": ANNUAL_GIFT_EXCLUSION,
            "gift_splitting": is_married,
            "recipients": len(rows),
        },
        assumptions=[
            f"An annual exclusion of ${ANNUAL_GIFT_EXCLUSION:,.0f} per donor per recipient applies.",
            "Married couples are assumed to elect gift splitting.",
        ],
        limitations=[
            "Direct tuition and medical payments are unlimited and excluded from this view.",
            "A gift tax return may still be required even when no tax is due.",
        ],
        result={
            "recipients": rows,
            "total_gifted": money(sum(r["gifted"] for r in rows)),
            "lifetime_exemption_used": money(lifetime_used),
            "annual_exclusion_per_recipient": money(exclusion),
        },
    )
