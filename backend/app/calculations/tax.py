"""Indian tax calculations: capital gains, slab tax, Chapter VI-A, regime choice.

Every figure is an estimate for planning discussion. Nothing here files a
return, and nothing here executes a trade.

Rules modelled (assessment year 2026-27, financial year 2025-26):

  * Listed equity and equity mutual funds
      - short term  (held <= 12 months)  : 20% under section 111A
      - long term   (held  > 12 months)  : 12.5% under section 112A,
                                           first Rs 1,25,000 of gains exempt
  * Debt mutual funds bought on or after 1 April 2023
      - always short term, taxed at the slab rate, no indexation
  * Other capital assets (gold, unlisted, property)
      - short term (<= 24 months) at slab; long term at 12.5% without indexation
  * Set-off: a short-term capital loss offsets both STCG and LTCG; a long-term
    capital loss offsets only LTCG. Unabsorbed losses carry forward eight
    assessment years, provided the return is filed by the due date.
  * There is no wash-sale rule in India. Selling to book a loss or to use the
    section 112A exemption and repurchasing immediately is permitted, so the
    product surfaces both harvesting a loss and harvesting a gain.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Sequence

from app.calculations.base import CalcResult, money, pct, safe_div

# -- Holding period thresholds ---------------------------------------------
EQUITY_LONG_TERM_DAYS = 366        # more than 12 months
OTHER_ASSET_LONG_TERM_DAYS = 731   # more than 24 months

# -- Capital gains rates ----------------------------------------------------
STCG_EQUITY_RATE = 0.20            # section 111A
LTCG_EQUITY_RATE = 0.125           # section 112A
LTCG_EQUITY_EXEMPTION = 1_25_000.0  # per financial year, per taxpayer
LTCG_OTHER_RATE = 0.125            # without indexation
LOSS_CARRY_FORWARD_YEARS = 8

# -- Surcharge and cess -----------------------------------------------------
HEALTH_EDUCATION_CESS = 0.04
# Surcharge on capital gains is capped at 15%.
CAPITAL_GAINS_SURCHARGE_CAP = 0.15
SURCHARGE_SLABS: list[tuple[float, float]] = [
    (5_00_00_000.0, 0.25),
    (2_00_00_000.0, 0.15),
    (1_00_00_000.0, 0.10),
    (50_00_000.0, 0.05),
]

# -- Slab rates -------------------------------------------------------------
# (upper bound of the slab, rate). The last entry is open ended.
NEW_REGIME_SLABS: list[tuple[float, float]] = [
    (4_00_000.0, 0.00),
    (8_00_000.0, 0.05),
    (12_00_000.0, 0.10),
    (16_00_000.0, 0.15),
    (20_00_000.0, 0.20),
    (24_00_000.0, 0.25),
    (float("inf"), 0.30),
]

OLD_REGIME_SLABS: list[tuple[float, float]] = [
    (2_50_000.0, 0.00),
    (5_00_000.0, 0.05),
    (10_00_000.0, 0.20),
    (float("inf"), 0.30),
]

NEW_REGIME_STANDARD_DEDUCTION = 75_000.0
OLD_REGIME_STANDARD_DEDUCTION = 50_000.0

# Section 87A rebate: full relief up to this taxable income.
NEW_REGIME_REBATE_LIMIT = 12_00_000.0
OLD_REGIME_REBATE_LIMIT = 5_00_000.0

# -- Chapter VI-A limits (old regime only) ----------------------------------
SECTION_80C_LIMIT = 1_50_000.0
SECTION_80CCD_1B_LIMIT = 50_000.0      # additional NPS contribution
SECTION_80D_SELF_LIMIT = 25_000.0      # health insurance, below 60
SECTION_80D_SENIOR_LIMIT = 50_000.0
SECTION_24B_LIMIT = 2_00_000.0         # home loan interest, self-occupied
SECTION_80TTA_LIMIT = 10_000.0         # savings interest, below 60
SECTION_80TTB_LIMIT = 50_000.0         # interest income, senior citizens

# -- Statutory savings limits ----------------------------------------------
PPF_ANNUAL_LIMIT = 1_50_000.0
SUKANYA_ANNUAL_LIMIT = 1_50_000.0
NPS_TIER1_MIN_ANNUAL = 1_000.0
SENIOR_CITIZEN_AGE = 60
SUPER_SENIOR_AGE = 80


# ---------------------------------------------------------------------------
# Holding period and gain character
# ---------------------------------------------------------------------------

def holding_period(acquired_on: date, as_of: date, asset_class: str = "indian_equity") -> str:
    """Short or long term, using the threshold that applies to the asset."""
    days = (as_of - acquired_on).days
    if asset_class in {"indian_equity", "intl_equity"}:
        return "long_term" if days >= EQUITY_LONG_TERM_DAYS else "short_term"
    if asset_class == "debt":
        # Debt funds bought on or after 1 April 2023 are always short term.
        return "short_term" if acquired_on >= date(2023, 4, 1) else (
            "long_term" if days >= OTHER_ASSET_LONG_TERM_DAYS else "short_term"
        )
    return "long_term" if days >= OTHER_ASSET_LONG_TERM_DAYS else "short_term"


def financial_year(day: date) -> str:
    """India runs 1 April to 31 March. Returns e.g. '2025-26'."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def financial_year_bounds(day: date) -> tuple[date, date]:
    start_year = day.year if day.month >= 4 else day.year - 1
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


