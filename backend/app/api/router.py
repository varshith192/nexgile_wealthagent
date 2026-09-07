"""Aggregates every route module under the configured API prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import advisor, auth, client, institutional, planning, platform, wealthagent

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(client.router)
api_router.include_router(planning.router)
api_router.include_router(wealthagent.router)
api_router.include_router(advisor.router)
api_router.include_router(institutional.router)
api_router.include_router(platform.router)

__all__ = ["api_router"]
