"""WealthAgent surface: insights, recommendations, actions, chat (§19)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.ai.service import get_ai_service
from app.core.constants import Permission
from app.core.deps import CurrentUser, DbSession, require, resolve_household_id
from app.schemas.requests import (
    AskRequest,
    ExplainRequest,
    RecommendationCreateRequest,
    RecommendationFromDraftRequest,
)
from app.services.wealthagent_service import WealthAgentService

router = APIRouter(tags=["wealthagent"])

WealthRead = Annotated[object, Depends(require(Permission.VIEW_OWN_WEALTH, Permission.VIEW_CLIENT_WEALTH))]
RecWrite = Annotated[object, Depends(require(Permission.CREATE_RECOMMENDATION, Permission.SUBMIT_APPROVAL))]


@router.get("/wealthagent")
def workspace(db: DbSession, user: CurrentUser, _: WealthRead, household_id: str | None = None) -> dict:
    hid = resolve_household_id(db, user, household_id)
    return WealthAgentService(db).workspace(hid)


@router.get("/wealthagent/insights")
def insights(db: DbSession, user: CurrentUser, _: WealthRead, household_id: str | None = None) -> list[dict]:
    hid = resolve_household_id(db, user, household_id)
    return WealthAgentService(db).insights(hid)


@router.get("/wealthagent/actions")
def actions(db: DbSession, user: CurrentUser, _: WealthRead, household_id: str | None = None) -> list[dict]:
    hid = resolve_household_id(db, user, household_id)
    return WealthAgentService(db).actions(hid)


@router.post("/wealthagent/ask")
def ask(payload: AskRequest, db: DbSession, user: CurrentUser, _: WealthRead) -> dict:
    """Answers are grounded in the household's verified figures only."""
    hid = resolve_household_id(db, user, payload.household_id)
    return WealthAgentService(db).ask(hid, payload.question, user)


@router.post("/wealthagent/explain")
def explain(payload: ExplainRequest, db: DbSession, user: CurrentUser, _: WealthRead) -> dict:
    return WealthAgentService(db).explain(payload.calculation, payload.audience)


@router.get("/wealthagent/provider")
def provider_info() -> dict:
    """Which intelligence layer is serving requests, and whether a key is set."""
    return get_ai_service().info.model_dump()


# ----------------------------------------------------------- recommendations
@router.get("/recommendations")
def list_recommendations(
    db: DbSession,
    user: CurrentUser,
    _: WealthRead,
    household_id: str | None = None,
    status_filter: str | None = None,
) -> list[dict]:
    hid = resolve_household_id(db, user, household_id)
    return WealthAgentService(db).list_recommendations(hid, status=status_filter)


@router.get("/recommendations/drafts")
def recommendation_drafts(
    db: DbSession, user: CurrentUser, _: WealthRead, household_id: str | None = None
) -> list[dict]:
    hid = resolve_household_id(db, user, household_id)
    return WealthAgentService(db).recommendations_preview(hid)


@router.post("/recommendations", status_code=status.HTTP_201_CREATED)
def create_recommendation(payload: RecommendationCreateRequest, db: DbSession, user: RecWrite) -> dict:
    hid = resolve_household_id(db, user, payload.household_id)
    return WealthAgentService(db).create_recommendation(
        hid, payload.model_dump(exclude={"household_id", "submit"}), user, submit=payload.submit
    )


@router.post("/recommendations/from-draft", status_code=status.HTTP_201_CREATED)
def create_from_draft(payload: RecommendationFromDraftRequest, db: DbSession, user: RecWrite) -> dict:
    """Promote an agent draft into a tracked recommendation with an approval record."""
    hid = resolve_household_id(db, user, payload.household_id)
    return WealthAgentService(db).create_from_draft(hid, payload.draft_key, user, submit=payload.submit)


@router.get("/recommendations/{recommendation_id}")
def recommendation_detail(recommendation_id: str, db: DbSession, user: CurrentUser, _: WealthRead) -> dict:
    service = WealthAgentService(db)
    rec = service.get_recommendation(recommendation_id)
    resolve_household_id(db, user, rec.household_id)
    return service.serialise_recommendation(rec)
