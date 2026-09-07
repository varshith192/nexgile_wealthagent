"""Request payloads. Every write endpoint validates through one of these."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class GoalCreateRequest(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    goal_type: Literal["retirement", "education", "home", "legacy", "life_event", "custom"]
    target_amount: float = Field(gt=0, le=1_000_000_000)
    current_amount: float = Field(default=0.0, ge=0)
    target_date: date
    monthly_contribution: float = Field(default=0.0, ge=0)
    expected_return: float = Field(default=0.06, ge=-0.5, le=0.5)
    inflation_rate: float = Field(default=0.025, ge=0, le=0.25)
    priority: Literal["high", "medium", "low"] = "medium"
    description: str | None = Field(default=None, max_length=2000)
    owner_label: str | None = Field(default=None, max_length=96)
    account_ids: list[str] = Field(default_factory=list)
    household_id: str | None = None

    @field_validator("target_date")
    @classmethod
    def _future(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("target_date must be in the future")
        return v


class GoalUpdateRequest(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    target_amount: float | None = Field(default=None, gt=0)
    current_amount: float | None = Field(default=None, ge=0)
    target_date: date | None = None
    monthly_contribution: float | None = Field(default=None, ge=0)
    expected_return: float | None = Field(default=None, ge=-0.5, le=0.5)
    inflation_rate: float | None = Field(default=None, ge=0, le=0.25)
    priority: Literal["high", "medium", "low"] | None = None
    owner_label: str | None = None


class ScenarioRequest(StrictModel):
    scenario_keys: list[str] | None = None
    persist: bool = True


class RecommendationCreateRequest(StrictModel):
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=3, max_length=4000)
    category: str = Field(default="portfolio", max_length=48)
    severity: Literal["info", "low", "medium", "high", "critical"] = "medium"
    rationale: str = Field(default="", max_length=4000)
    suggested_action: str = Field(default="", max_length=4000)
    impact_amount: float | None = None
    impact_label: str | None = Field(default=None, max_length=120)
    confidence: float = Field(default=0.8, ge=0, le=1)
    supporting_data: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    entity_type: str | None = None
    entity_id: str | None = None
    household_id: str | None = None
    submit: bool = False


class RecommendationFromDraftRequest(StrictModel):
    draft_key: str = Field(min_length=1, max_length=120)
    household_id: str | None = None
    submit: bool = True


class ApprovalDecisionRequest(StrictModel):
    note: str | None = Field(default=None, max_length=2000)


class ApprovalTransitionRequest(StrictModel):
    to_status: Literal["draft", "submitted", "under_review", "approved", "rejected", "cancelled", "completed"]
    note: str | None = Field(default=None, max_length=2000)


class AskRequest(StrictModel):
    question: str = Field(min_length=2, max_length=1000)
    household_id: str | None = None


class ExplainRequest(StrictModel):
    calculation: dict[str, Any]
    audience: Literal["client", "advisor"] = "client"


class DocumentClassifyRequest(StrictModel):
    filename: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class DocumentDecisionRequest(StrictModel):
    decision: Literal["accept", "edit", "reject"]
    category: str | None = None
    document_type: str | None = None


class DocumentShareRequest(StrictModel):
    shared_with_label: str = Field(min_length=2, max_length=160)
    permission: Literal["view", "download"] = "view"
    days_valid: int = Field(default=30, ge=1, le=365)


class MessageSendRequest(StrictModel):
    body: str = Field(min_length=1, max_length=8000)
    attachment_document_id: str | None = None


class ThreadCreateRequest(StrictModel):
    subject: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1, max_length=8000)
    topic: str = Field(default="general", max_length=48)
    household_id: str | None = None


class RebalanceCreateRequest(StrictModel):
    household_id: str | None = None
    name: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=2000)


class HarvestCreateRequest(StrictModel):
    tax_lot_id: str
    household_id: str | None = None


class BeneficiaryChangeRequest(StrictModel):
    beneficiary_id: str
    new_percentage: float = Field(ge=0, le=100)
    note: str | None = Field(default=None, max_length=1000)
    household_id: str | None = None


class ReportGenerateRequest(StrictModel):
    report_type: Literal["portfolio", "performance", "goal", "tax", "household", "quarterly_review"]
    period_start: date
    period_end: date
    benchmark_code: str | None = None
    household_id: str | None = None


class RetirementReadinessRequest(StrictModel):
    current_age: int | None = Field(default=None, ge=18, le=100)
    retirement_age: int | None = Field(default=None, ge=40, le=100)
    current_savings: float | None = Field(default=None, ge=0)
    annual_income: float | None = Field(default=None, ge=0)
    deferral_rate: float | None = Field(default=None, ge=0, le=1)
    employer_match: float | None = Field(default=None, ge=0)
    expected_return: float | None = Field(default=None, ge=-0.2, le=0.3)
    social_security_annual: float | None = Field(default=None, ge=0)
    other_income_annual: float | None = Field(default=None, ge=0)
    healthcare_annual: float | None = Field(default=None, ge=0)
    inflation: float | None = Field(default=None, ge=0, le=0.2)


class TaskUpdateRequest(StrictModel):
    status: Literal["open", "in_progress", "blocked", "complete"]


class SavedViewRequest(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    query: str = Field(min_length=1, max_length=255)
    categories: list[str] = Field(default_factory=list)
