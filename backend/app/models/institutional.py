"""Retirement plan sponsor, participant, fiduciary and compliance entities."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class Sponsor(BaseModel):
    __tablename__ = "sponsors"

    name: Mapped[str] = mapped_column(String(160), unique=True)
    industry: Mapped[str] = mapped_column(String(80), default="Technology")
    employee_count: Mapped[int] = mapped_column(Integer, default=0)
    pan_masked: Mapped[str | None] = mapped_column(String(24))
    location: Mapped[str | None] = mapped_column(String(120))
    relationship_since: Mapped[date | None] = mapped_column(Date())
    primary_contact_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    plans: Mapped[list["Plan"]] = relationship(back_populates="sponsor", cascade="all, delete-orphan")


class Plan(BaseModel):
    __tablename__ = "plans"

    sponsor_id: Mapped[str] = mapped_column(ForeignKey("sponsors.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    plan_number: Mapped[str] = mapped_column(String(16), default="001")
    plan_type: Mapped[str] = mapped_column(String(32), default="epf")
    plan_year_end: Mapped[date] = mapped_column(Date())
    total_assets: Mapped[float] = mapped_column(Float, default=0.0)
    eligible_employees: Mapped[int] = mapped_column(Integer, default=0)
    participating_employees: Mapped[int] = mapped_column(Integer, default=0)
    average_deferral_rate: Mapped[float] = mapped_column(Float, default=0.0)
    employer_match_formula: Mapped[str] = mapped_column(String(160), default="Statutory 12% of basic pay")
    # Employee contributions are fully vested from day one under Indian law; only
    # EPS (10 years) and gratuity (5 years) carry a qualifying period.
    vesting_schedule: Mapped[str] = mapped_column(String(96), default="EPF fully vested; EPS at 10 years; gratuity at 5 years")
    auto_enrollment: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_enrollment_rate: Mapped[float] = mapped_column(Float, default=0.06)
    auto_escalation: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_escalation_cap: Mapped[float] = mapped_column(Float, default=0.15)
    loans_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    hardship_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    recordkeeper: Mapped[str] = mapped_column(String(120), default="EPFO / Registered Recordkeeper")
    advisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    plan_health_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(24), default="active")

    sponsor: Mapped[Sponsor] = relationship(back_populates="plans")


class Participant(BaseModel):
    __tablename__ = "participants"
    __table_args__ = (Index("ix_participants_plan_status", "plan_id", "status"),)

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    employee_id_masked: Mapped[str] = mapped_column(String(24))
    birth_date: Mapped[date] = mapped_column(Date())
    hire_date: Mapped[date] = mapped_column(Date())
    annual_salary: Mapped[float] = mapped_column(Float)
    deferral_rate: Mapped[float] = mapped_column(Float, default=0.06)
    vpf_contribution_rate: Mapped[float] = mapped_column(Float, default=0.0)
    account_balance: Mapped[float] = mapped_column(Float, default=0.0)
    vpf_balance: Mapped[float] = mapped_column(Float, default=0.0)
    employer_balance: Mapped[float] = mapped_column(Float, default=0.0)
    vested_percentage: Mapped[float] = mapped_column(Float, default=1.0)
    is_hce: Mapped[bool] = mapped_column(Boolean, default=False)
    is_auto_enrolled: Mapped[bool] = mapped_column(Boolean, default=True)
    has_beneficiary: Mapped[bool] = mapped_column(Boolean, default=True)
    retirement_age: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(24), default="active")
    engagement_score: Mapped[float] = mapped_column(Float, default=0.5)

    plan: Mapped[Plan] = relationship()


class Contribution(BaseModel):
    __tablename__ = "contributions"
    __table_args__ = (Index("ix_contrib_participant_period", "participant_id", "period_end"),)

    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"))
    period_start: Mapped[date] = mapped_column(Date())
    period_end: Mapped[date] = mapped_column(Date())
    employee_pretax: Mapped[float] = mapped_column(Float, default=0.0)
    employee_vpf: Mapped[float] = mapped_column(Float, default=0.0)
    employee_catchup: Mapped[float] = mapped_column(Float, default=0.0)
    employer_match: Mapped[float] = mapped_column(Float, default=0.0)
    employer_profit_sharing: Mapped[float] = mapped_column(Float, default=0.0)
    tax_year: Mapped[int] = mapped_column(Integer, index=True)


class InvestmentOption(BaseModel):
    """A fund on the plan lineup, monitored against the IPS."""

    __tablename__ = "investment_options"

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160))
    ticker: Mapped[str | None] = mapped_column(String(16))
    asset_category: Mapped[str] = mapped_column(String(64), default="Large Cap Blend")
    expense_ratio: Mapped[float] = mapped_column(Float, default=0.005)
    category_median_expense: Mapped[float] = mapped_column(Float, default=0.006)
    plan_assets: Mapped[float] = mapped_column(Float, default=0.0)
    participants_invested: Mapped[int] = mapped_column(Integer, default=0)
    three_year_return: Mapped[float] = mapped_column(Float, default=0.0)
    five_year_return: Mapped[float] = mapped_column(Float, default=0.0)
    benchmark_three_year: Mapped[float] = mapped_column(Float, default=0.0)
    peer_rank_percentile: Mapped[int] = mapped_column(Integer, default=50)
    ips_status: Mapped[str] = mapped_column(String(24), default="pass")
    watch_reason: Mapped[str | None] = mapped_column(Text())
    is_default_scheme: Mapped[bool] = mapped_column(Boolean, default=False)
    revenue_share_bps: Mapped[int] = mapped_column(Integer, default=0)


class Fee(BaseModel):
    __tablename__ = "fees"

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    vendor: Mapped[str] = mapped_column(String(120))
    fee_type: Mapped[str] = mapped_column(String(48), default="recordkeeping")
    payer: Mapped[str] = mapped_column(String(32), default="participant")
    annual_amount: Mapped[float] = mapped_column(Float, default=0.0)
    per_participant_amount: Mapped[float] = mapped_column(Float, default=0.0)
    basis_points: Mapped[float] = mapped_column(Float, default=0.0)
    benchmark_basis_points: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_sharing: Mapped[float] = mapped_column(Float, default=0.0)
    contract_end: Mapped[date | None] = mapped_column(Date())
    sla_score: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text())


class ComplianceTest(BaseModel):
    __tablename__ = "compliance_tests"
    __table_args__ = (Index("ix_comptest_plan_year", "plan_id", "tax_year"),)

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    test_type: Mapped[str] = mapped_column(String(48), index=True)
    tax_year: Mapped[int] = mapped_column(Integer)
    hce_value: Mapped[float | None] = mapped_column(Float)
    nhce_value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(24), default="pass")
    status: Mapped[str] = mapped_column(String(24), default="complete")
    due_date: Mapped[date | None] = mapped_column(Date())
    completed_on: Mapped[date | None] = mapped_column(Date())
    corrective_action: Mapped[str | None] = mapped_column(Text())
    evidence_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    method: Mapped[str] = mapped_column(String(120), default="current_year_testing")


class Filing(BaseModel):
    __tablename__ = "filings"

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    filing_type: Mapped[str] = mapped_column(String(48), default="form_5500")
    tax_year: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date())
    extended_due_date: Mapped[date | None] = mapped_column(Date())
    filed_on: Mapped[date | None] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(24), default="pending")
    preparer: Mapped[str | None] = mapped_column(String(120))
    auditor: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text())


class FiduciaryReview(BaseModel):
    """Committee meeting evidence: agenda, minutes, action log."""

    __tablename__ = "fiduciary_reviews"

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    review_period: Mapped[str] = mapped_column(String(32), default="Q1 2026")
    held_on: Mapped[date] = mapped_column(Date())
    attendees: Mapped[list] = mapped_column(default=list)
    agenda: Mapped[list] = mapped_column(default=list)
    minutes: Mapped[str | None] = mapped_column(Text())
    decisions: Mapped[list] = mapped_column(default=list)
    funds_on_watch: Mapped[int] = mapped_column(Integer, default=0)
    ips_compliant: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="complete")
    evidence_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))


class ParticipantLoan(BaseModel):
    __tablename__ = "participant_loans"

    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    original_amount: Mapped[float] = mapped_column(Float)
    outstanding_balance: Mapped[float] = mapped_column(Float)
    interest_rate: Mapped[float] = mapped_column(Float, default=0.0825)
    term_months: Mapped[int] = mapped_column(Integer, default=60)
    payment_amount: Mapped[float] = mapped_column(Float, default=0.0)
    issued_on: Mapped[date] = mapped_column(Date())
    matures_on: Mapped[date] = mapped_column(Date())
    loan_type: Mapped[str] = mapped_column(String(32), default="general")
    status: Mapped[str] = mapped_column(String(24), default="current")


class EducationContent(BaseModel):
    __tablename__ = "education_content"

    title: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(32), default="guide")
    learning_path: Mapped[str] = mapped_column(String(96), default="Retirement Foundations")
    level: Mapped[str] = mapped_column(String(24), default="beginner")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=10)
    summary: Mapped[str] = mapped_column(Text())
    body: Mapped[str | None] = mapped_column(Text())
    tags: Mapped[list] = mapped_column(default=list)
    published_on: Mapped[date | None] = mapped_column(Date())


class EducationProgress(BaseModel):
    __tablename__ = "education_progress"

    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("education_content.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(24), default="not_started")
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float | None] = mapped_column(Float)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content: Mapped[EducationContent] = relationship()