# ---------------------------------------------------------------------------
# Slab tax
# ---------------------------------------------------------------------------

def _surcharge_rate(total_income: float, capped: bool = False) -> float:
    for threshold, rate in SURCHARGE_SLABS:
        if total_income > threshold:
            return min(rate, CAPITAL_GAINS_SURCHARGE_CAP) if capped else rate
    return 0.0


def _slab_tax(taxable_income: float, slabs: Sequence[tuple[float, float]]) -> float:
    tax = 0.0
    lower = 0.0
    for upper, rate in slabs:
        if taxable_income <= lower:
            break
        tax += (min(taxable_income, upper) - lower) * rate
        lower = upper
    return tax


def slab_tax(
    *,
    gross_income: float,
    regime: str,
    deductions: float,
    age: int,
    as_of: date,
) -> CalcResult:
    """Income tax under one regime, including rebate, surcharge and cess."""
    is_new = regime == "new"
    slabs = NEW_REGIME_SLABS if is_new else OLD_REGIME_SLABS
    standard = NEW_REGIME_STANDARD_DEDUCTION if is_new else OLD_REGIME_STANDARD_DEDUCTION

    # Chapter VI-A deductions are not available under the new regime.
    allowed_deductions = 0.0 if is_new else deductions
    taxable = max(gross_income - standard - allowed_deductions, 0.0)

    base_tax = _slab_tax(taxable, slabs)

    # Section 87A rebate.
    rebate_limit = NEW_REGIME_REBATE_LIMIT if is_new else OLD_REGIME_REBATE_LIMIT
    rebate = base_tax if taxable <= rebate_limit else 0.0
    tax_after_rebate = base_tax - rebate

    surcharge = tax_after_rebate * _surcharge_rate(taxable)
    cess = (tax_after_rebate + surcharge) * HEALTH_EDUCATION_CESS
    total = tax_after_rebate + surcharge + cess

    return CalcResult(
        method=(
            "slab tax on income after the standard deduction and any Chapter VI-A relief, "
            "less the section 87A rebate, plus surcharge and 4% health and education cess"
        ),
        as_of=as_of,
        inputs={
            "regime": regime,
            "financial_year": financial_year(as_of),
            "gross_income": money(gross_income),
            "standard_deduction": money(standard),
            "chapter_via_deductions": money(allowed_deductions),
            "taxable_income": money(taxable),
            "age": age,
        },
        assumptions=[
            f"Standard deduction of Rs {standard:,.0f} on salary income.",
            "Chapter VI-A deductions are available only under the old regime."
            if is_new
            else "Chapter VI-A deductions are claimed in full as entered.",
            f"Section 87A rebate applies where taxable income does not exceed Rs {rebate_limit:,.0f}.",
            "Health and education cess of 4% applies to tax plus surcharge.",
        ],
        limitations=[
            "This is a planning estimate, not a computation of your return.",
            "Marginal relief on surcharge, and relief under sections 89, 90 and 91, are not modelled.",
            "Capital gains are taxed separately at special rates and are not included here.",
            "Confirm every figure with a qualified chartered accountant before acting.",
        ],
        result={
            "regime": regime,
            "taxable_income": money(taxable),
            "tax_before_rebate": money(base_tax),
            "rebate_87a": money(rebate),
            "surcharge": money(surcharge),
            "cess": money(cess),
            "total_tax": money(total),
            "effective_rate": pct(safe_div(total, gross_income)),
            "marginal_rate": pct(_marginal_rate(taxable, slabs)),
        },
    )


