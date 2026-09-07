"""Nexgile WealthAgent API.

FastAPI application factory, error handling and the health endpoint that tells
you exactly which adapters are live.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.ai.service import get_ai_service
from app.api.router import api_router
from app.core.config import settings
from app.core.errors import AppError
from app.db.session import SessionLocal, create_all, engine
from app.schemas.responses import HealthResponse

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("nexgile")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SQLite (local/CI) is created on the fly. Postgres schema is owned by
    # supabase/schema.sql or Alembic, so we never issue DDL against it here.
    if settings.is_sqlite:
        create_all()
    ai = get_ai_service()
    logger.info(
        "Nexgile WealthAgent API starting | env=%s | db=%s | auth=%s | ai=%s (%s)",
        settings.environment,
        "sqlite" if settings.is_sqlite else "postgres",
        settings.auth_provider,
        ai.info.name,
        ai.info.mode,
    )
    yield
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Unified wealth-management platform API. Financial figures come from the deterministic "
        "calculation engine; the AI layer only explains them."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "The request could not be processed as submitted.",
                "details": [
                    {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
                    for err in exc.errors()
                ],
            }
        },
    )


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"error": {"code": "database_unavailable", "message": "The data service is temporarily unavailable."}},
    )


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Something went wrong. Please try again."}},
    )


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": settings.api_prefix,
        "status": "ok",
    }


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> dict:
    from app.models.identity import User

    database = "unavailable"
    seeded = False
    try:
        with SessionLocal() as db:
            count = db.execute(select(func.count()).select_from(User)).scalar_one()
            database = "sqlite" if settings.is_sqlite else "postgres"
            seeded = count > 0
    except SQLAlchemyError as exc:  # pragma: no cover - depends on environment
        logger.warning("Health check could not reach the database: %s", exc)

    ai = get_ai_service().info
    return {
        "status": "ok" if database != "unavailable" else "degraded",
        "version": settings.app_version,
        "environment": settings.environment,
        "database": database,
        "auth_provider": settings.auth_provider,
        "ai_provider": ai.name,
        "ai_mode": ai.mode,
        # An absent AI key is expected, not an error (§1).
        "ai_key_configured": bool(settings.ai_api_key),
        "seeded": seeded,
        "timestamp": datetime.now(timezone.utc),
    }


app.include_router(api_router, prefix=settings.api_prefix)
