"""Portfolio, accounts and holdings.

The database supplies positions; `app.calculations.portfolio` supplies the maths.
This service is the only place the two meet.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.calculations import portfolio as calc
from app.calculations import advisory as advisory_calc
from app.core.constants import ASSET_CLASS_LABELS, DataFreshness
from app.core.errors import NotFoundError
from app.models.identity import Household
from app.models.wealth import (
    Account,
    AllocationTarget,
    Benchmark,
    Holding,
    PerformancePoint,
    Portfolio,
    Security,
    TaxLot,
    Transaction,
)

FRESH_HOURS = 24
DELAYED_HOURS = 72


def freshness_from(timestamp: datetime | None, *, now: datetime | None = None) -> str:
    """Classify a feed timestamp so the UI never presents stale data as current (§39)."""
    if timestamp is None:
        return DataFreshness.UNAVAILABLE
    now = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age = now - timestamp
    if age <= timedelta(hours=FRESH_HOURS):
        return DataFreshness.FRESH
    if age <= timedelta(hours=DELAYED_HOURS):
        return DataFreshness.DELAYED
    return DataFreshness.STALE


class PortfolioService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- loading ------------------------------------------------------
    def household(self, household_id: str) -> Household:
        household = self.db.get(Household, household_id)
        if not household:
            raise NotFoundError("Household not found.")
        return household

    def get_portfolio(self, household_id: str) -> Portfolio | None:
        return self.db.execute(
            select(Portfolio).where(Portfolio.household_id == household_id).order_by(Portfolio.name)
        ).scalars().first()

    def accounts(self, household_id: str, *, include_liabilities: bool = True) -> list[Account]:
        stmt = (
            select(Account)
            .options(joinedload(Account.custodian))
            .where(Account.household_id == household_id)
            .order_by(Account.is_liability, Account.account_type, Account.name)
        )
        rows = list(self.db.execute(stmt).unique().scalars().all())
        return rows if include_liabilities else [a for a in rows if not a.is_liability]

    def positions(self, household_id: str, account_id: str | None = None) -> list[dict[str, Any]]:
        """Flatten holdings into the dictionary shape the calculation layer expects."""
        stmt = (
            select(Holding, Security, Account)
            .join(Security, Holding.security_id == Security.id)
            .join(Account, Holding.account_id == Account.id)
            .where(Account.household_id == household_id)
        )
        if account_id:
            stmt = stmt.where(Account.id == account_id)

        rows = self.db.execute(stmt).all()
        positions: list[dict[str, Any]] = []
        for holding, security, account in rows:
            positions.append(
                {
                    "holding_id": holding.id,
                    "security_id": security.id,
                    "account_id": account.id,
                    "account_name": account.name,
                    "account_type": account.account_type,
                    "tax_treatment": account.tax_treatment,
                    "symbol": security.symbol,
                    "name": security.name,
                    "security_type": security.security_type,
                    "asset_class": security.asset_class,
                    "asset_class_label": ASSET_CLASS_LABELS.get(security.asset_class, security.asset_class),
                    "sector": security.sector or "Diversified",
                    "region": security.region,
                    "quantity": holding.quantity,
                    "price": security.last_price,
                    "previous_close": security.previous_close or security.last_price,
                    "average_cost": holding.average_cost,
                    "beta": security.beta,
                    "volatility": security.annualised_volatility,
                    "dividend_yield": security.dividend_yield,
                    "expense_ratio": security.expense_ratio,
                    "esg_score": security.esg_score,
                    "is_municipal": security.is_municipal,
                    "price_status": security.price_status,
                    "price_as_of": security.price_as_of,
                    "acquired_on": holding.acquired_on,
                    "is_long_term": bool(
                        holding.acquired_on and (date.today() - holding.acquired_on).days >= 366
                    ),
                }
            )
        return positions

    def cash_balance(self, household_id: str) -> float:
        """Investable cash held inside managed accounts.

        Bank deposits count toward net worth but are not part of the managed
        portfolio, so they are deliberately excluded here.
        """
        return sum(
            (a.cash_balance or 0.0)
            for a in self.accounts(household_id)
            if not a.is_liability and a.account_type != "banking"
        )

    def performance_series(self, household_id: str, *, days: int | None = None) -> list[dict[str, Any]]:
        portfolio = self.get_portfolio(household_id)
        if not portfolio:
            return []
        stmt = select(PerformancePoint).where(PerformancePoint.portfolio_id == portfolio.id)
        rows = list(self.db.execute(stmt.order_by(PerformancePoint.as_of)).scalars().all())
        if days:
            rows = rows[-days:]
        return [
            {
                "as_of": row.as_of,
                "market_value": row.market_value,
                "daily_return": row.daily_return,
                "benchmark_return": row.benchmark_return,
                "cumulative_index": row.cumulative_index,
                "benchmark_index": row.benchmark_index,
                "net_flow": row.net_flow,
            }
            for row in rows
        ]

    def allocation_targets(self, household_id: str, kind: str = "strategic") -> list[dict[str, Any]]:
        portfolio = self.get_portfolio(household_id)
        if not portfolio:
            return []
        rows = self.db.execute(
            select(AllocationTarget).where(
                AllocationTarget.portfolio_id == portfolio.id, AllocationTarget.kind == kind
            )
        ).scalars().all()
        return [
            {
                "asset_class": row.asset_class,
                "asset_class_label": ASSET_CLASS_LABELS.get(row.asset_class, row.asset_class),
                "target_weight": row.target_weight,
                "min_weight": row.min_weight,
                "max_weight": row.max_weight,
                "tolerance_band": row.tolerance_band,
            }
            for row in rows
        ]

    def as_of(self, household_id: str) -> date:
        """The date the platform can stand behind for this household's figures."""
        series = self.performance_series(household_id)
        if series:
            return series[-1]["as_of"]
        portfolio = self.get_portfolio(household_id)
        if portfolio and portfolio.as_of:
            return portfolio.as_of.date()
        return date.today()

    # -- computed views ----------------------------------------------
    def valuation(self, household_id: str) -> dict[str, Any]:
        positions = self.positions(household_id)
        cash = self.cash_balance(household_id)
        return calc.value_portfolio(positions, self.as_of(household_id), cash=cash).to_dict()

    def net_worth(self, household_id: str) -> dict[str, Any]:
        accounts = self.accounts(household_id)
        rows = [
            {
                "id": a.id,
                "name": a.name,
                "account_type": a.account_type,
                "balance": a.balance,
                "is_liability": a.is_liability,
            }
            for a in accounts
        ]
        return calc.net_worth(rows, self.as_of(household_id)).to_dict()

    def net_worth_trend(self, household_id: str, months: int = 24) -> list[dict[str, Any]]:
        """Monthly net-worth history derived from the portfolio series plus static balances."""
        series = self.performance_series(household_id)
        if not series:
            return []
        nw = calc.net_worth(
            [
                {"balance": a.balance, "is_liability": a.is_liability, "account_type": a.account_type}
                for a in self.accounts(household_id)
            ],
            self.as_of(household_id),
        ).result
        latest_portfolio_value = series[-1]["market_value"]
        non_portfolio = nw["net_worth"] - latest_portfolio_value

        monthly: dict[str, dict[str, Any]] = {}
        for point in series:
            key = point["as_of"].strftime("%Y-%m")
            monthly[key] = {
                "period": key,
                "as_of": point["as_of"].isoformat(),
                "portfolio_value": round(point["market_value"], 2),
                "net_worth": round(point["market_value"] + non_portfolio, 2),
            }
        return list(monthly.values())[-months:]

    def allocation(self, household_id: str, dimension: str = "asset_class") -> dict[str, Any]:
        positions = self.positions(household_id)
        cash = self.cash_balance(household_id)
        cash_key = {"asset_class": "cash", "sector": "Cash & Equivalents", "region": "Cash"}.get(dimension, "cash")
        result = calc.allocation_breakdown(positions, dimension, self.as_of(household_id), cash=cash, cash_key=cash_key)
        payload = result.to_dict()
        for row in payload["result"]["rows"]:
            row["label"] = ASSET_CLASS_LABELS.get(row["key"], str(row["key"]).replace("_", " ").title())
        return payload

    def drift(self, household_id: str) -> dict[str, Any]:
        allocation = self.allocation(household_id)["result"]["rows"]
        targets = self.allocation_targets(household_id)
        result = calc.drift_vs_target(allocation, targets, self.as_of(household_id)).to_dict()
        for row in result["result"]["rows"]:
            row["label"] = ASSET_CLASS_LABELS.get(row["asset_class"], row["asset_class"].replace("_", " ").title())
        return result

    def concentration(self, household_id: str) -> dict[str, Any]:
        return calc.concentration(self.positions(household_id), self.as_of(household_id)).to_dict()

    def risk(self, household_id: str) -> dict[str, Any]:
        return calc.risk_metrics(
            self.positions(household_id), self.as_of(household_id), cash=self.cash_balance(household_id)
        ).to_dict()

    def income(self, household_id: str) -> dict[str, Any]:
        return calc.income_projection(self.positions(household_id), self.as_of(household_id)).to_dict()

    def performance(self, household_id: str, period: str | None = None) -> dict[str, Any]:
        series = self.performance_series(household_id)
        as_of = self.as_of(household_id)
        portfolio = self.get_portfolio(household_id)
        benchmark: Benchmark | None = portfolio.benchmark if portfolio else None

        if period:
            payload = calc.time_weighted_return(series, as_of, period).to_dict()
            payload["result"]["benchmark_name"] = benchmark.name if benchmark else None
            return payload

        periods = calc.performance_by_period(series, as_of)
        risk_adjusted = calc.risk_adjusted(series, as_of).to_dict()
        return {
            "as_of": as_of.isoformat(),
            "benchmark": {"code": benchmark.code, "name": benchmark.name} if benchmark else None,
            "periods": periods,
            "risk_adjusted": risk_adjusted,
            "series": [
                {
                    "as_of": p["as_of"].isoformat(),
                    "market_value": round(p["market_value"], 2),
                    "portfolio_index": round(p["cumulative_index"], 4),
                    "benchmark_index": round(p["benchmark_index"], 4),
                }
                for p in series
            ],
        }

    def holdings_table(
        self,
        household_id: str,
        *,
        search: str | None = None,
        asset_class: str | None = None,
        account_id: str | None = None,
        sort_by: str = "market_value",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        """The interactive holdings grid (§13): search, filter, sort, paginate."""
        positions = self.positions(household_id, account_id=account_id)
        total_value = sum(calc.position_metrics(p)["market_value"] for p in positions)

        rows = []
        for position in positions:
            metrics = calc.position_metrics(position)
            rows.append(
                {
                    "holding_id": position["holding_id"],
                    "security_id": position["security_id"],
                    "account_id": position["account_id"],
                    "account_name": position["account_name"],
                    "symbol": position["symbol"],
                    "name": position["name"],
                    "asset_class": position["asset_class"],
                    "asset_class_label": position["asset_class_label"],
                    "sector": position["sector"],
                    "region": position["region"],
                    "quantity": round(position["quantity"], 4),
                    "price": round(position["price"], 2),
                    "average_cost": round(position["average_cost"], 2),
                    "dividend_yield": position["dividend_yield"],
                    "price_status": position["price_status"],
                    "weight": round(metrics["market_value"] / total_value, 6) if total_value else 0.0,
                    **metrics,
                }
            )

        if search:
            needle = search.lower()
            rows = [r for r in rows if needle in r["symbol"].lower() or needle in r["name"].lower()]
        if asset_class:
            rows = [r for r in rows if r["asset_class"] == asset_class]

        reverse = sort_dir.lower() != "asc"
        rows.sort(key=lambda r: (r.get(sort_by) is None, r.get(sort_by)), reverse=reverse)

        total = len(rows)
        start = max(page - 1, 0) * page_size
        page_rows = rows[start : start + page_size]

        return {
            "rows": page_rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max((total + page_size - 1) // page_size, 1),
            "as_of": self.as_of(household_id).isoformat(),
            "totals": {
                "market_value": round(sum(r["market_value"] for r in rows), 2),
                "cost_basis": round(sum(r["cost_basis"] for r in rows), 2),
                "gain_loss": round(sum(r["gain_loss"] for r in rows), 2),
                "day_change": round(sum(r["day_change"] for r in rows), 2),
            },
        }

    def holding_detail(self, holding_id: str) -> dict[str, Any]:
        holding = self.db.get(Holding, holding_id)
        if not holding:
            raise NotFoundError("Holding not found.")
        security = self.db.get(Security, holding.security_id)
        account = self.db.get(Account, holding.account_id)
        lots = self.db.execute(
            select(TaxLot).where(TaxLot.holding_id == holding.id, TaxLot.is_open.is_(True)).order_by(TaxLot.acquired_on)
        ).scalars().all()

        position = {
            "quantity": holding.quantity,
            "price": security.last_price,
            "previous_close": security.previous_close,
            "average_cost": holding.average_cost,
        }
        metrics = calc.position_metrics(position)
        today = date.today()

        return {
            "holding_id": holding.id,
            "account": {"id": account.id, "name": account.name, "type": account.account_type},
            "security": {
                "id": security.id,
                "symbol": security.symbol,
                "name": security.name,
                "security_type": security.security_type,
                "asset_class": security.asset_class,
                "asset_class_label": ASSET_CLASS_LABELS.get(security.asset_class, security.asset_class),
                "sector": security.sector,
                "region": security.region,
                "last_price": security.last_price,
                "previous_close": security.previous_close,
                "dividend_yield": security.dividend_yield,
                "expense_ratio": security.expense_ratio,
                "beta": security.beta,
                "volatility": security.annualised_volatility,
                "esg_score": security.esg_score,
                "price_status": security.price_status,
                "price_as_of": security.price_as_of.isoformat() if security.price_as_of else None,
            },
            "quantity": round(holding.quantity, 4),
            **metrics,
            "annual_income": round(metrics["market_value"] * (security.dividend_yield or 0), 2),
            "tax_lots": [
                {
                    "id": lot.id,
                    "quantity": round(lot.quantity, 4),
                    "cost_per_share": round(lot.cost_per_share, 2),
                    "cost_basis": round(lot.quantity * lot.cost_per_share, 2),
                    "market_value": round(lot.quantity * security.last_price, 2),
                    "gain_loss": round(lot.quantity * (security.last_price - lot.cost_per_share), 2),
                    "acquired_on": lot.acquired_on.isoformat(),
                    "holding_period": "long_term" if (today - lot.acquired_on).days >= 366 else "short_term",
                    "washed": lot.washed,
                }
                for lot in lots
            ],
        }

    def account_detail(self, account_id: str) -> dict[str, Any]:
        account = self.db.get(Account, account_id)
        if not account:
            raise NotFoundError("Account not found.")

        positions = self.positions(account.household_id, account_id=account_id)
        valuation = calc.value_portfolio(positions, self.as_of(account.household_id), cash=account.cash_balance or 0.0)
        transactions = self.db.execute(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.trade_date.desc())
            .limit(25)
        ).scalars().all()

        return {
            "account": self.serialise_account(account),
            "valuation": valuation.to_dict(),
            "holdings": [
                {
                    "symbol": p["symbol"],
                    "name": p["name"],
                    "quantity": round(p["quantity"], 4),
                    "price": round(p["price"], 2),
                    "asset_class_label": p["asset_class_label"],
                    "holding_id": p["holding_id"],
                    **calc.position_metrics(p),
                }
                for p in sorted(positions, key=lambda p: p["quantity"] * p["price"], reverse=True)
            ],
            "transactions": [
                {
                    "id": t.id,
                    "trade_date": t.trade_date.isoformat(),
                    "type": t.transaction_type,
                    "description": t.description,
                    "amount": round(t.amount, 2),
                    "quantity": t.quantity,
                    "price": t.price,
                    "realized_gain": t.realized_gain,
                }
                for t in transactions
            ],
        }

    def serialise_account(self, account: Account) -> dict[str, Any]:
        return {
            "id": account.id,
            "name": account.name,
            "account_number_masked": account.account_number_masked,
            "account_type": account.account_type,
            "account_subtype": account.account_subtype,
            "tax_treatment": account.tax_treatment,
            "registration": account.registration,
            "balance": round(account.balance, 2),
            "cash_balance": round(account.cash_balance or 0.0, 2),
            "currency": account.currency,
            "is_liability": account.is_liability,
            "interest_rate": account.interest_rate,
            "minimum_payment": account.minimum_payment,
            "status": account.status,
            "is_external": account.is_external,
            "opened_on": account.opened_on.isoformat() if account.opened_on else None,
            "institution": account.custodian.name if account.custodian else "Self-reported",
            "connection_type": account.custodian.connection_type if account.custodian else "manual",
            "last_synced_at": account.last_synced_at.isoformat() if account.last_synced_at else None,
            "data_freshness": freshness_from(account.last_synced_at),
            "data_source": account.data_source,
        }

    def accounts_view(self, household_id: str) -> dict[str, Any]:
        accounts = self.accounts(household_id)
        rows = [self.serialise_account(a) for a in accounts]
        assets = [r for r in rows if not r["is_liability"]]
        liabilities = [r for r in rows if r["is_liability"]]
        by_type: dict[str, dict[str, Any]] = {}
        for row in rows:
            bucket = by_type.setdefault(
                row["account_type"], {"account_type": row["account_type"], "count": 0, "balance": 0.0}
            )
            bucket["count"] += 1
            bucket["balance"] += -row["balance"] if row["is_liability"] else row["balance"]

        return {
            "accounts": rows,
            "summary": {
                "total_assets": round(sum(r["balance"] for r in assets), 2),
                "total_liabilities": round(sum(r["balance"] for r in liabilities), 2),
                "net_worth": round(sum(r["balance"] for r in assets) - sum(r["balance"] for r in liabilities), 2),
                "account_count": len(rows),
                "external_count": sum(1 for r in rows if r["is_external"]),
                "by_type": list(by_type.values()),
            },
            "data_freshness": self.data_freshness(household_id),
            "as_of": self.as_of(household_id).isoformat(),
        }

    def data_freshness(self, household_id: str) -> dict[str, str]:
        accounts = self.accounts(household_id)
        feed = DataFreshness.UNAVAILABLE
        if accounts:
            statuses = [freshness_from(a.last_synced_at) for a in accounts]
            order = [DataFreshness.UNAVAILABLE, DataFreshness.STALE, DataFreshness.DELAYED, DataFreshness.FRESH]
            feed = min(statuses, key=lambda s: order.index(s))

        securities = self.db.execute(select(Security.price_status)).scalars().all()
        market = DataFreshness.FRESH
        if any(status == "stale" for status in securities):
            market = DataFreshness.STALE
        elif any(status == "delayed" for status in securities):
            market = DataFreshness.DELAYED

        return {
            "custodian_feed": str(feed),
            "market_data": str(market),
            "performance": str(DataFreshness.FRESH if self.performance_series(household_id) else DataFreshness.UNAVAILABLE),
        }

    # -- advisory tools ----------------------------------------------
    def advisory_analytics(self, household_id: str) -> dict[str, Any]:
        positions = self.positions(household_id)
        cash = self.cash_balance(household_id)
        as_of = self.as_of(household_id)
        allocation_rows = self.allocation(household_id)["result"]["rows"]
        weights = {str(row["key"]): float(row["weight"]) for row in allocation_rows}
        portfolio_value = float(self.valuation(household_id)["result"]["market_value"])

        return {
            "as_of": as_of.isoformat(),
            "correlation": advisory_calc.correlation_view(as_of).to_dict(),
            "efficient_frontier": advisory_calc.efficient_frontier(weights, as_of).to_dict(),
            "stress_tests": advisory_calc.stress_test(weights, portfolio_value, as_of).to_dict(),
            "liquidity": advisory_calc.liquidity_profile(positions, as_of, cash=cash).to_dict(),
            "esg": advisory_calc.esg_screen(positions, as_of).to_dict(),
            "risk": self.risk(household_id),
            "strategic_targets": self.allocation_targets(household_id, "strategic"),
            "tactical_targets": self.allocation_targets(household_id, "tactical"),
        }