def _marginal_rate(taxable_income: float, slabs: Sequence[tuple[float, float]]) -> float:
    lower = 0.0
    for upper, rate in slabs:
        if taxable_income <= upper:
            return rate
        lower = upper
    return slabs[-1][1]


def compare_regimes(
    *,
    gross_income: float,
    deductions: float,
    age: int,
    as_of: date,
) -> CalcResult:
    """Old versus new regime. Every taxpayer chooses again each year."""
    old = slab_tax(gross_income=gross_income, regime="old", deductions=deductions, age=age, as_of=as_of).result
    new = slab_tax(gross_income=gross_income, regime="new", deductions=deductions, age=age, as_of=as_of).result

    saving = old["total_tax"] - new["total_tax"]
    better = "new" if saving > 0 else "old"

    # The deduction level at which the old regime becomes the cheaper choice.
    # None means no realistic level of deductions closes the gap.
    breakeven: float | None = None
    probe = 0.0
    while probe <= 6_00_000.0:
        trial = slab_tax(gross_income=gross_income, regime="old", deductions=probe, age=age, as_of=as_of).result
        if trial["total_tax"] <= new["total_tax"]:
            breakeven = probe
            break
        probe += 5_000.0

    return CalcResult(
        method="the same income is taxed under both regimes and the cheaper one identified",
        as_of=as_of,
        inputs={
            "gross_income": money(gross_income),
            "chapter_via_deductions": money(deductions),
            "age": age,
            "financial_year": financial_year(as_of),
        },
        assumptions=[
            "Deductions entered are those actually available and claimed under the old regime.",
            "The new regime is the default; the old regime must be opted into each year.",
        ],
        limitations=[
            "A salaried taxpayer may switch each year; a taxpayer with business income generally may not.",
            "House property loss set-off and exempt allowances such as HRA and LTA are not modelled.",
        ],
        result={
            "old_regime_tax": old["total_tax"],
            "new_regime_tax": new["total_tax"],
            "recommended_regime": better,
            "annual_saving": money(abs(saving)),
            "old_effective_rate": old["effective_rate"],
            "new_effective_rate": new["effective_rate"],
            "old_marginal_rate": old["marginal_rate"],
            "new_marginal_rate": new["marginal_rate"],
            "deduction_breakeven": money(breakeven) if breakeven is not None else None,
            "old": old,
            "new": new,
        },
    )


# ---------------------------------------------------------------------------
# Capital gains
# ---------------------------------------------------------------------------

def realized_gains(transactions: Sequence[dict[str, Any]], as_of: date) -> CalcResult:
    """Realised gains for the financial year, split by character."""
    start, end = financial_year_bounds(as_of)
    equity_stcg = equity_ltcg = other_stcg = other_ltcg = 0.0
    count = 0

    for txn in transactions:
        trade_date = txn.get("trade_date")
        gain = txn.get("realized_gain")
        if trade_date is None or gain is None or not (start <= trade_date <= end):
            continue
        count += 1
        is_equity = txn.get("asset_class", "indian_equity") in {"indian_equity", "intl_equity"}
        if txn.get("is_long_term"):
            if is_equity:
                equity_ltcg += float(gain)
            else:
                other_ltcg += float(gain)
        else:
            if is_equity:
                equity_stcg += float(gain)
            else:
                other_stcg += float(gain)

    return CalcResult(
        method=(
            "realised gains are summed from settled sales in the financial year and split by "
            "holding period and by whether the asset is equity or not"
        ),
        as_of=as_of,
        inputs={"financial_year": financial_year(as_of), "transactions_considered": count},
        assumptions=[
            "Only settled transactions recorded in the platform are included.",
            "The financial year runs 1 April to 31 March.",
        ],
        limitations=[
            "Gains realised through brokers not linked to the platform are excluded.",
            "The broker's capital gains statement and the AIS remain the authoritative record.",
        ],
        result={
            "equity_stcg": money(equity_stcg),
            "equity_ltcg": money(equity_ltcg),
            "other_stcg": money(other_stcg),
            "other_ltcg": money(other_ltcg),
            "total_stcg": money(equity_stcg + other_stcg),
            "total_ltcg": money(equity_ltcg + other_ltcg),
            "net_gain": money(equity_stcg + equity_ltcg + other_stcg + other_ltcg),
            "transaction_count": count,
        },
    )


