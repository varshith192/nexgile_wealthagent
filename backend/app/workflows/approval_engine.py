"""The reusable approval engine (§37).

Recommendations, rebalances, harvests, distributions, beneficiary changes, plan
actions and compliance attestations all move through this one state machine.
Adding a new reviewable action means adding an entity type, not another workflow.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, AuditService
from app.core.constants import APPROVAL_TRANSITIONS, ApprovalStatus, EntityType, Permission, Role
from app.core.errors import ForbiddenError, NotFoundError, UnprocessableWorkflowError
from app.models.identity import User
from app.models.workflow import Approval, ApprovalEvent
from app.services.auth_service import has_permission

# Entity types whose record status is kept in step with its approval.
StatusSetter = Callable[[Session, str, str], None]


def _sync_recommendation(db: Session, entity_id: str, status: str) -> None:
    from app.models.planning import Recommendation

    row = db.get(Recommendation, entity_id)
    if row:
        row.status = status


def _sync_rebalance(db: Session, entity_id: str, status: str) -> None:
    from app.core.constants import RebalanceStatus
    from app.models.workflow import Rebalance

    mapping = {
        ApprovalStatus.DRAFT: RebalanceStatus.DRAFT,
        ApprovalStatus.SUBMITTED: RebalanceStatus.PENDING_REVIEW,
        ApprovalStatus.UNDER_REVIEW: RebalanceStatus.PENDING_REVIEW,
        ApprovalStatus.APPROVED: RebalanceStatus.APPROVED,
        ApprovalStatus.COMPLETED: RebalanceStatus.COMPLETED,
    }
    row = db.get(Rebalance, entity_id)
    if row:
        row.status = str(mapping.get(status, status))
        if status == ApprovalStatus.COMPLETED:
            row.executed_at = datetime.now(timezone.utc)


def _sync_harvest(db: Session, entity_id: str, status: str) -> None:
    from app.models.tax import Harvest

    mapping = {
        ApprovalStatus.SUBMITTED: "under_review",
        ApprovalStatus.UNDER_REVIEW: "under_review",
        ApprovalStatus.APPROVED: "approved",
        ApprovalStatus.REJECTED: "rejected",
        ApprovalStatus.COMPLETED: "executed",
    }
    row = db.get(Harvest, entity_id)
    if row:
        row.status = mapping.get(status, status)
        if status == ApprovalStatus.COMPLETED:
            row.executed_at = datetime.now(timezone.utc)


def _sync_beneficiary(db: Session, entity_id: str, status: str) -> None:
    from app.models.estate import Beneficiary

    row = db.get(Beneficiary, entity_id)
    if not row:
        return
    if status == ApprovalStatus.COMPLETED:
        if row.pending_percentage is not None:
            row.percentage = row.pending_percentage
            row.pending_percentage = None
        row.status = "completed"
        row.last_confirmed_on = date.today()
    elif status in {ApprovalStatus.SUBMITTED, ApprovalStatus.UNDER_REVIEW}:
        row.status = "under_review"
    elif status == ApprovalStatus.APPROVED:
        row.status = "approved"
    elif status == ApprovalStatus.REJECTED:
        row.status = "rejected"
        row.pending_percentage = None
    else:
        row.status = "draft"


def _sync_distribution(db: Session, entity_id: str, status: str) -> None:
    from app.models.estate import DistributionRequest

    row = db.get(DistributionRequest, entity_id)
    if row:
        row.status = status


SYNC_HANDLERS: dict[str, StatusSetter] = {
    EntityType.RECOMMENDATION: _sync_recommendation,
    EntityType.REBALANCE: _sync_rebalance,
    EntityType.HARVEST: _sync_harvest,
    EntityType.BENEFICIARY: _sync_beneficiary,
    EntityType.DISTRIBUTION: _sync_distribution,
}

# Who may decide on each kind of request.
DECISION_ROLES: dict[str, set[str]] = {
    EntityType.RECOMMENDATION: {Role.ADVISOR, Role.INVESTMENT_TEAM, Role.ADMIN},
    EntityType.REBALANCE: {Role.ADVISOR, Role.INVESTMENT_TEAM, Role.ADMIN},
    EntityType.HARVEST: {Role.ADVISOR, Role.TAX_SPECIALIST, Role.ADMIN},
    EntityType.BENEFICIARY: {Role.ADVISOR, Role.ESTATE_TRUST, Role.COMPLIANCE, Role.ADMIN},
    EntityType.DISTRIBUTION: {Role.ADVISOR, Role.ESTATE_TRUST, Role.COMPLIANCE, Role.ADMIN},
    EntityType.COMPLIANCE_TEST: {Role.COMPLIANCE, Role.ADMIN},
    EntityType.PLAN: {Role.PLAN_SPONSOR, Role.COMPLIANCE, Role.ADMIN},
}


class ApprovalEngine:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)

    # -- creation -----------------------------------------------------
    def create(
        self,
        *,
        entity_type: str,
        entity_id: str | None,
        title: str,
        summary: str | None = None,
        household_id: str | None = None,
        plan_id: str | None = None,
        requested_by: User | None = None,
        assigned_to_id: str | None = None,
        required_role: str = Role.ADVISOR,
        priority: str = "medium",
        due_date: date | None = None,
        payload: dict[str, Any] | None = None,
        estimated_impact: float | None = None,
        status: str = ApprovalStatus.DRAFT,
        commit: bool = True,
    ) -> Approval:
        approval = Approval(
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            summary=summary,
            household_id=household_id,
            plan_id=plan_id,
            requested_by_id=getattr(requested_by, "id", None),
            assigned_to_id=assigned_to_id,
            required_role=str(required_role),
            priority=priority,
            due_date=due_date,
            payload=payload or {},
            estimated_impact=estimated_impact,
            status=str(status),
            submitted_at=datetime.now(timezone.utc) if status == ApprovalStatus.SUBMITTED else None,
        )
        self.db.add(approval)
        self.db.flush()

        self._log_event(approval, None, str(status), requested_by, "Request created")
        if entity_id:
            self._sync_entity(entity_type, entity_id, str(status))

        self.audit.record(
            action=AuditAction.CREATE,
            entity_type=EntityType.APPROVAL,
            entity_id=approval.id,
            entity_label=title,
            actor=requested_by,
            household_id=household_id,
            summary=f"Approval request created for {entity_type}",
            after={"status": str(status), "entity_type": entity_type},
            commit=False,
        )
        if commit:
            self.db.commit()
            self.db.refresh(approval)
        return approval

    # -- transitions --------------------------------------------------
    def transition(
        self,
        approval_id: str,
        to_status: str,
        *,
        actor: User,
        note: str | None = None,
        enforce_role: bool = True,
    ) -> Approval:
        approval = self.db.get(Approval, approval_id)
        if not approval:
            raise NotFoundError("Approval request not found.")

        from_status = approval.status
        allowed = APPROVAL_TRANSITIONS.get(from_status, set())
        if to_status not in {str(s) for s in allowed}:
            raise UnprocessableWorkflowError(
                f"An approval cannot move from {from_status.replace('_', ' ')} to {to_status.replace('_', ' ')}.",
                details={"from": from_status, "to": to_status, "allowed": sorted(str(s) for s in allowed)},
            )

        if enforce_role and to_status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            self._assert_can_decide(approval, actor)

        approval.status = to_status
        now = datetime.now(timezone.utc)
        if to_status == ApprovalStatus.SUBMITTED:
            approval.submitted_at = now
        if to_status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            approval.decided_at = now
            approval.decided_by_id = actor.id
            approval.decision_note = note
        if to_status == ApprovalStatus.COMPLETED:
            approval.completed_at = now

        self._log_event(approval, from_status, to_status, actor, note)
        if approval.entity_id:
            self._sync_entity(approval.entity_type, approval.entity_id, to_status)

        action = {
            ApprovalStatus.SUBMITTED: AuditAction.APPROVAL_SUBMITTED,
            ApprovalStatus.UNDER_REVIEW: AuditAction.APPROVAL_REVIEWED,
            ApprovalStatus.APPROVED: AuditAction.APPROVAL_DECIDED,
            ApprovalStatus.REJECTED: AuditAction.APPROVAL_DECIDED,
            ApprovalStatus.COMPLETED: AuditAction.APPROVAL_COMPLETED,
        }.get(to_status, AuditAction.UPDATE)

        self.audit.record(
            action=action,
            entity_type=EntityType.APPROVAL,
            entity_id=approval.id,
            entity_label=approval.title,
            actor=actor,
            household_id=approval.household_id,
            summary=note or f"Approval moved to {to_status.replace('_', ' ')}",
            before={"status": from_status},
            after={"status": to_status, "decision_note": note},
            commit=False,
        )

        self.db.commit()
        self.db.refresh(approval)
        return approval

    def submit(self, approval_id: str, actor: User, note: str | None = None) -> Approval:
        return self.transition(approval_id, ApprovalStatus.SUBMITTED, actor=actor, note=note)

    def start_review(self, approval_id: str, actor: User, note: str | None = None) -> Approval:
        return self.transition(approval_id, ApprovalStatus.UNDER_REVIEW, actor=actor, note=note)

    def approve(self, approval_id: str, actor: User, note: str | None = None) -> Approval:
        return self.transition(approval_id, ApprovalStatus.APPROVED, actor=actor, note=note)

    def reject(self, approval_id: str, actor: User, note: str | None = None) -> Approval:
        return self.transition(approval_id, ApprovalStatus.REJECTED, actor=actor, note=note)

    def cancel(self, approval_id: str, actor: User, note: str | None = None) -> Approval:
        return self.transition(approval_id, ApprovalStatus.CANCELLED, actor=actor, note=note)

    def complete(self, approval_id: str, actor: User, note: str | None = None) -> Approval:
        """Mark the approved action as carried out (simulated execution)."""
        return self.transition(approval_id, ApprovalStatus.COMPLETED, actor=actor, note=note)

    # -- queries ------------------------------------------------------
    def list(
        self,
        *,
        household_ids: Sequence[str] | None = None,
        status: str | None = None,
        entity_type: str | None = None,
        assigned_to_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Approval], int]:
        stmt = select(Approval)
        if household_ids is not None:
            stmt = stmt.where(Approval.household_id.in_(list(household_ids)))
        if status:
            stmt = stmt.where(Approval.status == status)
        if entity_type:
            stmt = stmt.where(Approval.entity_type == entity_type)
        if assigned_to_id:
            stmt = stmt.where(Approval.assigned_to_id == assigned_to_id)

        total = len(self.db.execute(stmt).scalars().all())
        rows = list(
            self.db.execute(stmt.order_by(Approval.created_at.desc()).limit(limit).offset(offset)).scalars().all()
        )
        return rows, total

    def get(self, approval_id: str) -> Approval:
        approval = self.db.get(Approval, approval_id)
        if not approval:
            raise NotFoundError("Approval request not found.")
        return approval

    def pending_count(self, household_ids: Sequence[str] | None = None) -> int:
        stmt = select(Approval).where(
            Approval.status.in_([ApprovalStatus.SUBMITTED, ApprovalStatus.UNDER_REVIEW])
        )
        if household_ids is not None:
            stmt = stmt.where(Approval.household_id.in_(list(household_ids)))
        return len(self.db.execute(stmt).scalars().all())

    def available_transitions(self, approval: Approval, user: User) -> list[str]:
        candidates = sorted(str(s) for s in APPROVAL_TRANSITIONS.get(approval.status, set()))
        result = []
        for candidate in candidates:
            if candidate in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
                try:
                    self._assert_can_decide(approval, user)
                except ForbiddenError:
                    continue
            result.append(candidate)
        return result

    # -- internals ----------------------------------------------------
    def _assert_can_decide(self, approval: Approval, actor: User) -> None:
        if not has_permission(actor, Permission.APPROVE):
            raise ForbiddenError("Your role cannot approve or reject requests.")
        allowed_roles = DECISION_ROLES.get(approval.entity_type)
        if allowed_roles and actor.role not in allowed_roles:
            raise ForbiddenError(
                f"A {approval.entity_type.replace('_', ' ')} request must be decided by "
                f"{', '.join(sorted(allowed_roles))}.",
                details={"allowed_roles": sorted(allowed_roles)},
            )
        if approval.requested_by_id and approval.requested_by_id == actor.id and actor.role != Role.ADMIN:
            raise ForbiddenError("You cannot approve a request you submitted yourself.")

    def _log_event(
        self, approval: Approval, from_status: str | None, to_status: str, actor: User | None, note: str | None
    ) -> None:
        self.db.add(
            ApprovalEvent(
                approval_id=approval.id,
                from_status=from_status,
                to_status=to_status,
                actor_id=getattr(actor, "id", None),
                actor_name=getattr(actor, "full_name", None) or "System",
                note=note,
            )
        )

    def _sync_entity(self, entity_type: str, entity_id: str, status: str) -> None:
        handler = SYNC_HANDLERS.get(entity_type)
        if handler:
            handler(self.db, entity_id, status)
