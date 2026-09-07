"""FastAPI dependencies: current user, permission gates and household scoping.

Authorisation is enforced here, on the server, for every protected route (§46).
"""

from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.constants import Permission, Role
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.db.session import get_db
from app.models.identity import Client, User
from app.services.auth_service import AuthService, has_permission

DbSession = Annotated[Session, Depends(get_db)]


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


def get_audit_service(db: DbSession) -> AuditService:
    return AuditService(db)


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Sign in to continue.", code="missing_token")
    token = authorization.split(" ", 1)[1].strip()
    return AuthService(db).resolve_token(token)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    if not authorization:
        return None
    try:
        return get_current_user(db, authorization)
    except (UnauthorizedError, ForbiddenError):
        return None


def require(*permissions: Permission) -> Callable[[User], User]:
    """Route guard: the caller must hold at least one of these permissions."""

    def dependency(user: CurrentUser) -> User:
        if not any(has_permission(user, permission) for permission in permissions):
            raise ForbiddenError(
                "You do not have permission to view this resource.",
                details={"required_any_of": [str(p) for p in permissions]},
            )
        return user

    return dependency


def require_role(*roles: Role) -> Callable[[User], User]:
    def dependency(user: CurrentUser) -> User:
        if user.role not in {str(r) for r in roles} and user.role != Role.ADMIN:
            raise ForbiddenError(
                "This workspace is not available for your role.",
                details={"allowed_roles": [str(r) for r in roles]},
            )
        return user

    return dependency


def resolve_household_id(db: Session, user: User, requested: str | None = None) -> str:
    """Pick the household to operate on, and prove the caller may see it.

    A client is pinned to their own household. Everyone else may pass an explicit
    id, subject to their assignment scope.
    """
    auth = AuthService(db)
    allowed = auth.accessible_household_ids(user)

    if user.role == Role.CLIENT:
        client = db.query(Client).filter(Client.user_id == user.id).one_or_none()
        if not client:
            raise NotFoundError("No client profile is linked to this account.")
        if requested and requested != client.household_id:
            raise ForbiddenError("You can only view your own household.")
        return client.household_id

    if requested:
        if allowed is not None and requested not in allowed:
            raise ForbiddenError("This household is not in your book of business.")
        return requested

    if allowed:
        return allowed[0]

    from app.models.identity import Household

    household = db.query(Household).order_by(Household.name).first()
    if not household:
        raise NotFoundError("No households exist yet. Run the seed script.")
    return household.id


def client_context(request: Request) -> dict[str, str | None]:
    """Request metadata attached to audit events."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