def estimate_capital_gains_tax(
    *,
    equity_stcg: float,
    equity_ltcg: float,
    other_stcg: float,
    other_ltcg: float,
    slab_rate: float,
    total_income: float,
    as_of: date,
) -> CalcResult:
    """Capital gains tax after set-off, the 112A exemption, surcharge and cess."""
    # Set-off. A short-term loss offsets any gain; a long-term loss only offsets
    # long-term gains.
    st_pool = equity_stcg + other_stcg
    lt_pool = equity_ltcg + other_ltcg

    e_stcg, o_stcg = max(equity_stcg, 0.0), max(other_stcg, 0.0)
    e_ltcg, o_ltcg = max(equity_ltcg, 0.0), max(other_ltcg, 0.0)

    st_loss = -min(st_pool, 0.0)
    lt_loss = -min(lt_pool, 0.0)

    # A long-term loss reduces long-term gains first.
    if lt_loss:
        absorb = min(lt_loss, e_ltcg + o_ltcg)
        share = safe_div(absorb, e_ltcg + o_ltcg) if (e_ltcg + o_ltcg) else 0.0
        e_ltcg -= e_ltcg * share
        o_ltcg -= o_ltcg * share
        lt_loss -= absorb

    # A short-term loss may then be set against anything that remains. Highest
    # taxed buckets are relieved first, which is the taxpayer's best outcome.
    if st_loss:
        buckets = [e_stcg, o_stcg, e_ltcg, o_ltcg]
        for index in range(len(buckets)):
            if st_loss <= 0:
                break
            absorb = min(st_loss, buckets[index])
            buckets[index] -= absorb
            st_loss -= absorb
        e_stcg, o_stcg, e_ltcg, o_ltcg = buckets

    # Section 112A exemption applies to equity long-term gains only.
    exemption_used = min(e_ltcg, LTCG_EQUITY_EXEMPTION)
    taxable_equity_ltcg = max(e_ltcg - LTCG_EQUITY_EXEMPTION, 0.0)

    tax_equity_stcg = e_stcg * STCG_EQUITY_RATE
    tax_equity_ltcg = taxable_equity_ltcg * LTCG_EQUITY_RATE
    tax_other_stcg = o_stcg * slab_rate
    tax_other_ltcg = o_ltcg * LTCG_OTHER_RATE

    base_tax = tax_equity_stcg + tax_equity_ltcg + tax_other_stcg + tax_other_ltcg
    surcharge = base_tax * _surcharge_rate(total_income, capped=True)
    cess = (base_tax + surcharge) * HEALTH_EDUCATION_CESS
    total = base_tax + surcharge + cess

    carry_forward = st_loss + lt_loss
    net_gain = e_stcg + e_ltcg + o_stcg + o_ltcg

    return CalcResult(
        method=(
            "losses are set off first, then equity STCG at 20% under section 111A, equity LTCG above the "
            f"Rs {LTCG_EQUITY_EXEMPTION:,.0f} section 112A exemption at 12.5%, debt and other short-term gains at "
            "the slab rate and other long-term gains at 12.5%, plus surcharge and 4% cess"
        ),
        as_of=as_of,
        inputs={
            "equity_stcg": money(equity_stcg),
            "equity_ltcg": money(equity_ltcg),
            "other_stcg": money(other_stcg),
            "other_ltcg": money(other_ltcg),
            "slab_rate": slab_rate,
            "total_income": money(total_income),
            "section_112a_exemption": LTCG_EQUITY_EXEMPTION,
            "financial_year": financial_year(as_of),
        },
        assumptions=[
            f"The section 112A exemption of Rs {LTCG_EQUITY_EXEMPTION:,.0f} is available in full this year.",
            "Securities transaction tax has been paid, so sections 111A and 112A apply.",
            "Surcharge on capital gains is capped at 15%.",
            "Debt units purchased on or after 1 April 2023 are treated as short term without indexation.",
        ],
        limitations=[
            "A planning estimate, not a computation of your return.",
            f"Carried-forward losses are usable for {LOSS_CARRY_FORWARD_YEARS} assessment years and only if the "
            "return is filed by the due date.",
            "Grandfathered cost as at 31 January 2018 for pre-2018 holdings is not applied.",
        ],
        result={
            "taxable_equity_stcg": money(e_stcg),
            "taxable_equity_ltcg": money(taxable_equity_ltcg),
            "taxable_other_stcg": money(o_stcg),
            "taxable_other_ltcg": money(o_ltcg),
            "exemption_used": money(exemption_used),
            "exemption_remaining": money(max(LTCG_EQUITY_EXEMPTION - exemption_used, 0.0)),
            "tax_equity_stcg": money(tax_equity_stcg),
            "tax_equity_ltcg": money(tax_equity_ltcg),
            "tax_other_stcg": money(tax_other_stcg),
            "tax_other_ltcg": money(tax_other_ltcg),
            "base_tax": money(base_tax),
            "surcharge": money(surcharge),
            "cess": money(cess),
            "total_tax": money(total),
            "effective_rate": pct(safe_div(total, net_gain)) if net_gain > 0 else 0.0,
            "loss_carry_forward": money(carry_forward),
            "net_gain": money(net_gain),
        },
    )


