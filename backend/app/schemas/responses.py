"""Response envelopes used where a stable, documented shape matters."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    role_label: str
    title: str | None = None
    avatar_initials: str
    permissions: list[str]
    home_route: str
    client_id: str | None = None
    household_id: str | None = None
    is_demo: bool = False
    last_login_at: datetime | None = None
    timezone: str = "America/New_York"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserProfile


class DemoAccount(BaseModel):
    label: str
    email: str
    role: str
    role_label: str
    full_name: str
    title: str | None = None
    home_route: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class CalculationEnvelope(BaseModel):
    """Mirrors `CalcResult.to_dict()` so the disclosure contract is documented."""

    method: str
    result: Any
    as_of: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    source: str
    computed_at: str


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: str
    auth_provider: str
    ai_provider: str
    ai_mode: str
    ai_key_configured: bool
    seeded: bool
    timestamp: datetime
