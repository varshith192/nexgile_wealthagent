"""Institutional workspace, participant portal and compliance centre."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.constants import Permission
from app.core.deps import CurrentUser, DbSession, require
from app.schemas.requests import RetirementReadinessRequest
from app.services.institutional_service import InstitutionalService

router = APIRouter(tags=["institutional"])

PlanRead = Annotated[object, Depends(require(Permission.VIEW_INSTITUTIONAL, Permission.VIEW_COMPLIANCE))]
ParticipantRead = Annotated[object, Depends(require(Permission.VIEW_PARTICIPANT, Permission.VIEW_INSTITUTIONAL))]
ComplianceRead = Annotated[object, Depends(require(Permission.VIEW_COMPLIANCE))]
ComplianceWrite = Annotated[object, Depends(require(Permission.MANAGE_COMPLIANCE))]


def _today() -> date:
    return date.today()


# ----------------------------------------------------------- plan sponsor
@router.get("/institutional")
def institutional_dashboard(db: DbSession, user: PlanRead, plan_id: str | None = None) -> dict:
    return InstitutionalService(db).sponsor_dashboard(plan_id, _today())


@router.get("/plans")
def plans(db: DbSession, user: PlanRead) -> list[dict]:
    return InstitutionalService(db).plans()


@router.get("/plans/{plan_id}")
def plan_detail(plan_id: str, db: DbSession, user: PlanRead) -> dict:
    return InstitutionalService(db).sponsor_dashboard(plan_id, _today())


@router.get("/participants")
def participants(
    db: DbSession,
    user: PlanRead,
    plan_id: str | None = None,
    search: str | None = None,
    status_filter: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=5, le=100),
) -> dict:
    return InstitutionalService(db).participants(
        plan_id, search=search, status=status_filter, page=page, page_size=page_size
    )


@router.get("/institutional/investments")
def investment_lineup(db: DbSession, user: PlanRead, plan_id: str | None = None) -> dict:
    """Fiduciary oversight: IPS screening of the fund lineup (§30)."""
    return InstitutionalService(db).investment_lineup(plan_id, _today())


@router.get("/institutional/fees")
def plan_fees(db: DbSession, user: PlanRead, plan_id: str | None = None) -> dict:
    return InstitutionalService(db).fee_review(plan_id, _today())


# ------------------------------------------------------------- compliance
@router.get("/compliance")
def compliance_centre(db: DbSession, user: ComplianceRead, plan_id: str | None = None) -> dict:
    return InstitutionalService(db).compliance_summary(plan_id, _today())


@router.post("/compliance/tests/{test_id}/run")
def run_compliance_test(test_id: str, db: DbSession, user: ComplianceWrite) -> dict:
    return InstitutionalService(db).run_compliance_test(test_id, user, _today())


# ------------------------------------------------------------ participant
@router.get("/participant")
def participant_portal(db: DbSession, user: ParticipantRead) -> dict:
    return InstitutionalService(db).participant_portal(user, _today())


@router.get("/participant/readiness")
def participant_readiness(db: DbSession, user: ParticipantRead, participant_id: str | None = None) -> dict:
    service = InstitutionalService(db)
    if not participant_id:
        portal = service.participant_portal(user, _today())
        participant_id = portal["participant"]["id"]
    return service.retirement_readiness(participant_id, _today())


@router.post("/participant/readiness")
def participant_readiness_scenario(
    payload: RetirementReadinessRequest, db: DbSession, user: ParticipantRead, participant_id: str | None = None
) -> dict:
    """Re-run the projection with user-supplied inputs (§34). Read-only."""
    service = InstitutionalService(db)
    if not participant_id:
        portal = service.participant_portal(user, _today())
        participant_id = portal["participant"]["id"]
    return service.retirement_readiness(participant_id, _today(), payload.model_dump(exclude_none=True))


@router.get("/participant/education")
def participant_education(db: DbSession, user: ParticipantRead, participant_id: str | None = None) -> dict:
    service = InstitutionalService(db)
    if not participant_id:
        portal = service.participant_portal(user, _today())
        participant_id = portal["participant"]["id"]
    return service.education_for_participant(participant_id)


@router.get("/education")
def education_catalogue(db: DbSession, user: CurrentUser) -> list[dict]:
    return InstitutionalService(db).education_catalogue()
