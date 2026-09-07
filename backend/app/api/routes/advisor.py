"""Advisor workstation, Client 360, rebalancing and tasks."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.constants import Permission
from app.core.deps import CurrentUser, DbSession, require, resolve_household_id
from app.schemas.requests import RebalanceCreateRequest, TaskUpdateRequest
from app.services.advisor_service import AdvisorService
from app.services.auth_service import AuthService
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/advisor", tags=["advisor"])

AdvisorRead = Annotated[object, Depends(require(Permission.VIEW_CLIENT_WEALTH))]
RebalanceWrite = Annotated[object, Depends(require(Permission.MANAGE_REBALANCE))]


@router.get("")
def advisor_dashboard(db: DbSession, user: AdvisorRead) -> dict:
    scope = AuthService(db).accessible_household_ids(user)
    return AdvisorService(db).dashboard(user, scope)


@router.get("/clients")
def advisor_clients(db: DbSession, user: AdvisorRead, search: str | None = None) -> dict:
    scope = AuthService(db).accessible_household_ids(user)
    rows = AdvisorService(db).client_rows(scope)
    if search:
        needle = search.lower()
        rows = [r for r in rows if needle in r["name"].lower() or needle in (r["primary_contact"] or "").lower()]
    return {
        "clients": rows,
        "total": len(rows),
        "summary": {
            "total_aum": round(sum(r["total_assets"] for r in rows), 2),
            "households": len(rows),
            "pending_approvals": sum(r["pending_approvals"] for r in rows),
            "goals_off_track": sum(r["goals_off_track"] for r in rows),
        },
    }


@router.get("/clients/{household_id}")
def client_360(household_id: str, db: DbSession, user: AdvisorRead) -> dict:
    """The advisor Client 360 view (§21)."""
    hid = resolve_household_id(db, user, household_id)
    return AdvisorService(db).client_360(hid)


@router.get("/portfolio")
def advisor_portfolio(db: DbSession, user: AdvisorRead, household_id: str | None = None) -> dict:
    hid = resolve_household_id(db, user, household_id)
    service = PortfolioService(db)
    return {
        "household_id": hid,
        "analytics": service.advisory_analytics(hid),
        "allocation": service.allocation(hid),
        "drift": service.drift(hid),
        "valuation": service.valuation(hid),
        "performance": service.performance(hid),
    }


@router.get("/rebalancing")
def list_rebalances(
    db: DbSession, user: AdvisorRead, status_filter: str | None = Query(default=None)
) -> list[dict]:
    scope = AuthService(db).accessible_household_ids(user)
    return AdvisorService(db).list_rebalances(scope, status_filter)


@router.post("/rebalancing", status_code=status.HTTP_201_CREATED)
def propose_rebalance(payload: RebalanceCreateRequest, db: DbSession, user: RebalanceWrite) -> dict:
    hid = resolve_household_id(db, user, payload.household_id)
    return AdvisorService(db).propose_rebalance(hid, user, name=payload.name, note=payload.note)


@router.get("/rebalancing/{rebalance_id}")
def rebalance_detail(rebalance_id: str, db: DbSession, user: AdvisorRead) -> dict:
    return AdvisorService(db).rebalance_detail(rebalance_id)


@router.post("/rebalancing/{rebalance_id}/execute")
def execute_rebalance(rebalance_id: str, db: DbSession, user: RebalanceWrite) -> dict:
    """Simulated execution. Nexgile never routes an order to a broker."""
    return AdvisorService(db).execute_rebalance(rebalance_id, user)


@router.get("/tasks")
def advisor_tasks(db: DbSession, user: AdvisorRead, status_filter: str | None = None) -> list[dict]:
    scope = AuthService(db).accessible_household_ids(user)
    return AdvisorService(db).tasks(scope, status_filter)


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdateRequest, db: DbSession, user: AdvisorRead) -> dict:
    return AdvisorService(db).update_task(task_id, payload.status, user)