# ---------------------------------------------------------------------------
# Harvesting
# ---------------------------------------------------------------------------

def harvest_opportunities(
    lots: Sequence[dict[str, Any]],
    *,
    slab_rate: float,
    ltcg_exemption_remaining: float,
    as_of: date,
    minimum_loss: float = 25_000.0,
    minimum_gain: float = 10_000.0,
) -> CalcResult:
    """Two distinct Indian strategies, surfaced side by side.

    *Loss harvesting* books a capital loss to set against gains this year, with
    anything unabsorbed carried forward for eight years.

    *Gain harvesting* books long-term equity gains up to the unused section
    112A exemption and immediately repurchases, resetting the cost base at no
    tax cost. There is no wash-sale rule in India, so this is entirely
    legitimate and is the more valuable of the two for most households.
    """
    loss_rows: list[dict[str, Any]] = []
    gain_rows: list[dict[str, Any]] = []
    total_loss = 0.0
    total_loss_benefit = 0.0
    exemption_left = ltcg_exemption_remaining

    for lot in lots:
        quantity = float(lot.get("quantity") or 0.0)
        cost_per_unit = float(lot.get("cost_per_share") or 0.0)
        price = float(lot.get("price") or 0.0)
        asset_class = str(lot.get("asset_class", "indian_equity"))
        cost_basis = quantity * cost_per_unit
        market_value = quantity * price
        gain = market_value - cost_basis
        period = holding_period(lot["acquired_on"], as_of, asset_class)
        is_equity = asset_class in {"indian_equity", "intl_equity"}

        base = {
            "lot_id": lot.get("id"),
            "symbol": lot.get("symbol"),
            "name": lot.get("name"),
            "account_id": lot.get("account_id"),
            "account_name": lot.get("account_name"),
            "asset_class": asset_class,
            "quantity": round(quantity, 4),
            "cost_basis": money(cost_basis),
            "market_value": money(market_value),
            "holding_period": period,
            "acquired_on": lot["acquired_on"].isoformat(),
        }

        if gain <= -minimum_loss:
            # The rate the loss will shelter depends on what it offsets.
            if is_equity and period == "short_term":
                rate = STCG_EQUITY_RATE
            elif is_equity:
                rate = LTCG_EQUITY_RATE
            elif period == "short_term":
                rate = slab_rate
            else:
                rate = LTCG_OTHER_RATE
            benefit = abs(gain) * rate * (1 + HEALTH_EDUCATION_CESS)
            total_loss += gain
            total_loss_benefit += benefit
            loss_rows.append(
                {
                    **base,
                    "strategy": "harvest_loss",
                    "unrealized_gain": money(gain),
                    "applicable_rate": round(rate, 4),
                    "estimated_tax_benefit": money(benefit),
                    "rationale": "Book the loss to set against gains this year; any excess carries forward eight years.",
                }
            )

        elif is_equity and period == "long_term" and gain >= minimum_gain and exemption_left > 0:
            harvestable = min(gain, exemption_left)
            exemption_left -= harvestable
            # Tax that would otherwise be paid on this gain later, at 12.5%.
            benefit = harvestable * LTCG_EQUITY_RATE * (1 + HEALTH_EDUCATION_CESS)
            gain_rows.append(
                {
                    **base,
                    "strategy": "harvest_gain",
                    "unrealized_gain": money(gain),
                    "harvestable_gain": money(harvestable),
                    "applicable_rate": LTCG_EQUITY_RATE,
                    "estimated_tax_benefit": money(benefit),
                    "rationale": (
                        "Realise long-term gains inside the section 112A exemption and repurchase, "
                        "resetting the cost base at no tax cost."
                    ),
                }
            )

    loss_rows.sort(key=lambda r: r["estimated_tax_benefit"], reverse=True)
    gain_rows.sort(key=lambda r: r["estimated_tax_benefit"], reverse=True)
    total_gain_benefit = sum(r["estimated_tax_benefit"] for r in gain_rows)

    return CalcResult(
        method=(
            "loss lots below the review threshold are valued at the rate the loss would shelter; "
            "long-term equity gains are matched against the unused section 112A exemption"
        ),
        as_of=as_of,
        inputs={
            "lots_examined": len(lots),
            "minimum_loss_threshold": minimum_loss,
            "minimum_gain_threshold": minimum_gain,
            "ltcg_exemption_remaining": money(ltcg_exemption_remaining),
            "slab_rate": slab_rate,
            "financial_year": financial_year(as_of),
        },
        assumptions=[
            f"Only losses above Rs {minimum_loss:,.0f} and gains above Rs {minimum_gain:,.0f} are surfaced.",
            "Harvested losses are usable against gains of a permitted character this year.",
            "India has no wash-sale rule, so a repurchase immediately after the sale is permitted.",
        ],
        limitations=[
            "Brokerage, STT, stamp duty and exit loads are not modelled and reduce the benefit.",
            "Being out of the market between sale and repurchase carries price risk.",
            "Every candidate requires human approval; this platform never places an order.",
        ],
        result={
            "loss_opportunities": loss_rows,
            "gain_opportunities": gain_rows,
            "opportunity_count": len(loss_rows) + len(gain_rows),
            "loss_count": len(loss_rows),
            "gain_count": len(gain_rows),
            "total_harvestable_loss": money(total_loss),
            "total_harvestable_gain": money(sum(r["harvestable_gain"] for r in gain_rows)),
            "total_estimated_benefit": money(total_loss_benefit + total_gain_benefit),
            "loss_benefit": money(total_loss_benefit),
            "gain_benefit": money(total_gain_benefit),
            "exemption_remaining_after": money(exemption_left),
        },
    )


