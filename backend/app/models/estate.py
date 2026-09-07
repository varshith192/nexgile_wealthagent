"""Estate, trust, beneficiary and philanthropy entities."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class EstatePlan(BaseModel):
    __tablename__ = "estate_plans"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    plan_name: Mapped[str] = mapped_column(String(160), default="Family Estate Plan")
    document_type: Mapped[str] = mapped_column(String(48), default="will")
    status: Mapped[str] = mapped_column(String(24), default="current")
    executed_on: Mapped[date | None] = mapped_column(Date())
    last_reviewed_on: Mapped[date | None] = mapped_column(Date())
    next_review_due: Mapped[date | None] = mapped_column(Date())
    attorney: Mapped[str | None] = mapped_column(String(120))
    jurisdiction: Mapped[str | None] = mapped_column(String(80))
    executor: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text())
    estimated_estate_value: Mapped[float] = mapped_column(Float, default=0.0)
    projected_estate_tax: Mapped[float] = mapped_column(Float, default=0.0)


class Trust(BaseModel):
    __tablename__ = "trusts"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    estate_plan_id: Mapped[str | None] = mapped_column(ForeignKey("estate_plans.id", ondelete="SET NULL"))
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160))
    trust_type: Mapped[str] = mapped_column(String(48), default="revocable")
    grantor: Mapped[str] = mapped_column(String(120))
    trustee: Mapped[str] = mapped_column(String(120))
    successor_trustee: Mapped[str | None] = mapped_column(String(120))
    funded_amount: Mapped[float] = mapped_column(Float, default=0.0)
    is_funded: Mapped[bool] = mapped_column(Boolean, default=True)
    established_on: Mapped[date | None] = mapped_column(Date())
    situs: Mapped[str | None] = mapped_column(String(80))
    distribution_standard: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="active")


class PowerOfAttorney(BaseModel):
    __tablename__ = "powers_of_attorney"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    poa_type: Mapped[str] = mapped_column(String(48), default="financial")
    principal: Mapped[str] = mapped_column(String(120))
    agent: Mapped[str] = mapped_column(String(120))
    successor_agent: Mapped[str | None] = mapped_column(String(120))
    executed_on: Mapped[date | None] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(24), default="current")
    notes: Mapped[str | None] = mapped_column(Text())


class Beneficiary(BaseModel):
    __tablename__ = "beneficiaries"
    __table_args__ = (Index("ix_beneficiary_account", "account_id", "designation"),)

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    trust_id: Mapped[str | None] = mapped_column(ForeignKey("trusts.id", ondelete="SET NULL"))
    approval_id: Mapped[str | None] = mapped_column(ForeignKey("approvals.id", ondelete="SET NULL"), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    relationship_type: Mapped[str] = mapped_column(String(48), default="spouse")
    designation: Mapped[str] = mapped_column(String(24), default="primary")
    percentage: Mapped[float] = mapped_column(Float, default=100.0)
    birth_date: Mapped[date | None] = mapped_column(Date())
    is_charity: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="completed")
    pending_percentage: Mapped[float | None] = mapped_column(Float)
    last_confirmed_on: Mapped[date | None] = mapped_column(Date())


class DistributionRequest(BaseModel):
    __tablename__ = "distribution_requests"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    trust_id: Mapped[str | None] = mapped_column(ForeignKey("trusts.id", ondelete="SET NULL"))
    approval_id: Mapped[str | None] = mapped_column(ForeignKey("approvals.id", ondelete="SET NULL"), index=True)
    requested_by: Mapped[str] = mapped_column(String(120))
    beneficiary_name: Mapped[str] = mapped_column(String(160))
    amount: Mapped[float] = mapped_column(Float)
    purpose: Mapped[str] = mapped_column(String(200))
    distribution_type: Mapped[str] = mapped_column(String(48), default="discretionary")
    requested_on: Mapped[date] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(24), default="draft")
    tax_withholding: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text())


class Charity(BaseModel):
    __tablename__ = "charities"

    name: Mapped[str] = mapped_column(String(160), unique=True)
    ein_masked: Mapped[str | None] = mapped_column(String(24))
    mission_area: Mapped[str] = mapped_column(String(80), default="Education")
    location: Mapped[str | None] = mapped_column(String(120))
    rating: Mapped[float | None] = mapped_column(Float)
    is_qualified: Mapped[bool] = mapped_column(Boolean, default=True)


class DAF(BaseModel):
    """Donor-advised fund, private foundation or charitable trust vehicle."""

    __tablename__ = "dafs"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160))
    vehicle_type: Mapped[str] = mapped_column(String(48), default="daf")
    sponsor_organisation: Mapped[str | None] = mapped_column(String(160))
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    contributed_ytd: Mapped[float] = mapped_column(Float, default=0.0)
    granted_ytd: Mapped[float] = mapped_column(Float, default=0.0)
    annual_grant_target: Mapped[float] = mapped_column(Float, default=0.0)
    payout_requirement: Mapped[float | None] = mapped_column(Float)
    established_on: Mapped[date | None] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(24), default="active")

    grants: Mapped[list["Grant"]] = relationship(back_populates="daf", cascade="all, delete-orphan")


class Grant(BaseModel):
    __tablename__ = "grants"
    __table_args__ = (Index("ix_grants_daf_date", "daf_id", "granted_on"),)

    daf_id: Mapped[str] = mapped_column(ForeignKey("dafs.id", ondelete="CASCADE"), index=True)
    charity_id: Mapped[str] = mapped_column(ForeignKey("charities.id", ondelete="CASCADE"))
    amount: Mapped[float] = mapped_column(Float)
    granted_on: Mapped[date] = mapped_column(Date())
    purpose: Mapped[str | None] = mapped_column(String(200))
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="completed")
    impact_note: Mapped[str | None] = mapped_column(Text())

    daf: Mapped[DAF] = relationship(back_populates="grants")
    charity: Mapped[Charity] = relationship()


class Gift(BaseModel):
    """Lifetime gifting to individuals or charities, incl. QCD and appreciated stock."""

    __tablename__ = "gifts"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    charity_id: Mapped[str | None] = mapped_column(ForeignKey("charities.id", ondelete="SET NULL"))
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id", ondelete="SET NULL"))
    recipient: Mapped[str] = mapped_column(String(160))
    gift_type: Mapped[str] = mapped_column(String(48), default="cash")
    amount: Mapped[float] = mapped_column(Float)
    cost_basis: Mapped[float | None] = mapped_column(Float)
    gifted_on: Mapped[date] = mapped_column(Date())
    tax_year: Mapped[int] = mapped_column(Integer, index=True)
    uses_annual_exclusion: Mapped[bool] = mapped_column(Boolean, default=True)
    is_qcd: Mapped[bool] = mapped_column(Boolean, default=False)
    deduction_amount: Mapped[float] = mapped_column(Float, default=0.0)
    capital_gain_avoided: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text())


class GivingPlan(BaseModel):
    __tablename__ = "giving_plans"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    tax_year: Mapped[int] = mapped_column(Integer)
    target_amount: Mapped[float] = mapped_column(Float)
    committed_amount: Mapped[float] = mapped_column(Float, default=0.0)
    mission_focus: Mapped[str] = mapped_column(String(120), default="Education")
    strategy: Mapped[str] = mapped_column(String(120), default="Appreciated securities via DAF")
    status: Mapped[str] = mapped_column(String(24), default="active")
    review_date: Mapped[date | None] = mapped_column(Date())
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
