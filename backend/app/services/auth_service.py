"""Authentication and the role/permission resolution that follows it.

One sign-in path serves every role (§5). Which identity provider verifies the
credential is a configuration detail:

  AUTH_PROVIDER=local     issue and verify our own JWT against the users table
  AUTH_PROVIDER=supabase  verify a Supabase Auth access token, then map the
                          Supabase user onto the local profile that carries role,
                          household and permissions

Either way the rest of the application receives the same `User` row and the same
permission set, so authorisation logic never branches on the provider.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import ROLE_HOME, ROLE_LABELS, ROLE_PERMISSIONS, Permission, Role
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.models.identity import Client, User


def permissions_for(role: str) -> set[Permission]:
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(user: User, permission: Permission) -> bool:
    perms = permissions_for(user.role)
    return Permission.ADMIN_ALL in perms or permission in perms


def require_permission(user: User, permission: Permission) -> None:
    if not has_permission(user, permission):
        raise ForbiddenError(
            f"Your role ({ROLE_LABELS.get(user.role, user.role)}) does not have access to this resource.",
            details={"required_permission": str(permission)},
        )


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- lookups ------------------------------------------------------
    def get_by_email(self, email: str) -> User | None:
        return self.db.execute(select(User).where(User.email == email.lower().strip())).scalar_one_or_none()

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_supabase_id(self, supabase_user_id: str) -> User | None:
        return self.db.execute(
            select(User).where(User.supabase_user_id == supabase_user_id)
        ).scalar_one_or_none()

    # -- sign in ------------------------------------------------------
    def authenticate(self, email: str, password: str) -> User:
        """Verify a credential with whichever provider is configured."""
        if settings.auth_provider == "supabase":
            return self._authenticate_supabase(email, password)
        return self._authenticate_local(email, password)

    def _authenticate_local(self, email: str, password: str) -> User:
        user = self.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Incorrect email or password.", code="invalid_credentials")
        if not user.is_active:
            raise ForbiddenError("This account has been deactivated. Contact your administrator.")
        return user

    def _authenticate_supabase(self, email: str, password: str) -> User:  # pragma: no cover - external service
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise UnauthorizedError(
                "Supabase authentication is selected but SUPABASE_URL / SUPABASE_ANON_KEY are not configured.",
                code="auth_not_configured",
            )
        response = httpx.post(
            f"{settings.supabase_url}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.supabase_anon_key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=15.0,
        )
        if response.status_code != 200:
            raise UnauthorizedError("Incorrect email or password.", code="invalid_credentials")

        payload = response.json()
        supabase_user = payload.get("user") or {}
        user = self.get_by_supabase_id(supabase_user.get("id", "")) or self.get_by_email(email)
        if not user:
            raise ForbiddenError("No Nexgile profile is linked to this Supabase account.")
        if not user.supabase_user_id:
            user.supabase_user_id = supabase_user.get("id")
            self.db.commit()
        return user

    def issue_token(self, user: User, remember: bool = False) -> dict[str, Any]:
        client = self.db.execute(select(Client).where(Client.user_id == user.id)).scalar_one_or_none()
        token, expires_at = create_access_token(
            subject=user.id,
            role=user.role,
            email=user.email,
            remember=remember,
            extra={"household_id": client.household_id if client else None, "name": user.full_name},
        )
        user.last_login_at = datetime.now(timezone.utc)
        self.db.commit()
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_at": expires_at,
            "user": self.profile(user),
        }

    def resolve_token(self, token: str) -> User:
        payload = decode_token(token)
        subject = payload.get("sub")
        if not subject:
            raise UnauthorizedError("Token is missing a subject.", code="invalid_token")

        user = self.get_by_id(subject) or self.get_by_supabase_id(subject)
        if not user and payload.get("email"):
            user = self.get_by_email(payload["email"])
        if not user:
            raise UnauthorizedError("No profile matches this session.", code="unknown_user")
        if not user.is_active:
            raise ForbiddenError("This account has been deactivated.")
        return user

    # -- profile ------------------------------------------------------
    def profile(self, user: User) -> dict[str, Any]:
        client = self.db.execute(select(Client).where(Client.user_id == user.id)).scalar_one_or_none()
        perms = permissions_for(user.role)
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "role_label": ROLE_LABELS.get(user.role, user.role),
            "title": user.title,
            "avatar_initials": user.avatar_initials or "".join(p[0] for p in user.full_name.split()[:2]).upper(),
            "permissions": sorted(str(p) for p in perms),
            "home_route": ROLE_HOME.get(user.role, "/dashboard"),
            "client_id": client.id if client else None,
            "household_id": client.household_id if client else None,
            "is_demo": user.is_demo,
            "last_login_at": user.last_login_at,
            "timezone": user.timezone,
        }

    def demo_accounts(self) -> list[dict[str, Any]]:
        """Labelled demo identities for the sign-in page (§6)."""
        if not settings.enable_demo_accounts:
            return []
        rows = (
            self.db.execute(select(User).where(User.is_demo.is_(True)).order_by(User.created_at))
            .scalars()
            .all()
        )
        return [
            {
                "label": user.demo_label or ROLE_LABELS.get(user.role, user.role),
                "email": user.email,
                "role": user.role,
                "role_label": ROLE_LABELS.get(user.role, user.role),
                "full_name": user.full_name,
                "title": user.title,
                "home_route": ROLE_HOME.get(user.role, "/dashboard"),
            }
            for user in rows
        ]

    def set_password(self, user: User, password: str) -> None:
        user.password_hash = hash_password(password)
        self.db.commit()

    def accessible_household_ids(self, user: User) -> list[str] | None:
        """None means every household; a list narrows the query.

        Clients see only their own household. Advisory and oversight roles see
        the book they are assigned to; admin and compliance see everything.
        """
        from app.models.identity import AdvisorAssignment

        if user.role in {Role.ADMIN, Role.COMPLIANCE, Role.OPERATIONS, Role.INVESTMENT_TEAM}:
            return None
        if user.role == Role.CLIENT:
            client = self.db.execute(select(Client).where(Client.user_id == user.id)).scalar_one_or_none()
            return [client.household_id] if client else []
        if user.role in {Role.ADVISOR, Role.TAX_SPECIALIST, Role.ESTATE_TRUST}:
            rows = (
                self.db.execute(
                    select(AdvisorAssignment.household_id).where(AdvisorAssignment.advisor_id == user.id)
                )
                .scalars()
                .all()
            )
            # An advisor with no explicit assignment still sees the full book in
            # this demonstration dataset rather than an empty workstation.
            return list(rows) if rows else None
        return []
