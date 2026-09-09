"""Indian institutional and estate calculations.

Covers the employer's side of retirement provision (EPF/EPS/NPS Corporate),
statutory compliance under the EPF & MP Act, scheme monitoring, succession
planning and charitable giving.

Two things differ sharply from other jurisdictions and are modelled as they
actually are, not mapped onto foreign equivalents:

  * **India has no estate or inheritance tax.** Estate duty was abolished in
    1985. Succession planning is therefore about *clarity and control* — a
    valid will, correct nominations, HUF partition, trust structures — rather
    than about reducing a tax on death. The product says so plainly instead of
    inventing a liability.

  * **A nominee is not an heir.** Under Indian law a nominee receives the asset
    as a trustee for the legal heirs; the will or the applicable succession law
    decides who ultimately owns it. Getting this wrong is one of the most common
    and most expensive planning errors, so the product flags it directly.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from app.calculations.base import CalcResult, money, pct, safe_div

# -- EPF / EPS statutory parameters -----------------------------------------
EPF_WAGE_CEILING_MONTHLY = 15_000.0
EPF_EMPLOYEE_RATE = 0.12
EPF_EMPLOYER_RATE = 0.12
EPS_DIVERSION_RATE = 0.0833
EPF_ADMIN_CHARGE_RATE = 0.005      # employer's administrative charge
EDLI_RATE = 0.005                  # Employees Deposit Linked Insurance
ECR_DUE_DAY = 15                   # monthly Electronic Challan cum Return
EPF_INTEREST_RATE = 0.0825

# -- Gift tax, section 56(2)(x) ---------------------------------------------
GIFT_EXEMPT_THRESHOLD = 50_000.0   # from non-relatives, per financial year

# -- Section 80G -------------------------------------------------------------
SECTION_80G_AGI_CAP = 0.10         # qualifying limit for capped categories
CSR_TURNOVER_RATE = 0.02           # section 135 CSR obligation


# ---------------------------------------------------------------------------
# Plan health
# ---------------------------------------------------------------------------

def plan_health(
    *,
    eligible_employees: int,
    enrolled_employees: int,
    average_contribution_rate: float,
    average_balance: float,
    members_with_nomination: int,
    uan_seeded: int,
    nps_corporate_offered: bool,
    voluntary_pf_offered: bool,
    as_of: date,
) -> CalcResult:
    """Composite health score for an employer-sponsored retirement programme.

    EPF enrolment is statutory for eligible employees, so coverage should be
    near total. The score therefore weights the things an employer can actually
    influence: nomination coverage, UAN/KYC hygiene, voluntary savings above
    the statutory minimum, and whether an NPS Corporate tier is offered at all.
    """
    coverage = safe_div(enrolled_employees, eligible_employees)
    contribution_component = min(safe_div(average_contribution_rate, 0.18), 1.0)
    balance_component = min(safe_div(average_balance, 15_00_000.0), 1.0)
    nomination_component = safe_div(members_with_nomination, max(enrolled_employees, 1))
    kyc_component = safe_div(uan_seeded, max(enrolled_employees, 1))
    design_component = (0.5 if nps_corporate_offered else 0.0) + (0.5 if voluntary_pf_offered else 0.0)

    components = {
        "statutory_coverage": {"value": pct(coverage), "weight": 0.25, "score": coverage},
        "contribution_rate": {"value": pct(average_contribution_rate), "weight": 0.20, "score": contribution_component},
        "average_balance": {"value": money(average_balance), "weight": 0.15, "score": balance_component},
        "nomination_coverage": {"value": pct(nomination_component), "weight": 0.20, "score": nomination_component},
        "uan_kyc_seeding": {"value": pct(kyc_component), "weight": 0.10, "score": kyc_component},
        "programme_design": {"value": design_component, "weight": 0.10, "score": design_component},
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
        method=(
            "weighted score across statutory coverage, contribution rate, average balance, nomination "
            "coverage, UAN/KYC seeding and programme design"
        ),
        as_of=as_of,
        inputs={
            "eligible_employees": eligible_employees,
            "enrolled_employees": enrolled_employees,
            "average_contribution_rate": average_contribution_rate,
            "average_balance": money(average_balance),
            "nps_corporate_offered": nps_corporate_offered,
            "voluntary_pf_offered": voluntary_pf_offered,
        },
        assumptions=[
            "An 18% total contribution rate and a Rs 15,00,000 average balance are treated as full marks.",
            "EPF enrolment is statutory, so coverage below 100% indicates a compliance gap rather than a choice.",
            "Component weights reflect the review framework used for this demonstration.",
        ],
        limitations=[
            "The score is directional and does not replace an EPFO compliance audit.",
            "Industry and demographic differences between employers are not adjusted for.",
        ],
        result={
            "score": pct(score),
            "grade": grade,
            "coverage_rate": pct(coverage),
            "nomination_coverage": pct(nomination_component),
            "uan_seeding": pct(kyc_component),
            "components": components,
        },
    )


# ---------------------------------------------------------------------------
# Statutory compliance
# ---------------------------------------------------------------------------

def epf_contribution_check(
    *,
    total_wages: float,
    employee_remitted: float,
    employer_remitted: float,
    eps_remitted: float,
    member_count: int,
    as_of: date,
) -> CalcResult:
    """Reconcile what was remitted against what the Act requires.

    `total_wages` is an annual figure, so the statutory wage ceiling — which
    the Act states monthly, per member — is annualised before it is applied.
    """
    annual_ceiling = EPF_WAGE_CEILING_MONTHLY * 12 * member_count
    expected_employee = total_wages * EPF_EMPLOYEE_RATE
    expected_eps = min(total_wages, annual_ceiling) * EPS_DIVERSION_RATE
    expected_employer = total_wages * EPF_EMPLOYER_RATE - expected_eps
    expected_admin = total_wages * EPF_ADMIN_CHARGE_RATE
    expected_edli = min(total_wages, annual_ceiling) * EDLI_RATE

    employee_variance = employee_remitted - expected_employee
    employer_variance = employer_remitted - expected_employer
    eps_variance = eps_remitted - expected_eps

    tolerance = max(total_wages * 0.001, 100.0)
    compliant = all(abs(v) <= tolerance for v in (employee_variance, employer_variance, eps_variance))

    return CalcResult(
        method=(
            "expected remittance = 12% employee + 12% employer of wages, with 8.33% of the capped wage "
            "diverted to EPS, plus administrative charges and EDLI"
        ),
        as_of=as_of,
        inputs={
            "total_wages": money(total_wages),
            "member_count": member_count,
            "wage_ceiling": EPF_WAGE_CEILING_MONTHLY,
            "tolerance": money(tolerance),
        },
        assumptions=[
            f"EPS diversion is computed on a wage ceiling of Rs {EPF_WAGE_CEILING_MONTHLY:,.0f} per member per month.",
            "All members are covered at the statutory rate with no voluntary excess.",
            "Wages means basic pay plus dearness allowance.",
        ],
        limitations=[
            "International workers and members on higher-wage pension are computed differently.",
            "The EPFO's own reconciliation on the employer portal is the authoritative record.",
            "Damages under section 14B and interest under section 7Q on late payment are not computed here.",
        ],
        result={
            "expected_employee": money(expected_employee),
            "expected_employer": money(expected_employer),
            "expected_eps": money(expected_eps),
            "expected_admin_charges": money(expected_admin),
            "expected_edli": money(expected_edli),
            "employee_variance": money(employee_variance),
            "employer_variance": money(employer_variance),
            "eps_variance": money(eps_variance),
            "total_expected": money(expected_employee + expected_employer + expected_eps + expected_admin + expected_edli),
            "result": "pass" if compliant else "fail",
            "is_compliant": compliant,
            "corrective_action": None
            if compliant
            else "Reconcile the ECR against the wage register and remit the shortfall with interest under section 7Q.",
        },
    )


def ecr_filing_status(*, period_end: date, filed_on: date | None, as_of: date) -> CalcResult:
    """The monthly ECR is due by the 15th of the following month."""
    due_year = period_end.year + (1 if period_end.month == 12 else 0)
    due_month = 1 if period_end.month == 12 else period_end.month + 1
    due_date = date(due_year, due_month, ECR_DUE_DAY)

    if filed_on:
        days_late = max((filed_on - due_date).days, 0)
        status = "complete" if days_late == 0 else "late"
    else:
        days_late = max((as_of - due_date).days, 0)
        status = "overdue" if as_of > due_date else "pending"

    return CalcResult(
        method="the Electronic Challan cum Return is due by the 15th of the month following the wage month",
        as_of=as_of,
        inputs={
            "wage_month_end": period_end.isoformat(),
            "due_date": due_date.isoformat(),
            "filed_on": filed_on.isoformat() if filed_on else None,
        },
        assumptions=["The due date is the 15th of the following month, with no extension applied."],
        limitations=[
            "Late remittance attracts interest under section 7Q and damages under section 14B.",
            "The EPFO employer portal is the authoritative record of filing.",
        ],
        result={
            "due_date": due_date.isoformat(),
            "status": status,
            "days_late": days_late,
            "is_filed": filed_on is not None,
            "on_time": filed_on is not None and days_late == 0,
        },
    )


def nomination_coverage(members: Sequence[dict[str, Any]], as_of: date) -> CalcResult:
    """Nomination coverage across the membership, and why it matters."""
    total = len(members)
    with_nomination = sum(1 for m in members if m.get("has_nomination"))
    with_uan = sum(1 for m in members if m.get("uan_seeded", True))
    with_kyc = sum(1 for m in members if m.get("kyc_complete", True))

    gaps = [
        {
            "member_id": m.get("id"),
            "full_name": m.get("full_name"),
            "balance": money(float(m.get("balance") or 0.0)),
            "reason": "No nomination on file"
            if not m.get("has_nomination")
            else ("UAN not seeded" if not m.get("uan_seeded", True) else "KYC incomplete"),
        }
        for m in members
        if not m.get("has_nomination") or not m.get("uan_seeded", True) or not m.get("kyc_complete", True)
    ]
    gaps.sort(key=lambda row: row["balance"], reverse=True)

    return CalcResult(
        method="members are checked for a filed nomination, a seeded UAN and completed KYC",
        as_of=as_of,
        inputs={"members": total},
        assumptions=["Every member is expected to have a nomination, a seeded UAN and completed KYC."],
        limitations=[
            "A nominee receives the balance as trustee for the legal heirs; the will or succession law "
            "decides final ownership.",
            "Nominations filed on paper before UAN digitisation may not appear on the portal.",
        ],
        result={
            "nomination_coverage": pct(safe_div(with_nomination, total)),
            "uan_seeding": pct(safe_div(with_uan, total)),
            "kyc_completion": pct(safe_div(with_kyc, total)),
            "members_without_nomination": total - with_nomination,
            "gaps": gaps[:25],
            "gap_count": len(gaps),
            "balance_at_risk": money(sum(float(m.get("balance") or 0.0) for m in members if not m.get("has_nomination"))),
        },
    )


# ---------------------------------------------------------------------------
# Scheme monitoring
# ---------------------------------------------------------------------------

def scheme_monitor(options: Sequence[dict[str, Any]], as_of: date) -> CalcResult:
    """Screen the scheme menu against the investment policy.

    For an NPS Corporate tier the pension fund managers are regulated by PFRDA
    and returns are published; for a mutual fund menu the comparison is against
    the scheme benchmark and category median expense.
    """
    rows = []
    for option in options:
        reasons = []
        three_year = float(option.get("three_year_return") or 0.0)
        benchmark = float(option.get("benchmark_three_year") or 0.0)
        percentile = int(option.get("peer_rank_percentile") or 50)
        expense = float(option.get("expense_ratio") or 0.0)
        median_expense = float(option.get("category_median_expense") or 0.0)

        if three_year < benchmark:
            reasons.append(f"Three-year return {three_year:.2%} trails the benchmark {benchmark:.2%}.")
        if percentile > 50:
            reasons.append(f"Peer rank in the {percentile}th percentile is below the category median.")
        if expense > median_expense:
            reasons.append(f"Expense ratio {expense:.2%} exceeds the category median {median_expense:.2%}.")

        status = "pass" if not reasons else ("watch" if len(reasons) < 3 else "replace")
        rows.append(
            {
                "id": option.get("id"),
                "name": option.get("name"),
                "code": option.get("ticker"),
                "asset_category": option.get("asset_category"),
                "three_year_return": three_year,
                "benchmark_three_year": benchmark,
                "excess_return": round(three_year - benchmark, 4),
                "peer_rank_percentile": percentile,
                "expense_ratio": expense,
                "category_median_expense": median_expense,
                "scheme_assets": money(float(option.get("plan_assets") or 0.0)),
                "members_invested": option.get("participants_invested"),
                "is_default": bool(option.get("is_default_scheme")),
                "ips_status": status,
                "reasons": reasons,
            }
        )

    watch = [r for r in rows if r["ips_status"] != "pass"]

    return CalcResult(
        method="each scheme is screened on trailing return against benchmark, peer rank and expense ratio",
        as_of=as_of,
        inputs={
            "schemes_reviewed": len(rows),
            "criteria": ["3yr vs benchmark", "peer rank <= 50th", "expense <= category median"],
        },
        assumptions=[
            "The investment policy criteria configured for this programme apply across all categories.",
            "PFRDA-published NAV history is used for NPS schemes and AMFI data for mutual funds.",
        ],
        limitations=[
            "Quantitative screens miss fund manager changes, strategy drift and capacity constraints.",
            "A watch status is a prompt for committee discussion, not an automatic replacement.",
            "Past performance does not predict future returns.",
        ],
        result={
            "options": rows,
            "pass_count": len(rows) - len(watch),
            "watch_count": sum(1 for r in watch if r["ips_status"] == "watch"),
            "replace_count": sum(1 for r in watch if r["ips_status"] == "replace"),
            "compliant": not watch,
        },
    )


def fee_benchmark(fees: Sequence[dict[str, Any]], plan_assets: float, member_count: int, as_of: date) -> CalcResult:
    """All-in programme cost against peer benchmarks, by payer."""
    total = 0.0
    member_paid = 0.0
    rows = []

    for fee in fees:
        annual = float(fee.get("annual_amount") or 0.0)
        total += annual
        if fee.get("payer") == "participant":
            member_paid += annual
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
        method="all-in cost = sum of annual fees / programme assets, expressed in basis points against peer data",
        as_of=as_of,
        inputs={"plan_assets": money(plan_assets), "member_count": member_count, "fee_lines": len(rows)},
        assumptions=[
            "Peer benchmarks reflect programmes of similar asset size and membership.",
            "EPFO administrative charges are statutory and are shown at the prescribed rate.",
        ],
        limitations=[
            "Indirect compensation and float income may not be fully captured.",
            "Service scope differs between providers; price alone is not a governance conclusion.",
        ],
        result={
            "total_annual_cost": money(total),
            "all_in_basis_points": round(all_in_bps, 2),
            "per_participant_cost": money(safe_div(total, member_count)),
            "participant_paid": money(member_paid),
            "sponsor_paid": money(total - member_paid),
            "total_savings_opportunity": money(sum(r["annual_savings_opportunity"] for r in rows)),
            "lines": rows,
        },
    )


# ---------------------------------------------------------------------------
# Succession
# ---------------------------------------------------------------------------

def succession_review(
    *,
    gross_estate: float,
    liabilities: float,
    assets_with_nomination: float,
    assets_in_trust: float,
    assets_jointly_held: float,
    has_valid_will: bool,
    will_registered: bool,
    is_huf: bool,
    as_of: date,
) -> CalcResult:
    """Succession readiness. India levies no estate or inheritance tax.

    The risk being measured is not tax but *friction*: assets that will need a
    succession certificate or probate, nominations that conflict with the will,
    and an HUF whose partition has never been documented.
    """
    net_estate = max(gross_estate - liabilities, 0.0)

    # Assets that transfer without a court process.
    smooth_transfer = min(assets_with_nomination + assets_in_trust + assets_jointly_held, net_estate)
    requires_process = max(net_estate - smooth_transfer, 0.0)

    findings: list[dict[str, Any]] = []
    if not has_valid_will:
        findings.append(
            {
                "severity": "high",
                "finding": "No valid will on file",
                "detail": (
                    "Without a will the estate devolves under the applicable succession law, which may not "
                    "reflect the family's intentions and typically requires a succession certificate."
                ),
            }
        )
    elif not will_registered:
        findings.append(
            {
                "severity": "low",
                "finding": "Will is not registered",
                "detail": (
                    "Registration is optional in India but makes the will substantially harder to challenge "
                    "and easier to prove."
                ),
            }
        )

    if requires_process > 0:
        findings.append(
            {
                "severity": "medium",
                "finding": "Assets without a nomination or joint holding",
                "detail": (
                    f"Rs {requires_process:,.0f} of the estate has no nomination, joint holder or trust and "
                    "will need a succession certificate or probate before it can be transferred."
                ),
            }
        )

    if has_valid_will and assets_with_nomination > 0:
        findings.append(
            {
                "severity": "medium",
                "finding": "Confirm nominations agree with the will",
                "detail": (
                    "A nominee holds the asset as trustee for the legal heirs; where the nomination and the "
                    "will name different people, the estate is likely to end up in dispute."
                ),
            }
        )

    if is_huf:
        findings.append(
            {
                "severity": "medium",
                "finding": "HUF partition is not documented",
                "detail": (
                    "An undivided HUF continues after the karta's death. A documented partition deed avoids "
                    "disputes between coparceners and clarifies each member's share."
                ),
            }
        )

    readiness = safe_div(smooth_transfer, net_estate) if net_estate else 0.0

    return CalcResult(
        method=(
            "the estate is split between assets that transfer on nomination, joint holding or trust and "
            "assets that will require a succession certificate or probate"
        ),
        as_of=as_of,
        inputs={
            "gross_estate": money(gross_estate),
            "liabilities": money(liabilities),
            "assets_with_nomination": money(assets_with_nomination),
            "assets_in_trust": money(assets_in_trust),
            "assets_jointly_held": money(assets_jointly_held),
            "has_valid_will": has_valid_will,
            "is_huf": is_huf,
        },
        assumptions=[
            "India abolished estate duty in 1985; no tax is payable on inheritance itself.",
            "Assets held with a nomination, jointly, or inside a trust transfer without a court process.",
            "The applicable succession law depends on the family's personal law.",
        ],
        limitations=[
            "Income arising from inherited assets is taxable in the heir's hands from the date of inheritance.",
            "Stamp duty is payable on the transfer of immovable property in most states.",
            "Personal law differs materially between communities; take advice specific to the family.",
            "This is a planning view, not legal advice. Consult an estate lawyer.",
        ],
        result={
            "gross_estate": money(gross_estate),
            "net_estate": money(net_estate),
            "estate_tax_payable": 0.0,
            "smooth_transfer_value": money(smooth_transfer),
            "requires_succession_process": money(requires_process),
            "succession_readiness": pct(readiness),
            "findings": findings,
            "finding_count": len(findings),
            "note": "India levies no estate or inheritance tax. The planning objective is clarity and control, not tax.",
        },
    )


def gift_tax_review(gifts: Sequence[dict[str, Any]], as_of: date) -> CalcResult:
    """Section 56(2)(x): gifts from non-relatives above Rs 50,000 are taxable.

    Gifts between specified relatives are entirely exempt regardless of amount,
    which is the opposite structure to an annual-exclusion system.
    """
    financial_year_start = date(as_of.year if as_of.month >= 4 else as_of.year - 1, 4, 1)
    financial_year_end = date(financial_year_start.year + 1, 3, 31)

    from_relatives = 0.0
    from_non_relatives = 0.0
    rows = []

    for gift in gifts:
        gifted_on = gift.get("gifted_on")
        if not gifted_on or not (financial_year_start <= gifted_on <= financial_year_end):
            continue
        amount = float(gift.get("amount") or 0.0)
        is_relative = bool(gift.get("is_relative", True))
        if is_relative:
            from_relatives += amount
        else:
            from_non_relatives += amount
        rows.append(
            {
                "recipient": gift.get("recipient"),
                "amount": money(amount),
                "gifted_on": gifted_on.isoformat(),
                "is_relative": is_relative,
                "exempt": is_relative,
                "basis": "Exempt — gift between specified relatives"
                if is_relative
                else "Counts toward the Rs 50,000 non-relative threshold",
            }
        )

    # The threshold is all-or-nothing: cross it and the whole amount is taxable.
    taxable = from_non_relatives if from_non_relatives > GIFT_EXEMPT_THRESHOLD else 0.0

    return CalcResult(
        method=(
            "gifts from specified relatives are exempt in full; aggregate gifts from non-relatives above "
            f"Rs {GIFT_EXEMPT_THRESHOLD:,.0f} in a financial year are taxable in full as income from other sources"
        ),
        as_of=as_of,
        inputs={
            "financial_year": f"{financial_year_start.year}-{str(financial_year_start.year + 1)[-2:]}",
            "threshold": GIFT_EXEMPT_THRESHOLD,
            "gifts_considered": len(rows),
        },
        assumptions=[
            "Specified relatives include spouse, siblings, lineal ascendants and descendants, and their spouses.",
            "Gifts received on marriage, under a will, or in contemplation of death are exempt regardless of source.",
        ],
        limitations=[
            "Clubbing provisions under sections 60 to 64 may attribute income back to the giver.",
            "Immovable property gifts are valued at stamp duty value, not the stated consideration.",
            "There is no annual exclusion in India; the test is the relationship, not the amount per recipient.",
        ],
        result={
            "gifts": rows,
            "total_from_relatives": money(from_relatives),
            "total_from_non_relatives": money(from_non_relatives),
            "threshold": GIFT_EXEMPT_THRESHOLD,
            "taxable_amount": money(taxable),
            "threshold_breached": from_non_relatives > GIFT_EXEMPT_THRESHOLD,
            "headroom": money(max(GIFT_EXEMPT_THRESHOLD - from_non_relatives, 0.0)),
        },
    )


# ---------------------------------------------------------------------------
# Charitable giving
# ---------------------------------------------------------------------------

def section_80g_deduction(
    *,
    donations_100_no_cap: float,
    donations_50_no_cap: float,
    donations_100_capped: float,
    donations_50_capped: float,
    adjusted_gross_income: float,
    marginal_rate: float,
    as_of: date,
) -> CalcResult:
    """Section 80G relief across the four donation categories.

    Some approved funds allow 100% deduction without limit, some 50% without
    limit, and the rest are subject to a qualifying limit of 10% of adjusted
    gross total income.
    """
    qualifying_limit = adjusted_gross_income * SECTION_80G_AGI_CAP

    uncapped_deduction = donations_100_no_cap + donations_50_no_cap * 0.50

    # Capped categories share the single 10% qualifying limit.
    capped_total = donations_100_capped + donations_50_capped
    capped_allowed = min(capped_total, qualifying_limit)
    share_100 = safe_div(donations_100_capped, capped_total) if capped_total else 0.0
    capped_deduction = capped_allowed * share_100 + capped_allowed * (1 - share_100) * 0.50

    total_deduction = uncapped_deduction + capped_deduction
    tax_saving = total_deduction * marginal_rate
    total_donated = donations_100_no_cap + donations_50_no_cap + capped_total

    return CalcResult(
        method=(
            "100% and 50% categories without a limit are deducted in full; capped categories share a "
            "qualifying limit of 10% of adjusted gross total income"
        ),
        as_of=as_of,
        inputs={
            "donations_100_no_cap": money(donations_100_no_cap),
            "donations_50_no_cap": money(donations_50_no_cap),
            "donations_100_capped": money(donations_100_capped),
            "donations_50_capped": money(donations_50_capped),
            "adjusted_gross_income": money(adjusted_gross_income),
            "qualifying_limit": money(qualifying_limit),
            "marginal_rate": marginal_rate,
        },
        assumptions=[
            "Section 80G is available only under the old tax regime.",
            "Every donee holds a valid 80G registration and has issued Form 10BE.",
            "Cash donations above Rs 2,000 do not qualify.",
        ],
        limitations=[
            "The deduction is claimed against income; it does not reduce tax rupee for rupee.",
            "Donations to a foreign institution do not qualify.",
            "There is no donor-advised fund structure in India; giving is direct or through a trust or foundation.",
        ],
        result={
            "total_donated": money(total_donated),
            "qualifying_limit": money(qualifying_limit),
            "uncapped_deduction": money(uncapped_deduction),
            "capped_deduction": money(capped_deduction),
            "total_deduction": money(total_deduction),
            "tax_saving": money(tax_saving),
            "net_cost_of_giving": money(total_donated - tax_saving),
            "deduction_rate": pct(safe_div(total_deduction, total_donated)),
            "capped_donations_disallowed": money(max(capped_total - capped_allowed, 0.0)),
        },
    )


def csr_obligation(*, average_net_profit: float, spent: float, as_of: date) -> CalcResult:
    """Section 135: 2% of average net profit for companies above the thresholds."""
    required = average_net_profit * CSR_TURNOVER_RATE
    shortfall = max(required - spent, 0.0)

    return CalcResult(
        method="CSR obligation = 2% of the average net profit of the three immediately preceding financial years",
        as_of=as_of,
        inputs={
            "average_net_profit": money(average_net_profit),
            "spent": money(spent),
            "rate": CSR_TURNOVER_RATE,
        },
        assumptions=[
            "The company meets at least one section 135 threshold for net worth, turnover or net profit.",
            "Net profit is computed under section 198.",
        ],
        limitations=[
            "Unspent amounts for ongoing projects must be transferred to a designated account within 30 days.",
            "Other unspent amounts must go to a Schedule VII fund within six months of year end.",
            "CSR spending is not deductible as a business expense under section 37.",
        ],
        result={
            "required_spend": money(required),
            "actual_spend": money(spent),
            "shortfall": money(shortfall),
            "utilisation": pct(safe_div(spent, required)),
            "is_compliant": shortfall <= 0,
        },
    )
