"""Append-only audit trail (§38).

Every state change in the product routes through here so the activity timeline,
compliance review and the audit page all read from one place.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow import AuditEvent


class AuditAction:
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_UPDATE = "document_update"
    DOCUMENT_SHARE = "document_share"
    DOCUMENT_CLASSIFY = "document_classify"
    RECOMMENDATION_CREATED = "recommendation_created"
    APPROVAL_SUBMITTED = "approval_submitted"
    APPROVAL_REVIEWED = "approval_reviewed"
    APPROVAL_DECIDED = "approval_decided"
    APPROVAL_COMPLETED = "approval_completed"
    BENEFICIARY_CHANGE = "beneficiary_change"
    REBALANCE_CREATED = "rebalance_created"
    REBALANCE_EXECUTED = "rebalance_executed"
    HARVEST_CREATED = "harvest_created"
    HARVEST_EXECUTED = "harvest_executed"
    DISTRIBUTION_REQUESTED = "distribution_requested"
    COMPLIANCE_ACTION = "compliance_action"
    SCENARIO_RUN = "scenario_run"
    REPORT_GENERATED = "report_generated"
    GOAL_UPDATED = "goal_updated"


def _serialise(value: Any) -> Any:
    """JSON-safe snapshot of a before/after state."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _serialise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialise(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        entity_label: str | None = None,
        actor: Any | None = None,
        household_id: str | None = None,
        summary: str | None = None,
        status: str = "success",
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_id=getattr(actor, "id", None),
            actor_name=getattr(actor, "full_name", None) or "System",
            actor_role=getattr(actor, "role", None),
            household_id=household_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label,
            status=status,
            summary=summary,
            before_state=_serialise(before),
            after_state=_serialise(after),
            ip_address=ip_address,
            user_agent=(user_agent or "")[:255] or None,
        )
        self.db.add(event)
        if commit:
            self.db.commit()
            self.db.refresh(event)
        else:
            self.db.flush()
        return event

    def list_events(
        self,
        *,
        household_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Sequence[AuditEvent], int]:
        stmt = select(AuditEvent)
        if household_id:
            stmt = stmt.where(AuditEvent.household_id == household_id)
        if entity_type:
            stmt = stmt.where(AuditEvent.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditEvent.entity_id == entity_id)
        if actor_id:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        if action:
            stmt = stmt.where(AuditEvent.action == action)

        total = len(self.db.execute(stmt).scalars().all())
        rows = (
            self.db.execute(stmt.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset))
            .scalars()
            .all()
        )
        return rows, total

    def timeline_for_household(self, household_id: str, limit: int = 40) -> Sequence[AuditEvent]:
        rows, _ = self.list_events(household_id=household_id, limit=limit)
        return rows
