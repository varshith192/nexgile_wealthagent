"""Cross-cutting platform routes: approvals, audit, notifications, search,
reports, messaging and meetings.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.audit.service import AuditService
from app.core.constants import Permission
from app.core.deps import CurrentUser, DbSession, require, resolve_household_id
from app.reports.service import ReportService
from app.notifications.service import NotificationService
from app.schemas.requests import (
    ApprovalDecisionRequest,
    ApprovalTransitionRequest,
    MessageSendRequest,
    ReportGenerateRequest,
    SavedViewRequest,
    ThreadCreateRequest,
)
from app.services.auth_service import AuthService
from app.services.collaboration_service import MeetingService, MessagingService
from app.services.portfolio_service import PortfolioService
from app.services.search_service import SearchService
from app.workflows.approval_engine import ApprovalEngine

router = APIRouter(tags=["platform"])

ApproveGate = Annotated[object, Depends(require(Permission.APPROVE))]
AuditGate = Annotated[object, Depends(require(Permission.VIEW_AUDIT))]


# --------------------------------------------------------------- approvals
@router.get("/approvals")
def list_approvals(
    db: DbSession,
    user: CurrentUser,
    status_filter: str | None = Query(default=None),
    entity_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=5, le=200),
) -> dict:
    scope = AuthService(db).accessible_household_ids(user)
    engine = ApprovalEngine(db)
    rows, total = engine.list(
        household_ids=scope,
        status=status_filter,
        entity_type=entity_type,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return {
        "approvals": [_serialise_approval(db, a, user, engine) for a in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
        "pending_count": engine.pending_count(scope),
    }


def _serialise_approval(db, approval, user, engine: ApprovalEngine) -> dict:
    from app.models.identity import Household, User

    household = db.get(Household, approval.household_id) if approval.household_id else None
    requester = db.get(User, approval.requested_by_id) if approval.requested_by_id else None
    decider = db.get(User, approval.decided_by_id) if approval.decided_by_id else None
    return {
        "id": approval.id,
        "title": approval.title,
        "summary": approval.summary,
        "entity_type": approval.entity_type,
        "entity_id": approval.entity_id,
        "status": approval.status,
        "priority": approval.priority,
        "household_id": approval.household_id,
        "household": household.name if household else None,
        "requested_by": requester.full_name if requester else "System",
        "decided_by": decider.full_name if decider else None,
        "required_role": approval.required_role,
        "estimated_impact": approval.estimated_impact,
        "decision_note": approval.decision_note,
        "payload": approval.payload,
        "created_at": approval.created_at.isoformat(),
        "submitted_at": approval.submitted_at.isoformat() if approval.submitted_at else None,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        "completed_at": approval.completed_at.isoformat() if approval.completed_at else None,
        "due_date": approval.due_date.isoformat() if approval.due_date else None,
        "available_transitions": engine.available_transitions(approval, user),
        "events": [
            {
                "id": e.id,
                "from_status": e.from_status,
                "to_status": e.to_status,
                "actor_name": e.actor_name,
                "note": e.note,
                "created_at": e.created_at.isoformat(),
            }
            for e in approval.events
        ],
    }


@router.get("/approvals/{approval_id}")
def approval_detail(approval_id: str, db: DbSession, user: CurrentUser) -> dict:
    engine = ApprovalEngine(db)
    approval = engine.get(approval_id)
    if approval.household_id:
        resolve_household_id(db, user, approval.household_id)
    return _serialise_approval(db, approval, user, engine)


@router.post("/approvals/{approval_id}/submit")
def submit_approval(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    db: DbSession,
    user: Annotated[object, Depends(require(Permission.SUBMIT_APPROVAL, Permission.APPROVE))],
) -> dict:
    engine = ApprovalEngine(db)
    approval = engine.submit(approval_id, user, payload.note)
    return _serialise_approval(db, approval, user, engine)


@router.post("/approvals/{approval_id}/review")
def review_approval(
    approval_id: str, payload: ApprovalDecisionRequest, db: DbSession, user: ApproveGate
) -> dict:
    engine = ApprovalEngine(db)
    approval = engine.start_review(approval_id, user, payload.note)
    return _serialise_approval(db, approval, user, engine)


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, payload: ApprovalDecisionRequest, db: DbSession, user: ApproveGate) -> dict:
    engine = ApprovalEngine(db)
    approval = engine.approve(approval_id, user, payload.note)
    return _serialise_approval(db, approval, user, engine)


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, payload: ApprovalDecisionRequest, db: DbSession, user: ApproveGate) -> dict:
    engine = ApprovalEngine(db)
    approval = engine.reject(approval_id, user, payload.note)
    return _serialise_approval(db, approval, user, engine)


@router.post("/approvals/{approval_id}/complete")
def complete(approval_id: str, payload: ApprovalDecisionRequest, db: DbSession, user: ApproveGate) -> dict:
    engine = ApprovalEngine(db)
    approval = engine.complete(approval_id, user, payload.note)
    return _serialise_approval(db, approval, user, engine)


@router.post("/approvals/{approval_id}/transition")
def transition(
    approval_id: str,
    payload: ApprovalTransitionRequest,
    db: DbSession,
    user: Annotated[object, Depends(require(Permission.SUBMIT_APPROVAL, Permission.APPROVE))],
) -> dict:
    engine = ApprovalEngine(db)
    approval = engine.transition(approval_id, payload.to_status, actor=user, note=payload.note)
    return _serialise_approval(db, approval, user, engine)


# ------------------------------------------------------------------ audit
@router.get("/audit")
def audit_trail(
    db: DbSession,
    user: AuditGate,
    household_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=5, le=200),
) -> dict:
    hid = resolve_household_id(db, user, household_id) if household_id else None
    rows, total = AuditService(db).list_events(
        household_id=hid,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return {
        "events": [
            {
                "id": e.id,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "entity_label": e.entity_label,
                "actor_name": e.actor_name,
                "actor_role": e.actor_role,
                "household_id": e.household_id,
                "status": e.status,
                "summary": e.summary,
                "before_state": e.before_state,
                "after_state": e.after_state,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat(),
            }
            for e in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


# ---------------------------------------------------------- notifications
@router.get("/notifications")
def notifications(
    db: DbSession,
    user: CurrentUser,
    unread_only: bool = False,
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    scope = AuthService(db).accessible_household_ids(user)
    return NotificationService(db).list(
        user, unread_only=unread_only, category=category, limit=limit, household_ids=scope
    )


@router.post("/notifications/{alert_id}/read")
def mark_notification_read(alert_id: str, db: DbSession, user: CurrentUser) -> dict:
    return NotificationService(db).mark_read(alert_id, user)


@router.post("/notifications/read-all")
def mark_all_read(db: DbSession, user: CurrentUser) -> dict:
    return {"updated": NotificationService(db).mark_all_read(user)}


@router.delete("/notifications/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_notification(alert_id: str, db: DbSession, user: CurrentUser) -> None:
    NotificationService(db).dismiss(alert_id, user)


# ----------------------------------------------------------------- search
@router.get("/search")
def search(
    db: DbSession,
    user: CurrentUser,
    q: str = Query(min_length=1, max_length=200),
    categories: str | None = Query(default=None, description="Comma-separated category filter"),
) -> dict:
    scope = AuthService(db).accessible_household_ids(user)
    selected = [c.strip() for c in categories.split(",")] if categories else None
    return SearchService(db).search(q, user, scope, categories=selected)


@router.get("/search/suggestions")
def search_suggestions(db: DbSession, user: CurrentUser) -> dict:
    return SearchService(db).suggestions(user)


@router.post("/search/saved-views", status_code=status.HTTP_201_CREATED)
def save_view(payload: SavedViewRequest, db: DbSession, user: CurrentUser) -> dict:
    return SearchService(db).save_view(user, payload.name, payload.query, payload.categories)


# ---------------------------------------------------------------- reports
@router.get("/reports")
def list_reports(db: DbSession, user: CurrentUser, household_id: str | None = None) -> dict:
    hid = resolve_household_id(db, user, household_id)
    service = ReportService(db)
    return {"reports": service.list(hid), "catalogue": service.catalogue()}


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def generate_report(payload: ReportGenerateRequest, db: DbSession, user: CurrentUser) -> dict:
    hid = resolve_household_id(db, user, payload.household_id)
    return ReportService(db).generate(
        household_id=hid,
        report_type=payload.report_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        actor=user,
        benchmark_code=payload.benchmark_code,
    )


@router.get("/reports/{report_id}")
def report_detail(report_id: str, db: DbSession, user: CurrentUser) -> dict:
    report = ReportService(db).get(report_id)
    if report.get("household_id"):
        resolve_household_id(db, user, report["household_id"])
    return report


# --------------------------------------------------------------- messages
@router.get("/messages")
def message_threads(
    db: DbSession, user: CurrentUser, household_id: str | None = None, search: str | None = None
) -> dict:
    hid = resolve_household_id(db, user, household_id)
    return {"threads": MessagingService(db).threads(hid, search=search)}


@router.post("/messages", status_code=status.HTTP_201_CREATED)
def start_thread(payload: ThreadCreateRequest, db: DbSession, user: CurrentUser) -> dict:
    hid = resolve_household_id(db, user, payload.household_id)
    return MessagingService(db).start_thread(hid, payload.subject, payload.body, user, payload.topic)


@router.get("/messages/{thread_id}")
def message_thread(thread_id: str, db: DbSession, user: CurrentUser) -> dict:
    service = MessagingService(db)
    thread = service.thread(thread_id)
    return thread


@router.post("/messages/{thread_id}/reply", status_code=status.HTTP_201_CREATED)
def reply(thread_id: str, payload: MessageSendRequest, db: DbSession, user: CurrentUser) -> dict:
    return MessagingService(db).send(
        thread_id, payload.body, user, attachment_document_id=payload.attachment_document_id
    )


@router.post("/messages/{thread_id}/read")
def mark_thread_read(thread_id: str, db: DbSession, user: CurrentUser) -> dict:
    return {"marked_read": MessagingService(db).mark_read(thread_id, user)}


# --------------------------------------------------------------- meetings
@router.get("/meetings")
def meetings(db: DbSession, user: CurrentUser, household_id: str | None = None) -> dict:
    hid = resolve_household_id(db, user, household_id)
    return MeetingService(db).list(hid)


@router.get("/meetings/{meeting_id}")
def meeting_detail(meeting_id: str, db: DbSession, user: CurrentUser) -> dict:
    return MeetingService(db).detail(meeting_id)


@router.post("/meetings/action-items/{item_id}/complete")
def complete_action_item(item_id: str, db: DbSession, user: CurrentUser) -> dict:
    return MeetingService(db).complete_action_item(item_id, user)
