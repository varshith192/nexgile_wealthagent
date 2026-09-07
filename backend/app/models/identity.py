"""Identity, household and advisory-relationship tables."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class RoleRecord(BaseModel):
    __tablename__ = "roles"

    key: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(96))
    description: Mapped[str | None] = mapped_column(Text())
    home_route: Mapped[str] = mapped_column(String(96), default="/dashboard")

    permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan")


class PermissionRecord(BaseModel):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text())


class RolePermission(BaseModel):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), index=True)

    role: Mapped[RoleRecord] = relationship(back_populates="permissions")
    permission: Mapped[PermissionRecord] = relationship()


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_role_active", "role", "is_active"),)

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    avatar_initials: Mapped[str | None] = mapped_column(String(4))
    # Local auth only. When AUTH_PROVIDER=supabase this stays null and identity
    # is asserted by the Supabase access token.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    supabase_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    demo_label: Mapped[str | None] = mapped_column(String(64))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")

    client: Mapped["Client | None"] = relationship(back_populates="user", uselist=False)


class Household(BaseModel):
    __tablename__ = "households"

    name: Mapped[str] = mapped_column(String(160), index=True)
    segment: Mapped[str] = mapped_column(String(48), default="private_client")
    primary_advisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    risk_profile: Mapped[str] = mapped_column(String(32), default="moderate")
    since: Mapped[date | None] = mapped_column(Date())
    city: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text())

    members: Mapped[list["HouseholdMember"]] = relationship(back_populates="household", cascade="all, delete-orphan")
    clients: Mapped[list["Client"]] = relationship(back_populates="household")
    primary_advisor: Mapped[User | None] = relationship(foreign_keys=[primary_advisor_id])


class HouseholdMember(BaseModel):
    __tablename__ = "household_members"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    relationship_type: Mapped[str] = mapped_column(String(48), default="spouse")
    birth_date: Mapped[date | None] = mapped_column(Date())
    is_dependent: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[str | None] = mapped_column(String(255))

    household: Mapped[Household] = relationship(back_populates="members")


class Client(BaseModel):
    __tablename__ = "clients"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, unique=True)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date())
    retirement_age: Mapped[int] = mapped_column(default=65)
    filing_status: Mapped[str] = mapped_column(String(32), default="married_joint")
    marginal_tax_rate: Mapped[float] = mapped_column(Float, default=0.35)
    ltcg_tax_rate: Mapped[float] = mapped_column(Float, default=0.20)
    state_tax_rate: Mapped[float] = mapped_column(Float, default=0.05)
    annual_income: Mapped[float] = mapped_column(Float, default=0.0)
    annual_savings: Mapped[float] = mapped_column(Float, default=0.0)
    risk_tolerance: Mapped[str] = mapped_column(String(32), default="moderate")
    status: Mapped[str] = mapped_column(String(32), default="active")
    segment: Mapped[str] = mapped_column(String(48), default="private_client")
    onboarded_on: Mapped[date | None] = mapped_column(Date())

    user: Mapped[User | None] = relationship(back_populates="client")
    household: Mapped[Household] = relationship(back_populates="clients")


class AdvisorTeam(BaseModel):
    __tablename__ = "advisor_teams"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    region: Mapped[str | None] = mapped_column(String(80))
    lead_advisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class AdvisorAssignment(BaseModel):
    __tablename__ = "advisor_assignments"
    __table_args__ = (
        UniqueConstraint("advisor_id", "household_id", "role_on_account", name="uq_advisor_household_role"),
        Index("ix_assignment_household", "household_id"),
    )

    advisor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    team_id: Mapped[str | None] = mapped_column(ForeignKey("advisor_teams.id", ondelete="SET NULL"))
    role_on_account: Mapped[str] = mapped_column(String(48), default="lead_advisor")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)

    advisor: Mapped[User] = relationship()
    household: Mapped[Household] = relationship()