# ---------------------------------------------------------------------------
# Chapter VI-A
# ---------------------------------------------------------------------------

def chapter_via_summary(
    *,
    epf_contribution: float,
    ppf_contribution: float,
    elss_investment: float,
    life_insurance_premium: float,
    home_loan_principal: float,
    sukanya_contribution: float,
    tuition_fees: float,
    nps_additional: float,
    health_insurance_premium: float,
    home_loan_interest: float,
    savings_interest: float,
    age: int,
    as_of: date,
) -> CalcResult:
    """How much of each deduction ceiling has actually been used."""
    eighty_c_items = {
        "EPF contribution": epf_contribution,
        "PPF contribution": ppf_contribution,
        "ELSS investment": elss_investment,
        "Life insurance premium": life_insurance_premium,
        "Home loan principal": home_loan_principal,
        "Sukanya Samriddhi": sukanya_contribution,
        "Children's tuition fees": tuition_fees,
    }
    eighty_c_total = sum(eighty_c_items.values())
    eighty_c_claimed = min(eighty_c_total, SECTION_80C_LIMIT)

    nps_claimed = min(nps_additional, SECTION_80CCD_1B_LIMIT)
    senior = age >= SENIOR_CITIZEN_AGE
    health_limit = SECTION_80D_SENIOR_LIMIT if senior else SECTION_80D_SELF_LIMIT
    health_claimed = min(health_insurance_premium, health_limit)
    interest_claimed = min(home_loan_interest, SECTION_24B_LIMIT)
    savings_limit = SECTION_80TTB_LIMIT if senior else SECTION_80TTA_LIMIT
    savings_claimed = min(savings_interest, savings_limit)

    total = eighty_c_claimed + nps_claimed + health_claimed + interest_claimed + savings_claimed

    sections = [
        {
            "section": "80C",
            "label": "Investments and repayments",
            "limit": SECTION_80C_LIMIT,
            "invested": money(eighty_c_total),
            "claimed": money(eighty_c_claimed),
            "headroom": money(max(SECTION_80C_LIMIT - eighty_c_total, 0.0)),
            "fully_used": eighty_c_total >= SECTION_80C_LIMIT,
            "breakdown": [
                {"item": name, "amount": money(value)} for name, value in eighty_c_items.items() if value > 0
            ],
        },
        {
            "section": "80CCD(1B)",
            "label": "Additional NPS contribution",
            "limit": SECTION_80CCD_1B_LIMIT,
            "invested": money(nps_additional),
            "claimed": money(nps_claimed),
            "headroom": money(max(SECTION_80CCD_1B_LIMIT - nps_additional, 0.0)),
            "fully_used": nps_additional >= SECTION_80CCD_1B_LIMIT,
            "breakdown": [],
        },
        {
            "section": "80D",
            "label": "Health insurance premium",
            "limit": health_limit,
            "invested": money(health_insurance_premium),
            "claimed": money(health_claimed),
            "headroom": money(max(health_limit - health_insurance_premium, 0.0)),
            "fully_used": health_insurance_premium >= health_limit,
            "breakdown": [],
        },
        {
            "section": "24(b)",
            "label": "Home loan interest, self-occupied",
            "limit": SECTION_24B_LIMIT,
            "invested": money(home_loan_interest),
            "claimed": money(interest_claimed),
            "headroom": money(max(SECTION_24B_LIMIT - home_loan_interest, 0.0)),
            "fully_used": home_loan_interest >= SECTION_24B_LIMIT,
            "breakdown": [],
        },
        {
            "section": "80TTB" if senior else "80TTA",
            "label": "Interest income" if senior else "Savings account interest",
            "limit": savings_limit,
            "invested": money(savings_interest),
            "claimed": money(savings_claimed),
            "headroom": money(max(savings_limit - savings_interest, 0.0)),
            "fully_used": savings_interest >= savings_limit,
            "breakdown": [],
        },
    ]

    return CalcResult(
        method="each Chapter VI-A section is capped at its statutory limit and the unused headroom reported",
        as_of=as_of,
        inputs={"age": age, "financial_year": financial_year(as_of), "senior_citizen": senior},
        assumptions=[
            "These deductions are available only if the old regime is chosen for the year.",
            f"The section 80C ceiling of Rs {SECTION_80C_LIMIT:,.0f} covers EPF, PPF, ELSS, life insurance, "
            "home loan principal, Sukanya Samriddhi and tuition fees together.",
            "The employee's own EPF contribution counts toward 80C; the employer's does not.",
        ],
        limitations=[
            "Sections 80E, 80EE, 80EEA, 80G and 80GG are reported separately.",
            "ELSS carries a three-year lock-in; PPF and Sukanya are longer.",
            "Confirm eligibility with a chartered accountant before relying on any figure.",
        ],
        result={
            "sections": sections,
            "total_deductions": money(total),
            "total_headroom": money(sum(float(s["headroom"]) for s in sections)),
            "sections_fully_used": sum(1 for s in sections if s["fully_used"]),
        },
    )


