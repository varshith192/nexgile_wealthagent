"""Document vault, secure messaging and meetings."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class Document(BaseModel):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_household_category", "household_id", "category"),
        Index("ix_documents_status", "review_status"),
    )

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(32), index=True)
    document_type: Mapped[str | None] = mapped_column(String(64))
    tax_year: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[list] = mapped_column(default=list)
    description: Mapped[str | None] = mapped_column(Text())
    storage_key: Mapped[str | None] = mapped_column(String(512))
    storage_backend: Mapped[str] = mapped_column(String(24), default="local")
    mime_type: Mapped[str] = mapped_column(String(120), default="application/pdf")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    review_status: Mapped[str] = mapped_column(String(24), default="pending_review")
    # Deterministic classification produced by the mock intelligence service.
    suggested_category: Mapped[str | None] = mapped_column(String(32))
    suggested_document_type: Mapped[str | None] = mapped_column(String(64))
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classification_source: Mapped[str] = mapped_column(String(48), default="mock_rules")
    classification_reasons: Mapped[list] = mapped_column(default=list)
    classification_accepted: Mapped[bool | None] = mapped_column(Boolean)
    expires_on: Mapped[date | None] = mapped_column(Date())
    retention_until: Mapped[date | None] = mapped_column(Date())
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    shares: Mapped[list["DocumentShare"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(BaseModel):
    __tablename__ = "document_versions"
    __table_args__ = (Index("ix_docversion_document", "document_id", "version"),)

    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    storage_key: Mapped[str | None] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64))
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    change_note: Mapped[str | None] = mapped_column(String(255))

    document: Mapped[Document] = relationship(back_populates="versions")


class DocumentShare(BaseModel):
    __tablename__ = "document_shares"

    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    shared_with_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    shared_with_label: Mapped[str] = mapped_column(String(160))
    permission: Mapped[str] = mapped_column(String(16), default="view")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped[Document] = relationship(back_populates="shares")


class DocumentRequest(BaseModel):
    __tablename__ = "document_requests"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    requested_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32), default="tax")
    reason: Mapped[str | None] = mapped_column(Text())
    due_date: Mapped[date | None] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(24), default="open")
    fulfilled_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))


class MessageThread(BaseModel):
    __tablename__ = "message_threads"

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(48), default="general")
    status: Mapped[str] = mapped_column(String(24), default="open")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="Message.sent_at"
    )


class Message(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_thread_sent", "thread_id", "sent_at"),)

    thread_id: Mapped[str] = mapped_column(ForeignKey("message_threads.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    sender_name: Mapped[str] = mapped_column(String(160))
    sender_role: Mapped[str] = mapped_column(String(48), default="advisor")
    body: Mapped[str] = mapped_column(Text())
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attachment_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    attachment_name: Mapped[str | None] = mapped_column(String(255))

    thread: Mapped[MessageThread] = relationship(back_populates="messages")


class Meeting(BaseModel):
    __tablename__ = "meetings"
    __table_args__ = (Index("ix_meetings_household_start", "household_id", "starts_at"),)

    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    advisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    meeting_type: Mapped[str] = mapped_column(String(48), default="review")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    location: Mapped[str] = mapped_column(String(120), default="Video conference")
    status: Mapped[str] = mapped_column(String(24), default="scheduled")
    agenda: Mapped[list] = mapped_column(default=list)
    notes: Mapped[str | None] = mapped_column(Text())
    summary: Mapped[str | None] = mapped_column(Text())
    attendees: Mapped[list] = mapped_column(default=list)

    action_items: Mapped[list["ActionItem"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")


class ActionItem(BaseModel):
    __tablename__ = "action_items"

    meeting_id: Mapped[str | None] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    household_id: Mapped[str | None] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    thread_id: Mapped[str | None] = mapped_column(ForeignKey("message_threads.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(120))
    due_date: Mapped[date | None] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(24), default="open")
    notes: Mapped[str | None] = mapped_column(Text())

    meeting: Mapped[Meeting | None] = relationship(back_populates="action_items")
