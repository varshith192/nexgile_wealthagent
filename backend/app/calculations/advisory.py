"""Advisor portfolio tools: correlation, frontier, stress tests, liquidity, ESG, rebalancing."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Sequence

from app.calculations.base import CalcResult, money, pct, safe_div

# Long-run capital market assumptions used for the frontier and stress tests.
# Static reference data for this demonstration dataset; a production system
# would source these from the investment team's published CMAs.
CAPITAL_MARKET_ASSUMPTIONS: dict[str, dict[str, float]] = {
    "us_equity": {"expected_return": 0.072, "volatility": 0.163},
    "intl_equity": {"expected_return": 0.078, "volatility": 0.181},
    "fixed_income": {"expected_return": 0.045, "volatility": 0.058},
    "cash": {"expected_return": 0.036, "volatility": 0.006},
    "alternatives": {"expected_return": 0.068, "volatility": 0.121},
    "real_assets": {"expected_return": 0.058, "volatility": 0.142},
}

CORRELATION_MATRIX: dict[str, dict[str, float]] = {
    "us_equity": {"us_equity": 1.00, "intl_equity": 0.84, "fixed_income": 0.11, "cash": 0.00, "alternatives": 0.55, "real_assets": 0.62},
    "intl_equity": {"us_equity": 0.84, "intl_equity": 1.00, "fixed_income": 0.15, "cash": 0.00, "alternatives": 0.52, "real_assets": 0.58},
    "fixed_income": {"us_equity": 0.11, "intl_equity": 0.15, "fixed_income": 1.00, "cash": 0.18, "alternatives": 0.21, "real_assets": 0.24},
    "cash": {"us_equity": 0.00, "intl_equity": 0.00, "fixed_income": 0.18, "cash": 1.00, "alternatives": 0.05, "real_assets": 0.03},
    "alternatives": {"us_equity": 0.55, "intl_equity": 0.52, "fixed_income": 0.21, "cash": 0.05, "alternatives": 1.00, "real_assets": 0.47},
    "real_assets": {"us_equity": 0.62, "intl_equity": 0.58, "fixed_income": 0.24, "cash": 0.03, "alternatives": 0.47, "real_assets": 1.00},
}

STRESS_SCENARIOS: dict[str, dict[str, Any]] = {
    "global_financial_crisis": {
        "label": "Global Financial Crisis (2008)",
        "shocks": {"us_equity": -0.37, "intl_equity": -0.43, "fixed_income": 0.05, "cash": 0.02, "alternatives": -0.21, "real_assets": -0.40},
    },
    "covid_drawdown": {
        "label": "Pandemic Drawdown (Q1 2020)",
        "shocks": {"us_equity": -0.20, "intl_equity": -0.24, "fixed_income": 0.03, "cash": 0.00, "alternatives": -0.12, "real_assets": -0.26},
    },
    "rate_shock": {
        "label": "Rapid Rate Rise (+300bp)",
        "shocks": {"us_equity": -0.12, "intl_equity": -0.14, "fixed_income": -0.13, "cash": 0.01, "alternatives": -0.06, "real_assets": -0.16},
    },
    "stagflation": {
        "label": "Stagflation",
        "shocks": {"us_equity": -0.18, "intl_equity": -0.20, "fixed_income": -0.08, "cash": -0.03, "alternatives": 0.04, "real_assets": 0.09},
    },
}

LIQUIDITY_TIERS: dict[str, int] = {
    "cash": 0,
    "fixed_income": 2,
    "us_equity": 2,
    "intl_equity": 3,
    "real_assets": 5,
    "alternatives": 45,
}


def portfolio_expected_risk(weights: dict[str, float]) -> tuple[float, float]:
    """Expected return and volatility for an asset-class weight vector."""
    expected = sum(w * CAPITAL_MARKET_ASSUMPTIONS.get(a, {}).get("expected_return", 0.0) for a, w in weights.items())
    variance = 0.0
    for a, wa in weights.items():
        for b, wb in weights.items():
            vol_a = CAPITAL_MARKET_ASSUMPTIONS.get(a, {}).get("volatility", 0.0)
            vol_b = CAPITAL_MARKET_ASSUMPTIONS.get(b, {}).get("volatility", 0.0)
            corr = CORRELATION_MATRIX.get(a, {}).get(b, 0.0 if a != b else 1.0)
            variance += wa * wb * vol_a * vol_b * corr
    return expected, math.sqrt(max(variance, 0.0))


def correlation_view(as_of: date) -> CalcResult:
    """The asset-class correlation matrix used by every advisory tool."""
    return CalcResult(
        method="static long-run correlation matrix across asset classes",
        as_of=as_of,
        inputs={"asset_classes": list(CORRELATION_MATRIX.keys())},
        assumptions=["Correlations are long-run averages and are held constant."],
        limitations=[
            "Correlations rise toward one in a crisis, exactly when diversification is needed most.",
            "This matrix is reference data for the demonstration dataset, not a live risk model.",
        ],
        result={"matrix": CORRELATION_MATRIX, "capital_market_assumptions": CAPITAL_MARKET_ASSUMPTIONS},
    )


def efficient_frontier(current_weights: dict[str, float], as_of: date, points: int = 12) -> CalcResult:
    """Frontier from a conservative to an aggressive equity glidepath."""
    frontier = []
    for i in range(points):
        equity = 0.20 + (0.75 - 0.20) * (i / max(points - 1, 1))
        weights = {
            "us_equity": equity * 0.62,
            "intl_equity": equity * 0.38,
            "fixed_income": (1 - equity) * 0.72,
            "cash": (1 - equity) * 0.10,
            "alternatives": (1 - equity) * 0.12,
            "real_assets": (1 - equity) * 0.06,
        }
        expected, volatility = portfolio_expected_risk(weights)
        frontier.append(
            {
                "label": f"{equity:.0%} equity",
                "equity_weight": pct(equity),
                "expected_return": pct(expected),
                "volatility": pct(volatility),
                "sharpe": round(safe_div(expected - 0.036, volatility), 3),
            }
        )

    current_return, current_vol = portfolio_expected_risk(current_weights)

    return CalcResult(
        method="mean-variance frontier from capital market assumptions and the asset-class correlation matrix",
        as_of=as_of,
        inputs={"current_weights": {k: pct(v) for k, v in current_weights.items()}, "points": points},
        assumptions=[
            "Long-run capital market assumptions are as published for this demonstration dataset.",
            "The frontier is traced along an equity/defensive glidepath rather than a full optimiser.",
        ],
        limitations=[
            "Mean-variance optimisation is highly sensitive to its inputs and ignores higher moments.",
            "The frontier assumes no taxes, no trading costs and continuous rebalancing.",
        ],
        result={
            "frontier": frontier,
            "current": {
                "label": "Current portfolio",
                "expected_return": pct(current_return),
                "volatility": pct(current_vol),
                "sharpe": round(safe_div(current_return - 0.036, current_vol), 3),
            },
        },
    )


def stress_test(weights: dict[str, float], portfolio_value: float, as_of: date) -> CalcResult:
    """Apply historical shock vectors to the current allocation."""
    rows = []
    for key, scenario in STRESS_SCENARIOS.items():
        impact = sum(weights.get(asset, 0.0) * shock for asset, shock in scenario["shocks"].items())
        rows.append(
            {
                "key": key,
                "label": scenario["label"],
                "portfolio_impact_percent": pct(impact),
                "portfolio_impact_amount": money(portfolio_value * impact),
                "resulting_value": money(portfolio_value * (1 + impact)),
                "shocks": scenario["shocks"],
            }
        )

    rows.sort(key=lambda r: r["portfolio_impact_percent"])

    return CalcResult(
        method="scenario_impact = sum(asset_class_weight x historical shock for that asset class)",
        as_of=as_of,
        inputs={"portfolio_value": money(portfolio_value), "weights": {k: pct(v) for k, v in weights.items()}},
        assumptions=[
            "Shock vectors approximate peak-to-trough asset-class moves in each historical episode.",
            "The allocation is held fixed through the shock with no rebalancing or client behaviour change.",
        ],
        limitations=[
            "History does not repeat exactly; a future crisis may hit different assets.",
            "Single-period shocks say nothing about how long a recovery takes.",
        ],
        result={"scenarios": rows, "worst_case": rows[0] if rows else None},
    )


def liquidity_profile(positions: Sequence[dict[str, Any]], as_of: date, cash: float = 0.0) -> CalcResult:
    """Bucket the portfolio by how quickly it can be turned into cash."""
    buckets: dict[str, float] = defaultdict(float)
    total = cash
    buckets["immediate"] += cash

    for position in positions:
        value = float(position.get("quantity") or 0.0) * float(position.get("price") or 0.0)
        total += value
        days = LIQUIDITY_TIERS.get(str(position.get("asset_class")), 3)
        if days <= 0:
            bucket = "immediate"
        elif days <= 3:
            bucket = "under_1_week"
        elif days <= 30:
            bucket = "under_1_month"
        else:
            bucket = "over_1_month"
        buckets[bucket] += value

    rows = [
        {"bucket": bucket, "market_value": money(value), "weight": pct(safe_div(value, total))}
        for bucket, value in buckets.items()
    ]
    order = {"immediate": 0, "under_1_week": 1, "under_1_month": 2, "over_1_month": 3}
    rows.sort(key=lambda r: order.get(r["bucket"], 9))
    liquid = sum(r["market_value"] for r in rows if r["bucket"] in {"immediate", "under_1_week"})

    return CalcResult(
        method="each asset class is mapped to an expected settlement window and weighted by market value",
        as_of=as_of,
        inputs={"total_market_value": money(total), "cash": money(cash)},
        assumptions=["Settlement windows are typical for each asset class in normal market conditions."],
        limitations=[
            "Liquidity can disappear under stress, particularly for alternatives and private assets.",
            "Lock-ups, gates and redemption windows on specific funds are not modelled.",
        ],
        result={
            "buckets": rows,
            "liquid_value": money(liquid),
            "liquid_percent": pct(safe_div(liquid, total)),
            "illiquid_percent": pct(safe_div(total - liquid, total)),
        },
    )


def esg_screen(positions: Sequence[dict[str, Any]], as_of: date, minimum_score: float = 50.0) -> CalcResult:
    """Weighted ESG score and a list of holdings below the screen."""
    total = 0.0
    weighted = 0.0
    unscored = 0.0
    flagged = []

    for position in positions:
        value = float(position.get("quantity") or 0.0) * float(position.get("price") or 0.0)
        total += value
        score = position.get("esg_score")
        if score is None:
            unscored += value
            continue
        weighted += value * float(score)
        if float(score) < minimum_score:
            flagged.append(
                {
                    "symbol": position.get("symbol"),
                    "name": position.get("name"),
                    "esg_score": float(score),
                    "market_value": money(value),
                }
            )

    scored_value = total - unscored
    flagged.sort(key=lambda r: r["esg_score"])

    return CalcResult(
        method="portfolio ESG score = market-value-weighted average of scored holdings",
        as_of=as_of,
        inputs={"minimum_score": minimum_score, "total_market_value": money(total)},
        assumptions=["ESG scores are third-party reference data on a 0-100 scale for this demonstration dataset."],
        limitations=[
            "ESG ratings differ substantially between providers and are not comparable across vendors.",
            "Fund-level scores do not look through to underlying issuers.",
        ],
        result={
            "portfolio_score": round(safe_div(weighted, scored_value), 1),
            "coverage": pct(safe_div(scored_value, total)),
            "unscored_value": money(unscored),
            "below_screen": flagged,
            "below_screen_value": money(sum(r["market_value"] for r in flagged)),
        },
    )


def build_rebalance_plan(
    positions: Sequence[dict[str, Any]],
    targets: Sequence[dict[str, Any]],
    as_of: date,
    *,
    cash: float = 0.0,
    marginal_rate: float = 0.35,
    ltcg_rate: float = 0.20,
    minimum_trade: float = 2500.0,
    trading_cost_bps: float = 3.0,
) -> CalcResult:
    """Turn allocation drift into a concrete, reviewable trade list.

    The plan is a proposal only. It reaches the market only after human review,
    approval and a simulated execution step.
    """
    total = cash + sum(float(p.get("quantity") or 0.0) * float(p.get("price") or 0.0) for p in positions)
    target_map = {t["asset_class"]: float(t["target_weight"]) for t in targets}

    by_class: dict[str, float] = defaultdict(float)
    for position in positions:
        value = float(position.get("quantity") or 0.0) * float(position.get("price") or 0.0)
        by_class[str(position.get("asset_class"))] += value
    by_class["cash"] += cash

    class_deltas = {
        asset_class: (target_map.get(asset_class, 0.0) * total) - by_class.get(asset_class, 0.0)
        for asset_class in set(list(target_map.keys()) + list(by_class.keys()))
    }

    trades = []
    total_realized_gain = 0.0
    total_tax = 0.0
    turnover = 0.0

    for asset_class, delta in sorted(class_deltas.items(), key=lambda kv: abs(kv[1]), reverse=True):
        if asset_class == "cash" or abs(delta) < minimum_trade:
            continue

        candidates = [p for p in positions if str(p.get("asset_class")) == asset_class]
        if not candidates:
            continue

        if delta < 0:
            # Sell from the largest positions, preferring long-term lots.
            candidates.sort(
                key=lambda p: float(p.get("quantity") or 0.0) * float(p.get("price") or 0.0), reverse=True
            )
        else:
            candidates.sort(key=lambda p: float(p.get("expense_ratio") or 0.01))

        remaining = abs(delta)
        for position in candidates:
            if remaining < minimum_trade:
                break
            price = float(position.get("price") or 0.0)
            if price <= 0:
                continue
            position_value = float(position.get("quantity") or 0.0) * price
            amount = min(remaining, position_value) if delta < 0 else remaining
            if amount < minimum_trade:
                continue
            quantity = round(amount / price, 4)
            side = "sell" if delta < 0 else "buy"

            realized_gain = 0.0
            tax_impact = 0.0
            if side == "sell":
                average_cost = float(position.get("average_cost") or price)
                realized_gain = quantity * (price - average_cost)
                is_long_term = bool(position.get("is_long_term", True))
                rate = ltcg_rate if is_long_term else marginal_rate
                tax_impact = max(realized_gain, 0.0) * rate
                total_realized_gain += realized_gain
                total_tax += tax_impact

            turnover += amount
            remaining -= amount
            trades.append(
                {
                    "account_id": position.get("account_id"),
                    "account_name": position.get("account_name"),
                    "security_id": position.get("security_id"),
                    "symbol": position.get("symbol"),
                    "name": position.get("name"),
                    "asset_class": asset_class,
                    "side": side,
                    "quantity": quantity,
                    "estimated_price": round(price, 2),
                    "estimated_amount": money(amount),
                    "realized_gain": money(realized_gain),
                    "tax_impact": money(tax_impact),
                    "rationale": (
                        f"{'Reduce' if side == 'sell' else 'Increase'} {asset_class.replace('_', ' ')} "
                        f"toward its {target_map.get(asset_class, 0):.0%} target"
                    ),
                }
            )

    drift_rows = [
        {
            "asset_class": asset_class,
            "current_weight": pct(safe_div(by_class.get(asset_class, 0.0), total)),
            "target_weight": pct(target_map.get(asset_class, 0.0)),
            "drift": pct(safe_div(by_class.get(asset_class, 0.0), total) - target_map.get(asset_class, 0.0)),
            "dollar_delta": money(delta),
        }
        for asset_class, delta in class_deltas.items()
    ]
    drift_rows.sort(key=lambda r: abs(r["drift"]), reverse=True)
    trading_cost = turnover * (trading_cost_bps / 10_000)

    return CalcResult(
        method=(
            "dollar gap per asset class = (target weight x portfolio value) - current value; "
            "gaps above the minimum trade size are filled from existing positions"
        ),
        as_of=as_of,
        inputs={
            "portfolio_value": money(total),
            "minimum_trade": minimum_trade,
            "trading_cost_bps": trading_cost_bps,
            "marginal_rate": marginal_rate,
            "ltcg_rate": ltcg_rate,
        },
        assumptions=[
            "Trades execute at the last available price with no market impact.",
            "Sales are assumed to come from long-term lots unless a position is marked short-term.",
            f"Gaps smaller than ${minimum_trade:,.0f} are left alone to avoid uneconomic trades.",
        ],
        limitations=[
            "This is a proposal, not an order. Nothing is sent to a custodian or broker by this platform.",
            "Wash-sale interactions and lot-level optimisation require a separate tax review.",
            "Prices move between proposal and execution; final amounts will differ.",
        ],
        result={
            "trades": trades,
            "trade_count": len(trades),
            "drift": drift_rows,
            "max_drift": pct(max((abs(r["drift"]) for r in drift_rows), default=0.0)),
            "turnover_amount": money(turnover),
            "turnover_percent": pct(safe_div(turnover, total)),
            "estimated_realized_gain": money(total_realized_gain),
            "estimated_tax_cost": money(total_tax),
            "estimated_trading_cost": money(trading_cost),
            "cash_impact": money(sum(t["estimated_amount"] * (1 if t["side"] == "sell" else -1) for t in trades)),
            "portfolio_value": money(total),
        },
    )