# ---------------------------------------------------------------------------
# Advance tax
# ---------------------------------------------------------------------------

ADVANCE_TAX_INSTALMENTS: list[tuple[str, float, tuple[int, int]]] = [
    ("15 June", 0.15, (6, 15)),
    ("15 September", 0.45, (9, 15)),
    ("15 December", 0.75, (12, 15)),
    ("15 March", 1.00, (3, 15)),
]

ADVANCE_TAX_THRESHOLD = 10_000.0


def advance_tax_schedule(*, estimated_annual_tax: float, tax_paid: float, as_of: date) -> CalcResult:
    """Instalments due under section 208, and what is short today."""
    start_year = financial_year_bounds(as_of)[0].year
    liable = estimated_annual_tax > ADVANCE_TAX_THRESHOLD

    rows = []
    due_to_date = 0.0
    for label, cumulative, (month, day) in ADVANCE_TAX_INSTALMENTS:
        year = start_year if month >= 4 else start_year + 1
        due_date = date(year, month, day)
        cumulative_due = estimated_annual_tax * cumulative
        passed = due_date <= as_of
        if passed:
            due_to_date = cumulative_due
        rows.append(
            {
                "label": label,
                "due_date": due_date.isoformat(),
                "cumulative_percent": cumulative,
                "cumulative_due": money(cumulative_due),
                "instalment": money(cumulative_due - (rows[-1]["cumulative_due"] if rows else 0.0)),
                "is_past": passed,
            }
        )

    shortfall = max(due_to_date - tax_paid, 0.0)

    return CalcResult(
        method="section 208 instalments at 15%, 45%, 75% and 100% of the estimated liability",
        as_of=as_of,
        inputs={
            "estimated_annual_tax": money(estimated_annual_tax),
            "tax_paid": money(tax_paid),
            "threshold": ADVANCE_TAX_THRESHOLD,
            "financial_year": financial_year(as_of),
        },
        assumptions=[
            f"Advance tax is payable where the liability after TDS exceeds Rs {ADVANCE_TAX_THRESHOLD:,.0f}.",
            "TDS already deducted is treated as tax paid.",
        ],
        limitations=[
            "Interest under sections 234B and 234C on any shortfall is not calculated here.",
            "Senior citizens without business income are not liable to advance tax.",
        ],
        result={
            "is_liable": liable,
            "instalments": rows,
            "cumulative_due_to_date": money(due_to_date),
            "tax_paid": money(tax_paid),
            "shortfall": money(shortfall),
            "on_schedule": shortfall <= 0,
            "next_due": next((r for r in rows if not r["is_past"]), None),
        },
    )


