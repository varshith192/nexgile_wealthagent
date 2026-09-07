"""The AI contract.

Everything the product asks of an intelligence layer is declared here as a
narrow, typed interface. `MockAIService` implements it today with deterministic
business rules over the real dataset; a hosted model implements the same
interface tomorrow. Nothing outside this package knows which one is running.

Two rules hold for every implementation:

1. The provider never computes a financial figure. It receives verified numbers
   from `app.calculations` and explains them.
2. Every response carries provenance: which provider produced it, from which
   data, as of when, and with what confidence.
"""

from __future__ import annotations

import abc
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

InsightCategory = Literal[
    "portfolio",
    "goal",
    "tax",
    "estate",
    "philanthropy",
    "retirement",
    "cash",
    "document",
    "compliance",
    "plan",
]

Severity = Literal["info", "low", "medium", "high", "critical"]


class SupportingFact(BaseModel):
    """One verified number behind an insight, with its own provenance."""

    label: str
    value: str
    raw_value: float | None = None
    source: str = "nexgile_calculation_engine"
    as_of: date | None = None


class Insight(BaseModel):
    """What changed, why it matters, and what to consider next."""

    key: str
    title: str
    category: InsightCategory
    severity: Severity = "medium"
    summary: str
    impact: str
    suggested_next_step: str
    supporting_facts: list[SupportingFact] = Field(default_factory=list)
    calculation_method: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    confidence: float = 0.85
    as_of: date | None = None
    source: str = "deterministic_rules"
    entity_type: str | None = None
    entity_id: str | None = None
    action_url: str | None = None


class RecommendationDraft(BaseModel):
    """A proposed action. Always routed through human review before anything happens."""

    key: str
    title: str
    category: str
    severity: Severity = "medium"
    summary: str
    rationale: str
    suggested_action: str
    impact_amount: float | None = None
    impact_label: str | None = None
    confidence: float = 0.8
    supporting_data: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    requires_approval: bool = True
    entity_type: str | None = None
    entity_id: str | None = None


class NextAction(BaseModel):
    """Something the user can actually do from the WealthAgent surface."""

    key: str
    label: str
    description: str
    route: str
    category: str
    requires_approval: bool = False
    severity: Severity = "info"


class DocumentClassification(BaseModel):
    """Suggested filing for an uploaded document, with reasons, never auto-applied."""

    suggested_category: str
    suggested_document_type: str
    detected_year: int | None = None
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    suggested_tags: list[str] = Field(default_factory=list)
    source: str = "mock_rules"


class Explanation(BaseModel):
    """Plain-language narration of a calculation the engine already performed."""

    headline: str
    body: str
    method: str
    as_of: date | None = None
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    source: str


class AgentAnswer(BaseModel):
    """Reply to a conversational question, grounded in supplied facts only."""

    answer: str
    intent: str
    grounded_facts: list[SupportingFact] = Field(default_factory=list)
    related_routes: list[NextAction] = Field(default_factory=list)
    followups: list[str] = Field(default_factory=list)
    confidence: float = 0.7
    source: str
    disclaimer: str = (
        "WealthAgent explains figures produced by the platform's calculation engine. "
        "It is informational and is not investment, tax or legal advice."
    )


class AIContext(BaseModel):
    """The verified snapshot handed to the provider. Read-only by contract."""

    household_id: str | None = None
    household_name: str | None = None
    as_of: date
    currency: str = "USD"
    net_worth: dict[str, Any] = Field(default_factory=dict)
    portfolio: dict[str, Any] = Field(default_factory=dict)
    allocation: dict[str, Any] = Field(default_factory=dict)
    drift: dict[str, Any] = Field(default_factory=dict)
    concentration: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    performance: dict[str, Any] = Field(default_factory=dict)
    income: dict[str, Any] = Field(default_factory=dict)
    goals: dict[str, Any] = Field(default_factory=dict)
    tax: dict[str, Any] = Field(default_factory=dict)
    estate: dict[str, Any] = Field(default_factory=dict)
    philanthropy: dict[str, Any] = Field(default_factory=dict)
    documents: dict[str, Any] = Field(default_factory=dict)
    cash: dict[str, Any] = Field(default_factory=dict)
    meetings: list[dict[str, Any]] = Field(default_factory=list)
    data_freshness: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime | None = None


class AIProviderInfo(BaseModel):
    name: str
    mode: Literal["mock", "live"]
    model: str | None = None
    description: str
    capabilities: list[str] = Field(default_factory=list)
    requires_api_key: bool = False
    is_configured: bool = True


class AIProvider(abc.ABC):
    """Implement these five methods to plug a real model into the product."""

    name: str = "base"
    mode: Literal["mock", "live"] = "mock"

    @abc.abstractmethod
    def info(self) -> AIProviderInfo: ...

    @abc.abstractmethod
    def generate_insights(self, context: AIContext) -> list[Insight]: ...

    @abc.abstractmethod
    def generate_recommendations(self, context: AIContext) -> list[RecommendationDraft]: ...

    @abc.abstractmethod
    def suggest_actions(self, context: AIContext) -> list[NextAction]: ...

    @abc.abstractmethod
    def classify_document(self, filename: str, metadata: dict[str, Any] | None = None) -> DocumentClassification: ...

    @abc.abstractmethod
    def explain(self, calculation: dict[str, Any], audience: str = "client") -> Explanation: ...

    @abc.abstractmethod
    def answer(self, question: str, context: AIContext) -> AgentAnswer: ...
