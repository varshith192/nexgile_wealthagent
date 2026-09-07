"""Authentication routes. One sign-in path for every role (§5)."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.audit.service import AuditAction
from app.core.constants import EntityType, ROLE_LABELS
from app.core.deps import CurrentUser, DbSession, client_context
from app.core.errors import UnauthorizedError
from app.schemas.requests import LoginRequest
from app.schemas.responses import DemoAccount, TokenResponse, UserProfile
from app.audit.service import AuditService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: DbSession) -> dict:
    auth = AuthService(db)
    audit = AuditService(db)
    meta = client_context(request)

    try:
        user = auth.authenticate(payload.email, payload.password)
    except UnauthorizedError:
        audit.record(
            action=AuditAction.LOGIN_FAILED,
            entity_type=EntityType.SESSION,
            entity_label=payload.email,
            status="failed",
            summary="Sign-in attempt failed",
            **meta,
        )
        raise

    result = auth.issue_token(user, remember=payload.remember_me)
    audit.record(
        action=AuditAction.LOGIN,
        entity_type=EntityType.SESSION,
        entity_id=user.id,
        entity_label=user.email,
        actor=user,
        household_id=result["user"].get("household_id"),
        summary=f"Signed in as {ROLE_LABELS.get(user.role, user.role)}",
        **meta,
    )
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: CurrentUser, request: Request, db: DbSession) -> None:
    AuditService(db).record(
        action=AuditAction.LOGOUT,
        entity_type=EntityType.SESSION,
        entity_id=user.id,
        entity_label=user.email,
        actor=user,
        summary="Signed out",
        **client_context(request),
    )


@router.get("/me", response_model=UserProfile)
def me(user: CurrentUser, db: DbSession) -> dict:
    return AuthService(db).profile(user)


@router.get("/demo-accounts", response_model=list[DemoAccount])
def demo_accounts(db: DbSession) -> list[dict]:
    """Labelled demo identities for evaluation. No production credentials (§6)."""
    return AuthService(db).demo_accounts()