# ---------------------------------------------------------------------------
# Asset location
# ---------------------------------------------------------------------------

# Interest-bearing assets are taxed at slab rates in a taxable account, so they
# belong inside a tax-exempt wrapper wherever the wrapper allows them.
ASSET_LOCATION_PREFERENCE = {
    "debt": "tax_exempt",
    "gold": "taxable",
    "alternatives": "taxable",
    "indian_equity": "taxable",
    "intl_equity": "taxable",
    "cash": "taxable",
}


def asset_location_review(positions: Sequence[dict[str, Any]], slab_rate: float, as_of: date) -> CalcResult:
    """Flag interest income sitting where it is taxed at the slab rate."""
    by_bucket: dict[str, float] = defaultdict(float)
    misplaced = []
    total = 0.0

    for position in positions:
        value = float(position.get("quantity") or 0.0) * float(position.get("price") or 0.0)
        total += value
        treatment = position.get("tax_treatment", "taxable")
        asset_class = position.get("asset_class", "indian_equity")
        by_bucket[treatment] += value

        preferred = ASSET_LOCATION_PREFERENCE.get(asset_class, "taxable")
        if preferred == "tax_exempt" and treatment == "taxable" and value > 0:
            annual_yield = float(position.get("dividend_yield") or 0.0)
            misplaced.append(
                {
                    "symbol": position.get("symbol"),
                    "name": position.get("name"),
                    "asset_class": asset_class,
                    "current_location": treatment,
                    "preferred_location": "PPF, EPF or NPS",
                    "market_value": money(value),
                    "estimated_annual_drag": money(value * annual_yield * slab_rate),
                }
            )

    misplaced.sort(key=lambda r: r["estimated_annual_drag"], reverse=True)

    return CalcResult(
        method="each holding's asset class is compared against the wrapper that taxes it most lightly",
        as_of=as_of,
        inputs={"positions": len(positions), "total_market_value": money(total), "slab_rate": slab_rate},
        assumptions=[
            "Debt returns are taxed at the slab rate in a taxable account and are exempt inside PPF or EPF.",
            "Equity is left in taxable accounts, where long-term gains are taxed at 12.5% with an annual exemption.",
        ],
        limitations=[
            "PPF and Sukanya carry statutory annual contribution limits and long lock-ins.",
            "NPS restricts equity allocation and requires annuitisation of part of the corpus at exit.",
            "Moving an existing holding realises a gain; the tax may exceed the benefit.",
        ],
        result={
            "by_tax_treatment": {k: money(v) for k, v in by_bucket.items()},
            "misplaced": misplaced,
            "total_estimated_drag": money(sum(r["estimated_annual_drag"] for r in misplaced)),
        },
    )


def capital_gains_budget(*, realized_net: float, budget: float, pending_gains: float, as_of: date) -> CalcResult:
    """How much gain remains before the household breaches its annual budget."""
    used = realized_net + pending_gains
    remaining = budget - used

    return CalcResult(
        method="remaining budget = annual gain budget - (realised net gain + gains pending from proposed trades)",
        as_of=as_of,
        inputs={
            "realized_net_gain": money(realized_net),
            "pending_gains": money(pending_gains),
            "annual_budget": money(budget),
            "financial_year": financial_year(as_of),
        },
        assumptions=[
            "The budget is agreed with the client to keep the surcharge band and cash-flow impact under control.",
        ],
        limitations=["The budget covers capital gains only, not salary, business or interest income."],
        result={
            "budget": money(budget),
            "used": money(used),
            "remaining": money(remaining),
            "utilisation": pct(safe_div(used, budget)),
            "over_budget": remaining < 0,
        },
    )
