"""Tax centre entities: opportunities, harvests, wash-sale windows, RMDs."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class TaxOpportunity(BaseModel):
    __tablename__ = "tax_opportunities"
    __table_args__ = (Index("ix_tax_opps_household_status", "household_id", "status"),)

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id", ondelete="SET NULL"))
    opportunity_type: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text())
    estimated_benefit: Mapped[float] = mapped_column(Float, default=0.0)
    tax_year: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(24), default="identified", index=True)
    deadline: Mapped[date | None] = mapped_column(Date())
    method: Mapped[str] = mapped_column(String(120), default="deterministic_tax_rules")
    assumptions: Mapped[list] = mapped_column(default=list)
    supporting_data: Mapped[dict] = mapped_column(default=dict)
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Harvest(BaseModel):
    """A tax-loss harvesting proposal moving through review and approval."""

    __tablename__ = "harvests"
    __table_args__ = (Index("ix_harvests_household_status", "household_id", "status"),)

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    tax_lot_id: Mapped[str | None] = mapped_column(ForeignKey("tax_lots.id", ondelete="SET NULL"))
    replacement_security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id", ondelete="SET NULL"))
    approval_id: Mapped[str | None] = mapped_column(ForeignKey("approvals.id", ondelete="SET NULL"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    cost_basis: Mapped[float] = mapped_column(Float)
    market_value: Mapped[float] = mapped_column(Float)
    unrealized_loss: Mapped[float] = mapped_column(Float)
    holding_period: Mapped[str] = mapped_column(String(16), default="long_term")
    estimated_tax_benefit: Mapped[float] = mapped_column(Float)
    wash_sale_risk: Mapped[str] = mapped_column(String(16), default="clear")
    wash_sale_window_ends: Mapped[date | None] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(24), default="identified", index=True)
    tax_year: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text())
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)


class WashSaleWindow(BaseModel):
    """61-day window (30 before / 30 after) that blocks a loss from counting."""

    __tablename__ = "wash_sale_windows"
    __table_args__ = (Index("ix_wash_account_security", "account_id", "security_id"),)

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    trigger_transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    window_start: Mapped[date] = mapped_column(Date())
    window_end: Mapped[date] = mapped_column(Date())
    reason: Mapped[str] = mapped_column(String(160), default="Purchase within 30 days")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RMD(BaseModel):
    __tablename__ = "rmds"

    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    tax_year: Mapped[int] = mapped_column(Integer, index=True)
    prior_year_end_balance: Mapped[float] = mapped_column(Float)
    life_expectancy_factor: Mapped[float] = mapped_column(Float)
    required_amount: Mapped[float] = mapped_column(Float)
    distributed_amount: Mapped[float] = mapped_column(Float, default=0.0)
    deadline: Mapped[date] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(24), default="pending")
    satisfied_by_qcd: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[str] = mapped_column(String(120), default="uniform_lifetime_table")
