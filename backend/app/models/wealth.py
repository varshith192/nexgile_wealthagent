"""Accounts, securities, positions, lots, transactions and performance."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class Custodian(BaseModel):
    __tablename__ = "custodians"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    short_name: Mapped[str] = mapped_column(String(48))
    connection_type: Mapped[str] = mapped_column(String(32), default="aggregated")
    feed_status: Mapped[str] = mapped_column(String(24), default="fresh")
    logo_hint: Mapped[str | None] = mapped_column(String(32))


class Account(BaseModel):
    __tablename__ = "accounts"
    __table_args__ = (
        Index("ix_accounts_household_type", "household_id", "account_type"),
        Index("ix_accounts_client", "client_id"),
    )

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"))
    custodian_id: Mapped[str | None] = mapped_column(ForeignKey("custodians.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160))
    account_number_masked: Mapped[str] = mapped_column(String(32))
    account_type: Mapped[str] = mapped_column(String(32), index=True)
    account_subtype: Mapped[str | None] = mapped_column(String(48))
    tax_treatment: Mapped[str] = mapped_column(String(32), default="taxable")
    registration: Mapped[str] = mapped_column(String(64), default="individual")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    # Cached rollup; holdings remain the source of truth for invested accounts.
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    cash_balance: Mapped[float] = mapped_column(Float, default=0.0)
    is_liability: Mapped[bool] = mapped_column(Boolean, default=False)
    interest_rate: Mapped[float | None] = mapped_column(Float)
    minimum_payment: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), default="active")
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    opened_on: Mapped[date | None] = mapped_column(Date())
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_source: Mapped[str] = mapped_column(String(48), default="custodian_feed")

    custodian: Mapped[Custodian | None] = relationship()
    holdings: Mapped[list["Holding"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class Security(BaseModel):
    __tablename__ = "securities"
    __table_args__ = (Index("ix_securities_class", "asset_class", "sector"),)

    symbol: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    security_type: Mapped[str] = mapped_column(String(32), default="etf")
    asset_class: Mapped[str] = mapped_column(String(32), index=True)
    sector: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str] = mapped_column(String(48), default="United States")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    last_price: Mapped[float] = mapped_column(Float, default=0.0)
    previous_close: Mapped[float] = mapped_column(Float, default=0.0)
    dividend_yield: Mapped[float] = mapped_column(Float, default=0.0)
    expense_ratio: Mapped[float | None] = mapped_column(Float)
    beta: Mapped[float] = mapped_column(Float, default=1.0)
    annualised_volatility: Mapped[float] = mapped_column(Float, default=0.15)
    esg_score: Mapped[float | None] = mapped_column(Float)
    is_municipal: Mapped[bool] = mapped_column(Boolean, default=False)
    # Wash-sale support: a replacement candidate must NOT be substantially identical.
    substantially_identical_to: Mapped[str | None] = mapped_column(String(24))
    price_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_status: Mapped[str] = mapped_column(String(24), default="fresh")


class Benchmark(BaseModel):
    __tablename__ = "benchmarks"

    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text())
    composition: Mapped[dict] = mapped_column(default=dict)


class Portfolio(BaseModel):
    __tablename__ = "portfolios"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    strategy: Mapped[str] = mapped_column(String(64), default="Balanced Growth")
    benchmark_id: Mapped[str | None] = mapped_column(ForeignKey("benchmarks.id", ondelete="SET NULL"))
    inception_date: Mapped[date | None] = mapped_column(Date())
    management_fee_bps: Mapped[int] = mapped_column(Integer, default=75)
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    benchmark: Mapped[Benchmark | None] = relationship()


class Holding(BaseModel):
    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("account_id", "security_id", name="uq_holding_account_security"),
        Index("ix_holdings_security", "security_id"),
    )

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    portfolio_id: Mapped[str | None] = mapped_column(ForeignKey("portfolios.id", ondelete="SET NULL"), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    average_cost: Mapped[float] = mapped_column(Float, default=0.0)
    acquired_on: Mapped[date | None] = mapped_column(Date())
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped[Account] = relationship(back_populates="holdings")
    security: Mapped[Security] = relationship()
    tax_lots: Mapped[list["TaxLot"]] = relationship(back_populates="holding", cascade="all, delete-orphan")


class TaxLot(BaseModel):
    __tablename__ = "tax_lots"
    __table_args__ = (Index("ix_tax_lots_acquired", "acquired_on"),)

    holding_id: Mapped[str] = mapped_column(ForeignKey("holdings.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    cost_per_share: Mapped[float] = mapped_column(Float)
    acquired_on: Mapped[date] = mapped_column(Date())
    lot_method: Mapped[str] = mapped_column(String(16), default="FIFO")
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    washed: Mapped[bool] = mapped_column(Boolean, default=False)

    holding: Mapped[Holding] = relationship(back_populates="tax_lots")


class Transaction(BaseModel):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_account_date", "account_id", "trade_date"),)

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id", ondelete="SET NULL"))
    transaction_type: Mapped[str] = mapped_column(String(32), index=True)
    quantity: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    trade_date: Mapped[date] = mapped_column(Date(), index=True)
    settle_date: Mapped[date | None] = mapped_column(Date())
    description: Mapped[str | None] = mapped_column(Text())
    realized_gain: Mapped[float | None] = mapped_column(Float)
    is_long_term: Mapped[bool | None] = mapped_column(Boolean)


class PortfolioPosition(BaseModel):
    """Point-in-time snapshot of a portfolio position (books of record)."""

    __tablename__ = "portfolio_positions"
    __table_args__ = (Index("ix_position_portfolio_asof", "portfolio_id", "as_of"),)

    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    quantity: Mapped[float] = mapped_column(Float)
    market_value: Mapped[float] = mapped_column(Float)
    cost_basis: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    as_of: Mapped[date] = mapped_column(Date())


class AllocationTarget(BaseModel):
    """Strategic / tactical targets per asset class."""

    __tablename__ = "allocations"
    __table_args__ = (UniqueConstraint("portfolio_id", "asset_class", "kind", name="uq_allocation_target"),)

    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    asset_class: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(24), default="strategic")
    target_weight: Mapped[float] = mapped_column(Float)
    min_weight: Mapped[float] = mapped_column(Float, default=0.0)
    max_weight: Mapped[float] = mapped_column(Float, default=1.0)
    tolerance_band: Mapped[float] = mapped_column(Float, default=0.05)


class PerformancePoint(BaseModel):
    """Daily time-weighted series for a portfolio and its benchmark."""

    __tablename__ = "performance"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "as_of", name="uq_performance_point"),
        Index("ix_performance_asof", "as_of"),
    )

    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    as_of: Mapped[date] = mapped_column(Date())
    market_value: Mapped[float] = mapped_column(Float)
    net_flow: Mapped[float] = mapped_column(Float, default=0.0)
    daily_return: Mapped[float] = mapped_column(Float, default=0.0)
    benchmark_return: Mapped[float] = mapped_column(Float, default=0.0)
    cumulative_index: Mapped[float] = mapped_column(Float, default=100.0)
    benchmark_index: Mapped[float] = mapped_column(Float, default=100.0)
