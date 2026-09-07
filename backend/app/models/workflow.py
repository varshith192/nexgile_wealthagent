"""Cross-cutting workflow tables: approvals, rebalancing, alerts, reports, audit."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class Approval(BaseModel):
    """One reusable approval record for every reviewable action (§37)."""

    __tablename__ = "approvals"
    __table_args__ = (
        Index("ix_approvals_status_type", "status", "entity_type"),
        Index("ix_approvals_household", "household_id"),
    )

    household_id: Mapped[str | None] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    requested_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    assigned_to_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    decided_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    required_role: Mapped[str] = mapped_column(String(48), default="advisor")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date | None] = mapped_column(Date())
    decision_note: Mapped[str | None] = mapped_column(Text())
    payload: Mapped[dict] = mapped_column(default=dict)
    estimated_impact: Mapped[float | None] = mapped_column(Float)

    events: Mapped[list["ApprovalEvent"]] = relationship(
        back_populates="approval", cascade="all, delete-orphan", order_by="ApprovalEvent.created_at"
    )


class ApprovalEvent(BaseModel):
    __tablename__ = "approval_events"

    approval_id: Mapped[str] = mapped_column(ForeignKey("approvals.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_name: Mapped[str] = mapped_column(String(160), default="System")
    note: Mapped[str | None] = mapped_column(Text())

    approval: Mapped[Approval] = relationship(back_populates="events")


class Rebalance(BaseModel):
    __tablename__ = "rebalances"
    __table_args__ = (Index("ix_rebalance_household_status", "household_id", "status"),)

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"))
    approval_id: Mapped[str | None] = mapped_column(ForeignKey("approvals.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    strategy_note: Mapped[str | None] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    max_drift: Mapped[float] = mapped_column(Float, default=0.0)
    turnover_amount: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_tax_cost: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_trading_cost: Mapped[float] = mapped_column(Float, default=0.0)
    cash_impact: Mapped[float] = mapped_column(Float, default=0.0)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)

    trades: Mapped[list["RebalanceTrade"]] = relationship(back_populates="rebalance", cascade="all, delete-orphan")


class RebalanceTrade(BaseModel):
    __tablename__ = "rebalance_trades"

    rebalance_id: Mapped[str] = mapped_column(ForeignKey("rebalances.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[float] = mapped_column(Float)
    estimated_price: Mapped[float] = mapped_column(Float)
    estimated_amount: Mapped[float] = mapped_column(Float)
    realized_gain: Mapped[float] = mapped_column(Float, default=0.0)
    tax_impact: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="proposed")

    rebalance: Mapped[Rebalance] = relationship(back_populates="trades")


class Report(BaseModel):
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_household_type", "household_id", "report_type"),)

    household_id: Mapped[str | None] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    report_type: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(200))
    period_start: Mapped[date] = mapped_column(Date())
    period_end: Mapped[date] = mapped_column(Date())
    benchmark_code: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="ready")
    generated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sections: Mapped[list] = mapped_column(default=list)
    payload: Mapped[dict] = mapped_column(default=dict)
    assumptions: Mapped[list] = mapped_column(default=list)


class Alert(BaseModel):
    """Notification centre record (§28)."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_user_read", "user_id", "read_at"),
        Index("ix_alerts_household_category", "household_id", "category"),
    )

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    household_id: Mapped[str | None] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text())
    entity_type: Mapped[str | None] = mapped_column(String(48))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    action_url: Mapped[str | None] = mapped_column(String(200))
    due_date: Mapped[date | None] = mapped_column(Date())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(BaseModel):
    """Immutable activity trail (§38). Append-only by convention."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_actor_time", "actor_id", "created_at"),
        Index("ix_audit_household_time", "household_id", "created_at"),
    )

    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_name: Mapped[str] = mapped_column(String(160), default="System")
    actor_role: Mapped[str | None] = mapped_column(String(48))
    household_id: Mapped[str | None] = mapped_column(ForeignKey("households.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    entity_label: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), default="success")
    summary: Mapped[str | None] = mapped_column(Text())
    before_state: Mapped[dict | None] = mapped_column()
    after_state: Mapped[dict | None] = mapped_column()
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class SavedView(BaseModel):
    """Saved searches / views for global search (§36)."""

    __tablename__ = "saved_views"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    query: Mapped[str] = mapped_column(String(255))
    categories: Mapped[list] = mapped_column(default=list)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0)


class SearchHistory(BaseModel):
    __tablename__ = "search_history"
    __table_args__ = (Index("ix_search_user_time", "user_id", "created_at"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    query: Mapped[str] = mapped_column(String(255))
    result_count: Mapped[int] = mapped_column(Integer, default=0)
