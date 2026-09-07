"""Tax Center, estate, philanthropy and the document vault."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.core.constants import Permission
from app.core.deps import CurrentUser, DbSession, require, resolve_household_id
from app.schemas.requests import (
    BeneficiaryChangeRequest,
    DocumentClassifyRequest,
    DocumentDecisionRequest,
    DocumentShareRequest,
    HarvestCreateRequest,
)
from app.services.document_service import DocumentService
from app.services.estate_service import EstateService, PhilanthropyService
from app.services.portfolio_service import PortfolioService
from app.services.tax_service import TaxService

router = APIRouter(tags=["planning"])

TaxRead = Annotated[object, Depends(require(Permission.VIEW_TAX))]
TaxWrite = Annotated[object, Depends(require(Permission.MANAGE_TAX))]
EstateRead = Annotated[object, Depends(require(Permission.VIEW_ESTATE))]
DocsWrite = Annotated[object, Depends(require(Permission.MANAGE_DOCUMENTS))]


# --------------------------------------------------------------------- tax
@router.get("/tax")
def tax_overview(
    db: DbSession,
    user: CurrentUser,
    _: TaxRead,
    household_id: str | None = None,
    tax_year: int | None = Query(default=None, ge=2000, le=2100),
) -> dict:
    hid = resolve_household_id(db, user, household_id)
    as_of = PortfolioService(db).as_of(hid)
    return TaxService(db).overview(hid, as_of, tax_year)


@router.get("/tax/opportunities")
def tax_opportunities(
    db: DbSession, user: CurrentUser, _: TaxRead, household_id: str | None = None, tax_year: int | None = None
) -> list[dict]:
    hid = resolve_household_id(db, user, household_id)
    return TaxService(db).opportunities(hid, tax_year)


@router.get("/tax/harvests")
def list_harvests(
    db: DbSession, user: CurrentUser, _: TaxRead, household_id: str | None = None, status_filter: str | None = None
) -> list[dict]:
    hid = resolve_household_id(db, user, household_id)
    return TaxService(db).list_harvests(hid, status_filter)


@router.post("/tax/harvests", status_code=status.HTTP_201_CREATED)
def create_harvest(payload: HarvestCreateRequest, db: DbSession, user: TaxWrite) -> dict:
    hid = resolve_household_id(db, user, payload.household_id)
    as_of = PortfolioService(db).as_of(hid)
    return TaxService(db).create_harvest(hid, payload.tax_lot_id, user, as_of)


@router.post("/tax/harvests/{harvest_id}/execute")
def execute_harvest(harvest_id: str, db: DbSession, user: TaxWrite) -> dict:
    """Simulated execution only. No order reaches a custodian."""
    return TaxService(db).execute_harvest(harvest_id, user)


@router.get("/tax/wash-sale-check")
def wash_sale_check(
    security_id: str,
    db: DbSession,
    user: CurrentUser,
    _: TaxRead,
    household_id: str | None = None,
    sale_date: date | None = None,
) -> dict:
    hid = resolve_household_id(db, user, household_id)
    return TaxService(db).check_wash_sale(hid, security_id, sale_date)


@router.get("/tax/roth-conversion")
def roth_conversion(
    db: DbSession,
    user: CurrentUser,
    _: TaxRead,
    household_id: str | None = None,
    amount: float = Query(default=100_000.0, gt=0, le=10_000_000),
) -> dict:
    hid = resolve_household_id(db, user, household_id)
    as_of = PortfolioService(db).as_of(hid)
    return TaxService(db).roth_analysis(hid, as_of, amount)


# ------------------------------------------------------------------ estate
@router.get("/estate")
def estate_overview(db: DbSession, user: CurrentUser, _: EstateRead, household_id: str | None = None) -> dict:
    hid = resolve_household_id(db, user, household_id)
    as_of = PortfolioService(db).as_of(hid)
    return EstateService(db).overview(hid, as_of)


@router.post("/estate/beneficiaries/change", status_code=status.HTTP_201_CREATED)
def propose_beneficiary_change(
    payload: BeneficiaryChangeRequest,
    db: DbSession,
    user: Annotated[object, Depends(require(Permission.MANAGE_ESTATE, Permission.SUBMIT_APPROVAL))],
) -> dict:
    """Draft -> Review -> Approval -> Completed (§16)."""
    hid = resolve_household_id(db, user, payload.household_id)
    return EstateService(db).propose_beneficiary_change(
        hid, payload.beneficiary_id, payload.new_percentage, user, payload.note
    )


# ------------------------------------------------------------ philanthropy
@router.get("/philanthropy")
def philanthropy(db: DbSession, user: CurrentUser, _: EstateRead, household_id: str | None = None) -> dict:
    hid = resolve_household_id(db, user, household_id)
    as_of = PortfolioService(db).as_of(hid)
    return PhilanthropyService(db).overview(hid, as_of)


# --------------------------------------------------------------- documents
@router.get("/documents")
def list_documents(
    db: DbSession,
    user: CurrentUser,
    _: DocsWrite,
    household_id: str | None = None,
    search: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    review_status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=5, le=100),
) -> dict:
    hid = resolve_household_id(db, user, household_id)
    return DocumentService(db).list(
        hid,
        search=search,
        category=category,
        tag=tag,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: DbSession,
    user: DocsWrite,
    file: UploadFile = File(...),
    household_id: str | None = Form(default=None),
    category: str | None = Form(default=None),
    description: str | None = Form(default=None),
    expires_on: date | None = Form(default=None),
) -> dict:
    hid = resolve_household_id(db, user, household_id)
    content = await file.read()
    return DocumentService(db).upload(
        household_id=hid,
        filename=file.filename or "upload",
        content=content,
        actor=user,
        category=category,
        description=description,
        expires_on=expires_on,
        mime_type=file.content_type or "application/octet-stream",
    )


@router.post("/documents/classify")
def classify_document(payload: DocumentClassifyRequest, db: DbSession, user: DocsWrite) -> dict:
    """Suggested filing from the deterministic rules engine. Never auto-applied."""
    return DocumentService(db).classify(payload.filename, {"description": payload.description})


@router.get("/documents/{document_id}")
def document_detail(document_id: str, db: DbSession, user: CurrentUser, _: DocsWrite) -> dict:
    service = DocumentService(db)
    document = service.get(document_id)
    resolve_household_id(db, user, document.household_id)
    return service.detail(document_id)


@router.post("/documents/{document_id}/classification")
def resolve_classification(
    document_id: str, payload: DocumentDecisionRequest, db: DbSession, user: DocsWrite
) -> dict:
    service = DocumentService(db)
    document = service.get(document_id)
    resolve_household_id(db, user, document.household_id)
    return service.resolve_classification(
        document_id,
        decision=payload.decision,
        category=payload.category,
        document_type=payload.document_type,
        actor=user,
    )


@router.post("/documents/{document_id}/share", status_code=status.HTTP_201_CREATED)
def share_document(document_id: str, payload: DocumentShareRequest, db: DbSession, user: DocsWrite) -> dict:
    service = DocumentService(db)
    document = service.get(document_id)
    resolve_household_id(db, user, document.household_id)
    return service.share(
        document_id,
        shared_with_label=payload.shared_with_label,
        permission=payload.permission,
        actor=user,
        days_valid=payload.days_valid,
    )


@router.get("/documents/{document_id}/download")
def download_document(document_id: str, db: DbSession, user: CurrentUser, _: DocsWrite) -> Response:
    service = DocumentService(db)
    document = service.get(document_id)
    resolve_household_id(db, user, document.household_id)
    content, mime_type, name = service.read_file(document_id)
    return Response(
        content=content,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
