"""Portfolio mathematics: valuation, allocation, gain/loss, risk, performance.

Pure functions over plain dictionaries so they are trivially unit-testable and
free of database or request context.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Sequence

from app.calculations.base import CalcResult, money, pct, safe_div

PERIODS: dict[str, int | None] = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "3M": 91,
    "YTD": None,  # resolved against 1 January
    "1Y": 365,
    "3Y": 365 * 3,
    "5Y": 365 * 5,
}

TRADING_DAYS = 252


def position_metrics(position: dict[str, Any]) -> dict[str, Any]:
    """Market value, cost basis and gain/loss for a single position."""
    quantity = float(position.get("quantity") or 0.0)
    price = float(position.get("price") or 0.0)
    previous_close = float(position.get("previous_close") or price)
    average_cost = float(position.get("average_cost") or 0.0)

    market_value = quantity * price
    cost_basis = quantity * average_cost
    gain_loss = market_value - cost_basis
    day_change = quantity * (price - previous_close)

    return {
        "market_value": money(market_value),
        "cost_basis": money(cost_basis),
        "gain_loss": money(gain_loss),
        "gain_loss_percent": pct(safe_div(gain_loss, cost_basis)),
        "day_change": money(day_change),
        "day_change_percent": pct(safe_div(price - previous_close, previous_close)),
    }


def value_portfolio(positions: Sequence[dict[str, Any]], as_of: date, cash: float = 0.0) -> CalcResult:
    """Total market value, cost basis, unrealised gain and daily change."""
    market_value = cash
    cost_basis = cash
    day_change = 0.0
    priced = 0
    stale = 0

    for position in positions:
        metrics = position_metrics(position)
        market_value += metrics["market_value"]
        cost_basis += metrics["cost_basis"]
        day_change += metrics["day_change"]
        if position.get("price_status", "fresh") == "fresh":
            priced += 1
        else:
            stale += 1

    gain_loss = market_value - cost_basis
    previous_value = market_value - day_change

    return CalcResult(
        method="market_value = sum(quantity x last_price) + cash; unrealised = market_value - cost_basis",
        as_of=as_of,
        inputs={
            "position_count": len(positions),
            "cash": money(cash),
            "positions_priced": priced,
            "positions_stale": stale,
        },
        assumptions=[
            "Positions are valued at the most recent price supplied by the custodian feed.",
            "Cash balances are treated as fully liquid and valued at par.",
        ],
        limitations=[
            "Accrued interest, pending trades and unsettled cash are not reflected.",
            "Prices may lag the market; check the data-freshness badge on each panel.",
        ],
        result={
            "market_value": money(market_value),
            "cost_basis": money(cost_basis),
            "unrealized_gain": money(gain_loss),
            "unrealized_gain_percent": pct(safe_div(gain_loss, cost_basis)),
            "day_change": money(day_change),
            "day_change_percent": pct(safe_div(day_change, previous_value)),
            "cash": money(cash),
        },
    )


def allocation_breakdown(
    positions: Sequence[dict[str, Any]], key: str, as_of: date, cash: float = 0.0, cash_key: str = "cash"
) -> CalcResult:
    """Weight the portfolio by asset class, sector or region."""
    buckets: dict[str, float] = defaultdict(float)
    total = cash
    if cash:
        buckets[cash_key] += cash

    for position in positions:
        value = position_metrics(position)["market_value"]
        buckets[str(position.get(key) or "unclassified")] += value
        total += value

    rows = [
        {
            "key": bucket,
            "market_value": money(value),
            "weight": pct(safe_div(value, total)),
        }
        for bucket, value in sorted(buckets.items(), key=lambda item: item[1], reverse=True)
    ]

    return CalcResult(
        method=f"weight = market_value_of_{key} / total_market_value",
        as_of=as_of,
        inputs={"dimension": key, "total_market_value": money(total), "buckets": len(rows)},
        assumptions=["Every position is assigned to exactly one bucket; unclassified positions are grouped."],
        limitations=["Look-through into fund holdings is not applied; funds are classified at the fund level."],
        result={"total": money(total), "rows": rows},
    )


def drift_vs_target(
    current: Sequence[dict[str, Any]], targets: Sequence[dict[str, Any]], as_of: date, band: float = 0.05
) -> CalcResult:
    """Compare current weights against strategic targets and flag breaches."""
    current_map = {row["key"]: float(row["weight"]) for row in current}
    total_value = sum(float(row.get("market_value") or 0.0) for row in current)
    rows = []
    max_drift = 0.0

    keys = list(dict.fromkeys([t["asset_class"] for t in targets] + list(current_map.keys())))
    target_map = {t["asset_class"]: t for t in targets}

    for key in keys:
        target = target_map.get(key)
        target_weight = float(target["target_weight"]) if target else 0.0
        tolerance = float(target.get("tolerance_band", band)) if target else band
        actual = current_map.get(key, 0.0)
        drift = actual - target_weight
        max_drift = max(max_drift, abs(drift))
        rows.append(
            {
                "asset_class": key,
                "current_weight": pct(actual),
                "target_weight": pct(target_weight),
                "drift": pct(drift),
                "tolerance_band": pct(tolerance),
                "breached": abs(drift) > tolerance,
                "dollar_drift": money(drift * total_value),
            }
        )

    return CalcResult(
        method="drift = current_weight - target_weight; breach when |drift| > tolerance_band",
        as_of=as_of,
        inputs={"total_market_value": money(total_value), "default_band": band},
        assumptions=["Targets come from the approved investment policy for this portfolio."],
        limitations=["Drift ignores in-flight trades and scheduled contributions."],
        result={
            "rows": sorted(rows, key=lambda r: abs(r["drift"]), reverse=True),
            "max_drift": pct(max_drift),
            "breach_count": sum(1 for r in rows if r["breached"]),
        },
    )


SINGLE_NAME_TYPES = {"stock", "bond", "option", "private"}


def concentration(positions: Sequence[dict[str, Any]], as_of: date, threshold: float = 0.10) -> CalcResult:
    """Concentration risk, separating single names from diversified funds.

    A 12% position in a total-market index fund is not the same risk as a 12%
    position in one company, so the two are measured separately and the
    single-name figure is what drives the concentration warning.
    """
    valued = []
    total = 0.0
    for position in positions:
        value = position_metrics(position)["market_value"]
        total += value
        valued.append({**position, "market_value": value})

    rows = []
    hhi = 0.0
    for position in sorted(valued, key=lambda p: p["market_value"], reverse=True):
        weight = safe_div(position["market_value"], total)
        hhi += weight**2
        is_single_name = str(position.get("security_type", "etf")) in SINGLE_NAME_TYPES
        rows.append(
            {
                "symbol": position.get("symbol"),
                "name": position.get("name"),
                "security_type": position.get("security_type", "etf"),
                "is_single_name": is_single_name,
                "market_value": money(position["market_value"]),
                "weight": pct(weight),
                "exceeds_threshold": weight > threshold and is_single_name,
            }
        )

    single_names = [r for r in rows if r["is_single_name"]]
    top = rows[0] if rows else None
    top_single_name = single_names[0] if single_names else None
    top5 = sum(r["weight"] for r in rows[:5])

    return CalcResult(
        method="weight = position_value / portfolio_value; HHI = sum(weight^2)",
        as_of=as_of,
        inputs={"threshold": threshold, "position_count": len(rows), "total_market_value": money(total)},
        assumptions=[
            f"A single-name position above {threshold:.0%} of the portfolio is flagged for review.",
            "Diversified funds are reported by weight but are not treated as single-name concentration.",
        ],
        limitations=[
            "Concentration is measured at the position level; overlapping exposure inside funds is not aggregated.",
            "Two funds tracking the same index appear as separate positions.",
        ],
        result={
            "rows": rows,
            "top_position": top,
            "top_single_name": top_single_name,
            "single_name_weight": pct(sum(r["weight"] for r in single_names)),
            "top_five_weight": pct(top5),
            "hhi": pct(hhi),
            "flagged": [r for r in rows if r["exceeds_threshold"]],
        },
    )


def risk_metrics(positions: Sequence[dict[str, Any]], as_of: date, cash: float = 0.0) -> CalcResult:
    """Value-weighted beta and volatility, plus an equity-exposure summary."""
    total = cash
    weighted_beta = 0.0
    weighted_vol = 0.0
    equity_value = 0.0

    valued = []
    for position in positions:
        value = position_metrics(position)["market_value"]
        total += value
        valued.append((position, value))

    for position, value in valued:
        weight = safe_div(value, total)
        weighted_beta += weight * float(position.get("beta") or 1.0)
        weighted_vol += weight * float(position.get("volatility") or 0.15)
        if str(position.get("asset_class", "")).endswith("equity"):
            equity_value += value

    # Cash contributes zero beta/volatility but does dilute both.
    return CalcResult(
        method="portfolio_beta = sum(weight_i x beta_i); portfolio_volatility = sum(weight_i x sigma_i)",
        as_of=as_of,
        inputs={"total_market_value": money(total), "cash": money(cash)},
        assumptions=[
            "Security beta and volatility are supplied as static reference data for this demonstration dataset.",
            "A weighted average of volatilities is used rather than a full covariance matrix.",
        ],
        limitations=[
            "Because correlations are not modelled, the volatility figure overstates risk for a diversified book.",
            "Beta is measured against the portfolio benchmark, not a global market portfolio.",
        ],
        result={
            "beta": round(weighted_beta, 3),
            "volatility": pct(weighted_vol),
            "equity_exposure": pct(safe_div(equity_value, total)),
            "cash_exposure": pct(safe_div(cash, total)),
        },
    )


def time_weighted_return(series: Sequence[dict[str, Any]], as_of: date, period: str = "YTD") -> CalcResult:
    """Chain daily returns over a period and compare with the benchmark."""
    if not series:
        return CalcResult(
            method="time_weighted_return = product(1 + r_t) - 1",
            as_of=as_of,
            result={"return": 0.0, "benchmark_return": 0.0, "excess_return": 0.0, "points": 0},
            assumptions=[],
            limitations=["No performance history is available for this portfolio."],
        )

    ordered = sorted(series, key=lambda p: p["as_of"])
    end = ordered[-1]["as_of"]
    days = PERIODS.get(period)
    if period == "YTD":
        start_cutoff = date(end.year, 1, 1)
    elif days is None:
        start_cutoff = ordered[0]["as_of"]
    else:
        start_cutoff = date.fromordinal(max(ordered[0]["as_of"].toordinal(), end.toordinal() - days))

    window = [p for p in ordered if p["as_of"] >= start_cutoff]
    if len(window) < 2:
        window = ordered[-2:]

    growth = 1.0
    bench_growth = 1.0
    for point in window[1:]:
        growth *= 1 + float(point.get("daily_return") or 0.0)
        bench_growth *= 1 + float(point.get("benchmark_return") or 0.0)

    portfolio_return = growth - 1
    benchmark_return = bench_growth - 1
    elapsed_days = max((window[-1]["as_of"] - window[0]["as_of"]).days, 1)
    annualised = (1 + portfolio_return) ** (365 / elapsed_days) - 1 if elapsed_days >= 365 else None

    return CalcResult(
        method="time_weighted_return = product(1 + daily_return) - 1, chained across the period",
        as_of=end,
        inputs={
            "period": period,
            "start": window[0]["as_of"].isoformat(),
            "end": end.isoformat(),
            "observations": len(window),
        },
        assumptions=[
            "Daily returns are net of investment-management fees and gross of any external advisory fee.",
            "Time weighting removes the effect of client contributions and withdrawals.",
        ],
        limitations=[
            "Periods shorter than a year are not annualised.",
            "Returns for periods longer than the available history are truncated to the data on file.",
        ],
        result={
            "period": period,
            "return": pct(portfolio_return),
            "benchmark_return": pct(benchmark_return),
            "excess_return": pct(portfolio_return - benchmark_return),
            "annualized_return": pct(annualised) if annualised is not None else None,
            "start_value": money(float(window[0].get("market_value") or 0.0)),
            "end_value": money(float(window[-1].get("market_value") or 0.0)),
            "points": len(window),
        },
    )


def performance_by_period(series: Sequence[dict[str, Any]], as_of: date) -> dict[str, Any]:
    """Return dictionary keyed by the standard period buttons (§12)."""
    return {period: time_weighted_return(series, as_of, period).result for period in PERIODS}


def risk_adjusted(series: Sequence[dict[str, Any]], as_of: date, risk_free_rate: float = 0.042) -> CalcResult:
    """Annualised volatility, Sharpe ratio, max drawdown and tracking error."""
    returns = [float(p.get("daily_return") or 0.0) for p in sorted(series, key=lambda p: p["as_of"])]
    bench = [float(p.get("benchmark_return") or 0.0) for p in sorted(series, key=lambda p: p["as_of"])]

    if len(returns) < 3:
        return CalcResult(
            method="annualised statistics from the daily return series",
            as_of=as_of,
            result={"volatility": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0, "tracking_error": 0.0},
            limitations=["Not enough history to compute risk statistics."],
        )

    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    volatility = math.sqrt(variance) * math.sqrt(TRADING_DAYS)
    annual_return = (1 + mean) ** TRADING_DAYS - 1
    sharpe = safe_div(annual_return - risk_free_rate, volatility)

    active = [r - b for r, b in zip(returns, bench)]
    active_mean = sum(active) / len(active)
    active_var = sum((a - active_mean) ** 2 for a in active) / (len(active) - 1)
    tracking_error = math.sqrt(active_var) * math.sqrt(TRADING_DAYS)

    peak = 1.0
    equity = 1.0
    max_drawdown = 0.0
    for r in returns:
        equity *= 1 + r
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)

    return CalcResult(
        method="volatility = stdev(daily) x sqrt(252); sharpe = (annualised return - risk free) / volatility",
        as_of=as_of,
        inputs={"observations": len(returns), "risk_free_rate": risk_free_rate, "trading_days": TRADING_DAYS},
        assumptions=[
            f"A {risk_free_rate:.2%} annual risk-free rate is used.",
            "252 trading days per year.",
        ],
        limitations=[
            "Statistics describe the observed history only and are not predictive.",
            "Daily returns are assumed independent, which understates tail risk.",
        ],
        result={
            "volatility": pct(volatility),
            "annualized_return": pct(annual_return),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown": pct(max_drawdown),
            "tracking_error": pct(tracking_error),
            "information_ratio": round(safe_div(active_mean * TRADING_DAYS, tracking_error), 3),
        },
    )


def income_projection(positions: Sequence[dict[str, Any]], as_of: date) -> CalcResult:
    """Forward twelve-month income from stated dividend yields."""
    total_income = 0.0
    total_value = 0.0
    rows = []
    for position in positions:
        value = position_metrics(position)["market_value"]
        yield_rate = float(position.get("dividend_yield") or 0.0)
        income = value * yield_rate
        total_income += income
        total_value += value
        if income > 0:
            rows.append(
                {
                    "symbol": position.get("symbol"),
                    "name": position.get("name"),
                    "market_value": money(value),
                    "yield": pct(yield_rate),
                    "annual_income": money(income),
                    "is_municipal": bool(position.get("is_municipal")),
                }
            )

    municipal_income = sum(r["annual_income"] for r in rows if r["is_municipal"])

    return CalcResult(
        method="forward_income = sum(market_value x stated_dividend_yield)",
        as_of=as_of,
        inputs={"income_positions": len(rows), "total_market_value": money(total_value)},
        assumptions=["Current stated yields are held constant for the next twelve months."],
        limitations=[
            "Distributions are not guaranteed and issuers may cut or suspend them.",
            "Return of capital and special distributions are excluded.",
        ],
        result={
            "annual_income": money(total_income),
            "monthly_income": money(total_income / 12),
            "portfolio_yield": pct(safe_div(total_income, total_value)),
            "municipal_income": money(municipal_income),
            "taxable_income": money(total_income - municipal_income),
            "rows": sorted(rows, key=lambda r: r["annual_income"], reverse=True),
        },
    )


def net_worth(accounts: Iterable[dict[str, Any]], as_of: date) -> CalcResult:
    """Assets minus liabilities across every linked account."""
    assets = 0.0
    liabilities = 0.0
    by_type: dict[str, float] = defaultdict(float)

    account_list = list(accounts)
    for account in account_list:
        balance = float(account.get("balance") or 0.0)
        if account.get("is_liability"):
            liabilities += abs(balance)
            by_type[str(account.get("account_type"))] -= abs(balance)
        else:
            assets += balance
            by_type[str(account.get("account_type"))] += balance

    return CalcResult(
        method="net_worth = sum(asset_account_balances) - sum(liability_account_balances)",
        as_of=as_of,
        inputs={"account_count": len(account_list)},
        assumptions=[
            "Balances reflect the latest custodian or aggregator sync for each account.",
            "Manually tracked assets are included at the value the household last supplied.",
        ],
        limitations=[
            "Illiquid or unlinked assets not entered in the platform are excluded.",
            "Liability balances exclude accrued interest since the last statement.",
        ],
        result={
            "total_assets": money(assets),
            "total_liabilities": money(liabilities),
            "net_worth": money(assets - liabilities),
            "by_account_type": {k: money(v) for k, v in by_type.items()},
            "leverage_ratio": pct(safe_div(liabilities, assets)),
        },
    )
