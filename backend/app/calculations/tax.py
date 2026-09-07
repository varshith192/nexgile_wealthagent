"""Tax calculations: realised gains, harvesting, wash sales, Roth, RMD, asset location.

Every figure is an estimate for planning discussion. Nothing here executes a trade.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Sequence

from app.calculations.base import CalcResult, money, pct, safe_div

LONG_TERM_DAYS = 366
WASH_SALE_DAYS = 30
CAPITAL_LOSS_ORDINARY_OFFSET = 3000.0

# IRS Uniform Lifetime Table (abridged to the ages this product plans for).
UNIFORM_LIFETIME_TABLE: dict[int, float] = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0,
    79: 21.1, 80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0,
    86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8,
    93: 10.1, 94: 9.5, 95: 8.9,
}

RMD_START_AGE = 73


def holding_period(acquired_on: date, as_of: date) -> str:
    return "long_term" if (as_of - acquired_on).days >= LONG_TERM_DAYS else "short_term"


def realized_gains(transactions: Sequence[dict[str, Any]], tax_year: int, as_of: date) -> CalcResult:
    """Split year-to-date realised gains into short and long term."""
    short_term = 0.0
    long_term = 0.0
    count = 0

    for txn in transactions:
        if txn.get("trade_date") is None or txn["trade_date"].year != tax_year:
            continue
        gain = txn.get("realized_gain")
        if gain is None:
            continue
        count += 1
        if txn.get("is_long_term"):
            long_term += float(gain)
        else:
            short_term += float(gain)

    net = short_term + long_term

    return CalcResult(
        method="realised gains are summed from settled sale transactions in the tax year, split by holding period",
        as_of=as_of,
        inputs={"tax_year": tax_year, "transactions_considered": count},
        assumptions=["Only settled transactions recorded in the platform are included."],
        limitations=[
            "Gains realised at institutions not linked to the platform are excluded.",
            "Wash-sale adjustments reported by the custodian on Form 1099-B may differ.",
        ],
        result={
            "short_term_gain": money(short_term),
            "long_term_gain": money(long_term),
            "net_gain": money(net),
            "transaction_count": count,
        },
    )


def estimate_tax_on_gains(
    short_term_gain: float,
    long_term_gain: float,
    marginal_rate: float,
    ltcg_rate: float,
    state_rate: float,
    as_of: date,
) -> CalcResult:
    """Federal + state estimate on realised capital gains, with loss carryover."""
    net = short_term_gain + long_term_gain
    carryforward = 0.0
    ordinary_offset = 0.0

    if net < 0:
        ordinary_offset = min(abs(net), CAPITAL_LOSS_ORDINARY_OFFSET)
        carryforward = abs(net) - ordinary_offset
        federal = -(ordinary_offset * marginal_rate)
        state = -(ordinary_offset * state_rate)
    else:
        st = max(short_term_gain, 0.0)
        lt = max(long_term_gain, 0.0)
        # A loss in one bucket offsets a gain in the other before rates apply.
        if short_term_gain < 0:
            lt = max(lt + short_term_gain, 0.0)
            st = 0.0
        if long_term_gain < 0:
            st = max(st + long_term_gain, 0.0)
            lt = 0.0
        federal = st * marginal_rate + lt * ltcg_rate
        state = (st + lt) * state_rate

    return CalcResult(
        method=(
            "short-term gains taxed at the marginal ordinary rate, long-term at the capital-gains rate, "
            "plus a flat state rate; net losses offset up to $3,000 of ordinary income and carry forward"
        ),
        as_of=as_of,
        inputs={
            "short_term_gain": money(short_term_gain),
            "long_term_gain": money(long_term_gain),
            "marginal_rate": marginal_rate,
            "ltcg_rate": ltcg_rate,
            "state_rate": state_rate,
        },
        assumptions=[
            "A flat marginal rate is applied rather than bracket-by-bracket calculation.",
            "The 3.8% net investment income tax and AMT are not modelled.",
            "State tax is estimated with a single flat rate.",
        ],
        limitations=[
            "This is a planning estimate, not tax advice or a tax return calculation.",
            "Confirm all figures with a qualified tax professional before acting.",
        ],
        result={
            "federal_tax": money(federal),
            "state_tax": money(state),
            "total_tax": money(federal + state),
            "effective_rate": pct(safe_div(federal + state, net)) if net > 0 else 0.0,
            "ordinary_income_offset": money(ordinary_offset),
            "loss_carryforward": money(carryforward),
        },
    )


def wash_sale_check(
    security_symbol: str,
    sale_date: date,
    purchases: Sequence[dict[str, Any]],
    substantially_identical: Sequence[str] = (),
) -> CalcResult:
    """Flag a loss sale blocked by a purchase in the 61-day window."""
    watch_symbols = {security_symbol, *substantially_identical}
    window_start = sale_date - timedelta(days=WASH_SALE_DAYS)
    window_end = sale_date + timedelta(days=WASH_SALE_DAYS)

    conflicts = [
        {
            "symbol": p.get("symbol"),
            "trade_date": p["trade_date"].isoformat(),
            "quantity": p.get("quantity"),
            "reason": "Substantially identical security purchased inside the 61-day window",
        }
        for p in purchases
        if p.get("symbol") in watch_symbols and window_start <= p["trade_date"] <= window_end
    ]

    risk = "blocked" if conflicts else "clear"

    return CalcResult(
        method="a loss is disallowed if a substantially identical security is bought 30 days before or after the sale",
        as_of=sale_date,
        inputs={
            "symbol": security_symbol,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "watched_symbols": sorted(watch_symbols),
            "purchases_examined": len(purchases),
        },
        assumptions=[
            "Substantially identical securities are identified from the reference data mapping in this platform.",
            "Purchases across all linked accounts, including IRAs, are considered.",
        ],
        limitations=[
            "Purchases in accounts not linked to the platform, or in a spouse's separate accounts, cannot be seen.",
            "Whether two funds are substantially identical can be a matter of judgement; confirm with a tax adviser.",
        ],
        result={
            "risk": risk,
            "is_blocked": bool(conflicts),
            "conflicts": conflicts,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "safe_to_repurchase_after": window_end.isoformat(),
        },
    )


def harvest_opportunities(
    lots: Sequence[dict[str, Any]],
    marginal_rate: float,
    ltcg_rate: float,
    state_rate: float,
    as_of: date,
    minimum_loss: float = 1000.0,
) -> CalcResult:
    """Find loss lots worth harvesting and size the estimated benefit."""
    rows = []
    total_loss = 0.0
    total_benefit = 0.0

    for lot in lots:
        quantity = float(lot.get("quantity") or 0.0)
        cost_per_share = float(lot.get("cost_per_share") or 0.0)
        price = float(lot.get("price") or 0.0)
        cost_basis = quantity * cost_per_share
        market_value = quantity * price
        loss = market_value - cost_basis
        if loss >= -minimum_loss:
            continue

        period = holding_period(lot["acquired_on"], as_of)
        rate = ltcg_rate if period == "long_term" else marginal_rate
        benefit = abs(loss) * (rate + state_rate)
        total_loss += loss
        total_benefit += benefit

        rows.append(
            {
                "lot_id": lot.get("id"),
                "symbol": lot.get("symbol"),
                "name": lot.get("name"),
                "account_id": lot.get("account_id"),
                "account_name": lot.get("account_name"),
                "quantity": round(quantity, 4),
                "cost_basis": money(cost_basis),
                "market_value": money(market_value),
                "unrealized_loss": money(loss),
                "holding_period": period,
                "acquired_on": lot["acquired_on"].isoformat(),
                "applicable_rate": round(rate + state_rate, 4),
                "estimated_tax_benefit": money(benefit),
                "wash_sale_risk": lot.get("wash_sale_risk", "clear"),
                "replacement_symbol": lot.get("replacement_symbol"),
            }
        )

    rows.sort(key=lambda r: r["estimated_tax_benefit"], reverse=True)

    return CalcResult(
        method="benefit = |unrealised loss| x (applicable capital-gains rate + state rate) per open tax lot",
        as_of=as_of,
        inputs={
            "lots_examined": len(lots),
            "minimum_loss_threshold": minimum_loss,
            "marginal_rate": marginal_rate,
            "ltcg_rate": ltcg_rate,
            "state_rate": state_rate,
        },
        assumptions=[
            f"Only lots with a loss greater than ${minimum_loss:,.0f} are surfaced.",
            "The harvested loss is assumed usable against gains of the same character this year.",
            "A replacement security preserves market exposure without being substantially identical.",
        ],
        limitations=[
            "Trading costs, bid-ask spreads and the risk of being out of the market are not modelled.",
            "Every candidate must clear a wash-sale check and human approval before any action is taken.",
            "This platform never executes trades; execution is simulated for demonstration.",
        ],
        result={
            "opportunities": rows,
            "opportunity_count": len(rows),
            "total_harvestable_loss": money(total_loss),
            "total_estimated_benefit": money(total_benefit),
        },
    )


def roth_conversion(
    conversion_amount: float,
    current_marginal_rate: float,
    expected_retirement_rate: float,
    years_to_retirement: int,
    growth_rate: float,
    as_of: date,
) -> CalcResult:
    """Compare paying tax now on a conversion against paying it in retirement."""
    tax_now = conversion_amount * current_marginal_rate
    grown = conversion_amount * ((1 + growth_rate) ** max(years_to_retirement, 0))
    tax_later = grown * expected_retirement_rate
    after_tax_roth = grown
    after_tax_traditional = grown - tax_later
    net_benefit = after_tax_roth - after_tax_traditional - tax_now * ((1 + growth_rate) ** max(years_to_retirement, 0))

    return CalcResult(
        method=(
            "compare after-tax value of converting now (tax paid from outside funds) with leaving the balance "
            "pre-tax and paying tax at the expected retirement rate"
        ),
        as_of=as_of,
        inputs={
            "conversion_amount": money(conversion_amount),
            "current_marginal_rate": current_marginal_rate,
            "expected_retirement_rate": expected_retirement_rate,
            "years_to_retirement": years_to_retirement,
            "growth_rate": growth_rate,
        },
        assumptions=[
            "Conversion tax is paid from taxable assets outside the retirement account.",
            "Tax rates today and in retirement are as entered and stay constant.",
            "The converted balance grows at a constant rate with no withdrawals.",
        ],
        limitations=[
            "Future tax law, IRMAA surcharges and state tax changes are not modelled.",
            "A conversion is irreversible; recharacterisation is no longer permitted.",
            "Effects on ACA subsidies, Social Security taxation and financial aid are excluded.",
        ],
        result={
            "tax_due_now": money(tax_now),
            "projected_balance_at_retirement": money(grown),
            "tax_if_not_converted": money(tax_later),
            "after_tax_value_roth": money(after_tax_roth),
            "after_tax_value_traditional": money(after_tax_traditional),
            "net_benefit": money(net_benefit),
            "favourable": net_benefit > 0,
            "breakeven_retirement_rate": pct(current_marginal_rate),
        },
    )


def rmd_amount(age: int, prior_year_end_balance: float, tax_year: int, as_of: date) -> CalcResult:
    """Required minimum distribution using the IRS Uniform Lifetime Table."""
    required = 0.0
    factor = UNIFORM_LIFETIME_TABLE.get(age)

    if age >= RMD_START_AGE and factor:
        required = prior_year_end_balance / factor

    return CalcResult(
        method="RMD = prior 31 December balance / IRS Uniform Lifetime Table factor for the account owner's age",
        as_of=as_of,
        inputs={
            "age": age,
            "prior_year_end_balance": money(prior_year_end_balance),
            "life_expectancy_factor": factor,
            "tax_year": tax_year,
            "rmd_start_age": RMD_START_AGE,
        },
        assumptions=[
            f"Distributions begin at age {RMD_START_AGE} under current law.",
            "The Uniform Lifetime Table applies (not the Joint Life table for a much younger spouse).",
        ],
        limitations=[
            "Inherited accounts, still-working exceptions and 403(b) aggregation rules are not modelled.",
            "A missed distribution carries an excise tax; confirm the amount with your tax adviser.",
        ],
        result={
            "required_amount": money(required),
            "is_required": age >= RMD_START_AGE,
            "deadline": date(tax_year, 12, 31).isoformat(),
            "life_expectancy_factor": factor,
        },
    )


ASSET_LOCATION_PREFERENCE = {
    "fixed_income": "tax_deferred",
    "alternatives": "tax_deferred",
    "real_assets": "tax_deferred",
    "us_equity": "taxable",
    "intl_equity": "taxable",
    "cash": "taxable",
}


def asset_location_review(positions: Sequence[dict[str, Any]], as_of: date) -> CalcResult:
    """Flag tax-inefficient assets sitting in the wrong account type."""
    by_bucket: dict[str, float] = defaultdict(float)
    misplaced = []
    total = 0.0

    for position in positions:
        value = float(position.get("quantity") or 0.0) * float(position.get("price") or 0.0)
        total += value
        treatment = position.get("tax_treatment", "taxable")
        asset_class = position.get("asset_class", "us_equity")
        by_bucket[treatment] += value

        preferred = ASSET_LOCATION_PREFERENCE.get(asset_class, "taxable")
        if preferred == "tax_deferred" and treatment == "taxable" and value > 0:
            misplaced.append(
                {
                    "symbol": position.get("symbol"),
                    "name": position.get("name"),
                    "asset_class": asset_class,
                    "current_location": treatment,
                    "preferred_location": preferred,
                    "market_value": money(value),
                    "estimated_annual_drag": money(value * float(position.get("dividend_yield") or 0.0) * 0.35),
                }
            )

    misplaced.sort(key=lambda r: r["estimated_annual_drag"], reverse=True)

    return CalcResult(
        method="compare each holding's asset class against the preferred account type, then size the annual tax drag",
        as_of=as_of,
        inputs={"positions": len(positions), "total_market_value": money(total)},
        assumptions=[
            "Income-producing assets belong in tax-deferred accounts; growth assets belong in taxable accounts.",
            "Tax drag is estimated at a 35% ordinary rate on distributed income.",
        ],
        limitations=[
            "Relocating assets may trigger capital gains that outweigh the benefit.",
            "Account-level constraints, liquidity needs and estate objectives are not considered here.",
        ],
        result={
            "by_tax_treatment": {k: money(v) for k, v in by_bucket.items()},
            "misplaced": misplaced,
            "total_estimated_drag": money(sum(r["estimated_annual_drag"] for r in misplaced)),
        },
    )


def capital_gains_budget(
    realized_net: float, budget: float, pending_gains: float, as_of: date
) -> CalcResult:
    """How much gain is left before the household breaches its annual budget."""
    used = realized_net + pending_gains
    remaining = budget - used

    return CalcResult(
        method="remaining_budget = annual_gain_budget - (realised net gain + gains pending from proposed trades)",
        as_of=as_of,
        inputs={
            "realized_net_gain": money(realized_net),
            "pending_gains": money(pending_gains),
            "annual_budget": money(budget),
        },
        assumptions=["The gain budget is set with the client to keep taxable income inside a target bracket."],
        limitations=["The budget covers capital gains only, not other income that may push the household into a higher bracket."],
        result={
            "budget": money(budget),
            "used": money(used),
            "remaining": money(remaining),
            "utilisation": pct(safe_div(used, budget)),
            "over_budget": remaining < 0,
        },
    )
