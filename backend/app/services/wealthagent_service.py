"""WealthAgent (§19): insights, recommendations, actions and grounded Q&A.

The flow the product is built around:

    financial data -> calculations -> analysis -> insight -> recommendation
    -> human review -> approval -> action -> audit event

This service owns the first half and hands the second half to the approval
engine. The AI layer only ever sees numbers the calculation engine produced.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIContext
from app.ai.service import AIService, get_ai_service
from app.audit.service import AuditAction, AuditService
from app.core.constants import ApprovalStatus, EntityType, Role
from app.core.errors import NotFoundError
from app.models.collab import Meeting
from app.models.identity import Household, User
from app.models.planning import Recommendation
from app.services.document_service import DocumentService
from app.services.estate_service import EstateService, PhilanthropyService
from app.services.goal_service import GoalService
from app.services.portfolio_service import PortfolioService
from app.services.tax_service import TaxService
from app.workflows.approval_engine import ApprovalEngine


class WealthAgentService:
    def __init__(self, db: Session, ai: AIService | None = None, audit: AuditService | None = None) -> None:
        self.db = db
        self.ai = ai or get_ai_service()
        self.audit = audit or AuditService(db)
        self.portfolio = PortfolioService(db)
        self.goals = GoalService(db, self.audit)
        self.tax = TaxService(db, self.audit)
        self.estate = EstateService(db, self.audit)
        self.philanthropy = PhilanthropyService(db, self.audit)
        self.documents = DocumentService(db, self.audit, self.ai)
        self.approvals = ApprovalEngine(db, self.audit)

    # -- context ------------------------------------------------------
    def build_context(self, household_id: str) -> AIContext:
        """Assemble the verified snapshot handed to the AI layer."""
        household = self.db.get(Household, household_id)
        if not household:
            raise NotFoundError("Household not found.")

        as_of = self.portfolio.as_of(household_id)
        valuation = self.portfolio.valuation(household_id)["result"]
        tax_overview = self.tax.overview(household_id, as_of)
        estate_overview = self.estate.overview(household_id, as_of)
        giving = self.philanthropy.overview(household_id, as_of)
        documents = self.documents.list(household_id, page_size=1)

        upcoming = self.db.execute(
            select(Meeting)
            .where(Meeting.household_id == household_id, Meeting.status == "scheduled")
            .order_by(Meeting.starts_at)
            .limit(3)
        ).scalars().all()

        return AIContext(
            household_id=household_id,
            household_name=household.name,
            as_of=as_of,
            currency="USD",
            net_worth=self.portfolio.net_worth(household_id)["result"],
            portfolio=valuation,
            allocation=self.portfolio.allocation(household_id)["result"],
            drift=self.portfolio.drift(household_id)["result"],
            concentration=self.portfolio.concentration(household_id)["result"],
            risk=self.portfolio.risk(household_id)["result"],
            performance=self.portfolio.performance(household_id)["periods"],
            income=self.portfolio.income(household_id)["result"],
            goals=self.goals.summary(household_id, as_of)["result"],
            tax={
                "harvest": tax_overview["harvest"]["result"],
                "realized": tax_overview["realized_gains"]["result"],
                "rmd": tax_overview["rmd"],
                "asset_location": tax_overview["asset_location"]["result"],
                "estimate": tax_overview["tax_estimate"]["result"],
            },
            estate={
                **estate_overview["projection"]["result"],
                "last_reviewed_on": estate_overview["last_reviewed_on"],
                "beneficiary_gaps": estate_overview["beneficiary_gaps"],
            },
            philanthropy={
                "daf_balance": giving["summary"]["total_balance"],
                "granted_ytd": giving["summary"]["granted_ytd"],
                "annual_grant_target": giving["summary"]["annual_grant_target"],
            },
            documents={
                "total": documents["summary"]["total"],
                "pending_review": documents["summary"]["pending_review"],
                "expiring_soon": self.documents.expiring_soon(household_id),
            },
            cash={"balance": valuation.get("cash", 0.0)},
            meetings=[
                {"id": m.id, "title": m.title, "starts_at": m.starts_at.isoformat(), "type": m.meeting_type}
                for m in upcoming
            ],
            data_freshness=self.portfolio.data_freshness(household_id),
            generated_at=datetime.now(timezone.utc),
        )

    # -- the three WealthAgent surfaces -------------------------------
    def insights(self, household_id: str) -> list[dict[str, Any]]:
        context = self.build_context(household_id)
        return [i.model_dump(mode="json") for i in self.ai.insights(context)]

    def recommendations_preview(self, household_id: str) -> list[dict[str, Any]]:
        context = self.build_context(household_id)
        return [r.model_dump(mode="json") for r in self.ai.recommendations(context)]

    def actions(self, household_id: str) -> list[dict[str, Any]]:
        context = self.build_context(household_id)
        return [a.model_dump(mode="json") for a in self.ai.actions(context)]

    def workspace(self, household_id: str) -> dict[str, Any]:
        """Everything the WealthAgent page renders, from one context build."""
        context = self.build_context(household_id)
        insights = self.ai.insights(context)
        drafts = self.ai.recommendations(context)
        actions = self.ai.actions(context)
        stored = self.list_recommendations(household_id)

        return {
            "as_of": context.as_of.isoformat(),
            "household": {"id": household_id, "name": context.household_name},
            "provider": self.ai.info.model_dump(),
            "insights": [i.model_dump(mode="json") for i in insights],
            "recommendation_drafts": [r.model_dump(mode="json") for r in drafts],
            "actions": [a.model_dump(mode="json") for a in actions],
            "recommendations": stored,
            "summary": {
                "insight_count": len(insights),
                "high_severity": sum(1 for i in insights if i.severity in {"high", "critical"}),
                "draft_count": len(drafts),
                "open_recommendations": sum(
                    1 for r in stored if r["status"] in {"draft", "submitted", "under_review"}
                ),
            },
            "data_freshness": context.data_freshness,
            "disclaimer": (
                "WealthAgent surfaces figures produced by the platform's calculation engine and the business rules "
                "applied to them. It is informational and is not investment, tax or legal advice. Every action "
                "requires human review and approval."
            ),
        }

    def ask(self, household_id: str, question: str, actor: User | None = None) -> dict[str, Any]:
        context = self.build_context(household_id)
        answer = self.ai.answer(question, context)
        return answer.model_dump(mode="json")

    def explain(self, calculation: dict[str, Any], audience: str = "client") -> dict[str, Any]:
        return self.ai.explain(calculation, audience).model_dump(mode="json")

    # -- recommendation persistence + workflow ------------------------
    def list_recommendations(
        self, household_id: str, *, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        stmt = select(Recommendation).where(Recommendation.household_id == household_id)
        if status:
            stmt = stmt.where(Recommendation.status == status)
        rows = self.db.execute(stmt.order_by(Recommendation.created_at.desc()).limit(limit)).scalars().all()
        return [self.serialise_recommendation(r) for r in rows]

    def serialise_recommendation(self, rec: Recommendation) -> dict[str, Any]:
        return {
            "id": rec.id,
            "household_id": rec.household_id,
            "title": rec.title,
            "category": rec.category,
            "severity": rec.severity,
            "summary": rec.summary,
            "rationale": rec.rationale,
            "suggested_action": rec.suggested_action,
            "impact_amount": rec.impact_amount,
            "impact_label": rec.impact_label,
            "confidence": rec.confidence,
            "status": rec.status,
            "source": rec.source,
            "generator": rec.generator,
            "supporting_data": rec.supporting_data,
            "assumptions": rec.assumptions,
            "limitations": rec.limitations,
            "entity_type": rec.entity_type,
            "entity_id": rec.entity_id,
            "approval_id": rec.approval_id,
            "as_of": rec.as_of.isoformat() if rec.as_of else None,
            "created_at": rec.created_at.isoformat(),
        }

    def get_recommendation(self, recommendation_id: str) -> Recommendation:
        rec = self.db.get(Recommendation, recommendation_id)
        if not rec:
            raise NotFoundError("Recommendation not found.")
        return rec

    def create_recommendation(
        self, household_id: str, payload: dict[str, Any], actor: User, *, submit: bool = False
    ) -> dict[str, Any]:
        """Promote a draft into a tracked recommendation with an approval record."""
        as_of = self.portfolio.as_of(household_id)
        rec = Recommendation(
            household_id=household_id,
            title=payload["title"],
            category=payload.get("category", "portfolio"),
            severity=payload.get("severity", "medium"),
            summary=payload["summary"],
            rationale=payload.get("rationale", ""),
            suggested_action=payload.get("suggested_action", ""),
            impact_amount=payload.get("impact_amount"),
            impact_label=payload.get("impact_label"),
            confidence=float(payload.get("confidence") or 0.8),
            status=ApprovalStatus.DRAFT,
            source=payload.get("source", "wealthagent_rules"),
            generator=self.ai.info.name,
            supporting_data=payload.get("supporting_data") or {},
            assumptions=payload.get("assumptions") or [],
            limitations=payload.get("limitations") or [],
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
            as_of=datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc),
            created_by_id=actor.id,
        )
        self.db.add(rec)
        self.db.flush()

        approval = self.approvals.create(
            entity_type=EntityType.RECOMMENDATION,
            entity_id=rec.id,
            title=rec.title,
            summary=rec.summary,
            household_id=household_id,
            requested_by=actor,
            required_role=Role.ADVISOR,
            priority="high" if rec.severity in {"high", "critical"} else "medium",
            payload={"recommendation_id": rec.id, "category": rec.category},
            estimated_impact=rec.impact_amount,
            status=ApprovalStatus.DRAFT,
            commit=False,
        )
        rec.approval_id = approval.id

        self.audit.record(
            action=AuditAction.RECOMMENDATION_CREATED,
            entity_type=EntityType.RECOMMENDATION,
            entity_id=rec.id,
            entity_label=rec.title,
            actor=actor,
            household_id=household_id,
            summary=f"Recommendation created: {rec.title}",
            after={"category": rec.category, "severity": rec.severity, "impact": rec.impact_amount},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(rec)

        if submit:
            self.approvals.submit(approval.id, actor, note="Submitted for advisor review")
            self.db.refresh(rec)

        return self.serialise_recommendation(rec)

    def create_from_draft(self, household_id: str, draft_key: str, actor: User, submit: bool = True) -> dict[str, Any]:
        """Turn one of the agent's drafts into a tracked recommendation."""
        context = self.build_context(household_id)
        drafts = {d.key: d for d in self.ai.recommendations(context)}
        draft = drafts.get(draft_key)
        if not draft:
            raise NotFoundError(f"No current recommendation draft with key {draft_key!r}.")

        return self.create_recommendation(
            household_id,
            {
                "title": draft.title,
                "category": draft.category,
                "severity": draft.severity,
                "summary": draft.summary,
                "rationale": draft.rationale,
                "suggested_action": draft.suggested_action,
                "impact_amount": draft.impact_amount,
                "impact_label": draft.impact_label,
                "confidence": draft.confidence,
                "supporting_data": draft.supporting_data,
                "assumptions": draft.assumptions,
                "limitations": draft.limitations,
                "entity_type": draft.entity_type,
                "entity_id": draft.entity_id,
                "source": "wealthagent_rules",
            },
            actor,
            submit=submit,
        )
