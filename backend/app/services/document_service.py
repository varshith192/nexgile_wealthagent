"""Document vault (§18).

Uploads are classified by the mock intelligence service. The suggestion is
always presented as a suggestion — accept, edit or reject — and the product
never claims an external model processed the file.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.service import AIService, get_ai_service
from app.audit.service import AuditAction, AuditService
from app.core.config import settings
from app.core.constants import DocumentCategory, EntityType
from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.models.collab import Document, DocumentRequest, DocumentShare, DocumentVersion
from app.models.identity import User

EXPIRY_WINDOW_DAYS = 90
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


class DocumentService:
    def __init__(self, db: Session, audit: AuditService | None = None, ai: AIService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.ai = ai or get_ai_service()

    # -- storage ------------------------------------------------------
    def _storage_dir(self, household_id: str) -> Path:
        path = Path(settings.local_storage_dir) / household_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _validate_upload(self, filename: str, size_bytes: int) -> str:
        if not filename or filename.strip() in {".", ".."}:
            raise ValidationError("A file name is required.")
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in settings.upload_extension_set:
            raise ValidationError(
                f"Files of type .{extension or 'unknown'} are not accepted.",
                details={"allowed": sorted(settings.upload_extension_set)},
            )
        if size_bytes > settings.max_upload_bytes:
            raise ValidationError(
                f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)}MB limit.",
                details={"size_bytes": size_bytes},
            )
        return extension

    def _safe_filename(self, filename: str) -> str:
        """Strip any path component; never trust a client-supplied name."""
        return SAFE_NAME.sub("_", Path(filename).name)[:200]

    # -- reads --------------------------------------------------------
    def list(
        self,
        household_id: str,
        *,
        search: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        review_status: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        stmt = select(Document).where(Document.household_id == household_id)
        if category:
            stmt = stmt.where(Document.category == category)
        if review_status:
            stmt = stmt.where(Document.review_status == review_status)
        if search:
            needle = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(Document.name.ilike(needle), Document.document_type.ilike(needle), Document.description.ilike(needle))
            )

        rows = list(self.db.execute(stmt.order_by(Document.created_at.desc())).scalars().all())
        if tag:
            rows = [r for r in rows if tag in (r.tags or [])]

        total = len(rows)
        start = max(page - 1, 0) * page_size
        page_rows = rows[start : start + page_size]

        counts: dict[str, int] = {}
        for row in rows:
            counts[row.category] = counts.get(row.category, 0) + 1

        today = date.today()
        return {
            "documents": [self.serialise(d) for d in page_rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max((total + page_size - 1) // page_size, 1),
            "categories": [
                {"key": str(c), "label": str(c).title(), "count": counts.get(str(c), 0)} for c in DocumentCategory
            ],
            "tags": sorted({t for r in rows for t in (r.tags or [])}),
            "summary": {
                "total": total,
                "pending_review": sum(1 for r in rows if r.review_status == "pending_review"),
                "expiring_soon": sum(
                    1 for r in rows if r.expires_on and today <= r.expires_on <= today + timedelta(days=EXPIRY_WINDOW_DAYS)
                ),
                "expired": sum(1 for r in rows if r.expires_on and r.expires_on < today),
            },
            "requests": self.open_requests(household_id),
        }

    def serialise(self, document: Document) -> dict[str, Any]:
        today = date.today()
        uploader = self.db.get(User, document.uploaded_by_id) if document.uploaded_by_id else None
        return {
            "id": document.id,
            "name": document.name,
            "original_filename": document.original_filename,
            "category": document.category,
            "document_type": document.document_type,
            "tax_year": document.tax_year,
            "tags": document.tags or [],
            "description": document.description,
            "mime_type": document.mime_type,
            "size_bytes": document.size_bytes,
            "current_version": document.current_version,
            "review_status": document.review_status,
            "uploaded_by": uploader.full_name if uploader else "System",
            "uploaded_at": (document.uploaded_at or document.created_at).isoformat(),
            "expires_on": document.expires_on.isoformat() if document.expires_on else None,
            "retention_until": document.retention_until.isoformat() if document.retention_until else None,
            "is_confidential": document.is_confidential,
            "is_expired": bool(document.expires_on and document.expires_on < today),
            "expires_soon": bool(
                document.expires_on and today <= document.expires_on <= today + timedelta(days=EXPIRY_WINDOW_DAYS)
            ),
            "storage_backend": document.storage_backend,
            "classification": {
                "suggested_category": document.suggested_category,
                "suggested_document_type": document.suggested_document_type,
                "confidence": document.classification_confidence,
                "source": document.classification_source,
                "reasons": document.classification_reasons or [],
                "accepted": document.classification_accepted,
                "note": "Suggested by the platform's deterministic rules engine. Review before filing.",
            }
            if document.suggested_category
            else None,
        }

    def get(self, document_id: str, household_id: str | None = None) -> Document:
        document = self.db.get(Document, document_id)
        if not document:
            raise NotFoundError("Document not found.")
        if household_id and document.household_id != household_id:
            raise ForbiddenError("This document belongs to another household.")
        return document

    def detail(self, document_id: str, household_id: str | None = None) -> dict[str, Any]:
        document = self.get(document_id, household_id)
        versions = self.db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version.desc())
        ).scalars().all()
        shares = self.db.execute(
            select(DocumentShare).where(DocumentShare.document_id == document.id, DocumentShare.revoked.is_(False))
        ).scalars().all()

        return {
            **self.serialise(document),
            "versions": [
                {
                    "id": v.id,
                    "version": v.version,
                    "size_bytes": v.size_bytes,
                    "checksum": v.checksum,
                    "change_note": v.change_note,
                    "uploaded_at": v.created_at.isoformat(),
                }
                for v in versions
            ],
            "shares": [
                {
                    "id": s.id,
                    "shared_with": s.shared_with_label,
                    "permission": s.permission,
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                }
                for s in shares
            ],
        }

    def expiring_soon(self, household_id: str, days: int = EXPIRY_WINDOW_DAYS) -> list[dict[str, Any]]:
        today = date.today()
        rows = self.db.execute(
            select(Document).where(
                Document.household_id == household_id,
                Document.expires_on.is_not(None),
                Document.expires_on <= today + timedelta(days=days),
            )
        ).scalars().all()
        return [
            {"id": d.id, "name": d.name, "category": d.category, "expires_on": d.expires_on.isoformat()}
            for d in sorted(rows, key=lambda d: d.expires_on)
        ]

    def open_requests(self, household_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(DocumentRequest).where(
                DocumentRequest.household_id == household_id, DocumentRequest.status == "open"
            )
        ).scalars().all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "category": r.category,
                "reason": r.reason,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "status": r.status,
            }
            for r in rows
        ]

    # -- classification -----------------------------------------------
    def classify(self, filename: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.ai.classify_document(filename, metadata)
        return result.model_dump()

    # -- writes -------------------------------------------------------
    def upload(
        self,
        *,
        household_id: str,
        filename: str,
        content: BinaryIO | bytes,
        actor: User,
        category: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        expires_on: date | None = None,
        mime_type: str = "application/octet-stream",
        account_id: str | None = None,
    ) -> dict[str, Any]:
        raw = content if isinstance(content, bytes) else content.read()
        self._validate_upload(filename, len(raw))
        safe_name = self._safe_filename(filename)

        classification = self.ai.classify_document(filename, {"description": description})
        resolved_category = category or classification.suggested_category

        storage_key = None
        if settings.storage_backend == "local":
            target = self._storage_dir(household_id) / f"{uuid.uuid4().hex}_{safe_name}"
            target.write_bytes(raw)
            storage_key = str(target.relative_to(Path(settings.local_storage_dir)))
        else:  # pragma: no cover - Supabase Storage path
            storage_key = f"{household_id}/{uuid.uuid4().hex}_{safe_name}"

        document = Document(
            household_id=household_id,
            uploaded_by_id=actor.id,
            account_id=account_id,
            name=safe_name,
            original_filename=filename,
            category=resolved_category,
            document_type=classification.suggested_document_type,
            tax_year=classification.detected_year,
            tags=list({*(tags or []), *classification.suggested_tags}),
            description=description,
            storage_key=storage_key,
            storage_backend=settings.storage_backend,
            mime_type=mime_type,
            size_bytes=len(raw),
            current_version=1,
            review_status="pending_review",
            suggested_category=classification.suggested_category,
            suggested_document_type=classification.suggested_document_type,
            classification_confidence=classification.confidence,
            classification_source=classification.source,
            classification_reasons=classification.reasons,
            classification_accepted=None,
            expires_on=expires_on,
            retention_until=date.today() + timedelta(days=365 * 7),
            uploaded_at=datetime.now(timezone.utc),
        )
        self.db.add(document)
        self.db.flush()

        self.db.add(
            DocumentVersion(
                document_id=document.id,
                version=1,
                storage_key=storage_key,
                size_bytes=len(raw),
                checksum=hashlib.sha256(raw).hexdigest()[:64],
                uploaded_by_id=actor.id,
                change_note="Initial upload",
            )
        )

        self.audit.record(
            action=AuditAction.DOCUMENT_UPLOAD,
            entity_type=EntityType.DOCUMENT,
            entity_id=document.id,
            entity_label=document.name,
            actor=actor,
            household_id=household_id,
            summary=f"Uploaded {document.name} ({len(raw)} bytes)",
            after={
                "category": document.category,
                "suggested_category": classification.suggested_category,
                "confidence": classification.confidence,
            },
            commit=False,
        )
        self.db.commit()
        self.db.refresh(document)
        return self.serialise(document)

    def resolve_classification(
        self, document_id: str, *, decision: str, category: str | None, actor: User, document_type: str | None = None
    ) -> dict[str, Any]:
        """Accept, edit or reject the suggested filing (§18)."""
        if decision not in {"accept", "edit", "reject"}:
            raise ValidationError("Decision must be accept, edit or reject.")

        document = self.get(document_id)
        before = {"category": document.category, "review_status": document.review_status}

        if decision == "accept":
            document.category = document.suggested_category or document.category
            document.document_type = document.suggested_document_type or document.document_type
            document.classification_accepted = True
        elif decision == "edit":
            if not category:
                raise ValidationError("A category is required when editing the suggestion.")
            document.category = category
            if document_type:
                document.document_type = document_type
            document.classification_accepted = False
        else:
            document.classification_accepted = False
            document.category = category or DocumentCategory.OTHER

        document.review_status = "reviewed"

        self.audit.record(
            action=AuditAction.DOCUMENT_CLASSIFY,
            entity_type=EntityType.DOCUMENT,
            entity_id=document.id,
            entity_label=document.name,
            actor=actor,
            household_id=document.household_id,
            summary=f"Classification {decision}ed for {document.name}",
            before=before,
            after={"category": document.category, "review_status": document.review_status, "decision": decision},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(document)
        return self.serialise(document)

    def share(
        self, document_id: str, *, shared_with_label: str, permission: str, actor: User, days_valid: int = 30
    ) -> dict[str, Any]:
        document = self.get(document_id)
        if permission not in {"view", "download"}:
            raise ValidationError("Permission must be view or download.")

        share = DocumentShare(
            document_id=document.id,
            shared_with_label=shared_with_label,
            permission=permission,
            expires_at=datetime.now(timezone.utc) + timedelta(days=days_valid),
        )
        self.db.add(share)

        self.audit.record(
            action=AuditAction.DOCUMENT_SHARE,
            entity_type=EntityType.DOCUMENT,
            entity_id=document.id,
            entity_label=document.name,
            actor=actor,
            household_id=document.household_id,
            summary=f"Shared with {shared_with_label} ({permission})",
            after={"shared_with": shared_with_label, "permission": permission},
            commit=False,
        )
        self.db.commit()
        return {"id": share.id, "shared_with": shared_with_label, "permission": permission}

    def read_file(self, document_id: str, household_id: str | None = None) -> tuple[bytes, str, str]:
        document = self.get(document_id, household_id)
        if document.storage_backend != "local" or not document.storage_key:
            raise NotFoundError("This document is stored externally and has no local copy.")
        path = Path(settings.local_storage_dir) / document.storage_key
        # Guard against a storage key escaping the storage root.
        root = Path(settings.local_storage_dir).resolve()
        if not path.resolve().is_relative_to(root) or not path.exists():
            raise NotFoundError("The stored file is no longer available.")
        return path.read_bytes(), document.mime_type, document.name
