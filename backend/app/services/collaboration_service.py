"""Secure messaging (§26) and meetings (§27)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, AuditService
from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.models.collab import ActionItem, Meeting, Message, MessageThread
from app.models.identity import User


class MessagingService:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)

    def threads(self, household_id: str, *, search: str | None = None) -> list[dict[str, Any]]:
        stmt = select(MessageThread).where(MessageThread.household_id == household_id)
        if search:
            needle = f"%{search.lower()}%"
            stmt = stmt.where(MessageThread.subject.ilike(needle))
        rows = self.db.execute(stmt.order_by(MessageThread.last_message_at.desc())).scalars().all()
        return [self._thread_summary(t) for t in rows]

    def _thread_summary(self, thread: MessageThread) -> dict[str, Any]:
        messages = thread.messages
        last = messages[-1] if messages else None
        return {
            "id": thread.id,
            "subject": thread.subject,
            "topic": thread.topic,
            "status": thread.status,
            "message_count": len(messages),
            "unread_count": sum(1 for m in messages if m.read_at is None and m.sender_role != "client"),
            "last_message_at": thread.last_message_at.isoformat() if thread.last_message_at else None,
            "last_message_preview": (last.body[:140] + "…") if last and len(last.body) > 140 else (last.body if last else None),
            "last_sender": last.sender_name if last else None,
        }

    def thread(self, thread_id: str, household_id: str | None = None) -> dict[str, Any]:
        thread = self.db.get(MessageThread, thread_id)
        if not thread:
            raise NotFoundError("Conversation not found.")
        if household_id and thread.household_id != household_id:
            raise ForbiddenError("This conversation belongs to another household.")

        items = self.db.execute(select(ActionItem).where(ActionItem.thread_id == thread.id)).scalars().all()

        return {
            **self._thread_summary(thread),
            "messages": [
                {
                    "id": m.id,
                    "sender_name": m.sender_name,
                    "sender_role": m.sender_role,
                    "body": m.body,
                    "sent_at": m.sent_at.isoformat(),
                    "read_at": m.read_at.isoformat() if m.read_at else None,
                    "attachment_name": m.attachment_name,
                    "attachment_document_id": m.attachment_document_id,
                }
                for m in thread.messages
            ],
            "action_items": [
                {
                    "id": a.id,
                    "title": a.title,
                    "owner": a.owner,
                    "status": a.status,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                }
                for a in items
            ],
        }

    def send(
        self, thread_id: str, body: str, actor: User, *, attachment_document_id: str | None = None
    ) -> dict[str, Any]:
        if not body or not body.strip():
            raise ValidationError("A message cannot be empty.")
        thread = self.db.get(MessageThread, thread_id)
        if not thread:
            raise NotFoundError("Conversation not found.")

        now = datetime.now(timezone.utc)
        message = Message(
            thread_id=thread.id,
            sender_id=actor.id,
            sender_name=actor.full_name,
            sender_role=actor.role,
            body=body.strip(),
            sent_at=now,
            attachment_document_id=attachment_document_id,
        )
        self.db.add(message)
        thread.last_message_at = now
        thread.status = "open"

        self.audit.record(
            action=AuditAction.CREATE,
            entity_type="message",
            entity_id=message.id,
            entity_label=thread.subject,
            actor=actor,
            household_id=thread.household_id,
            summary=f"Message sent in '{thread.subject}'",
            commit=False,
        )
        self.db.commit()
        self.db.refresh(message)
        return {
            "id": message.id,
            "sender_name": message.sender_name,
            "sender_role": message.sender_role,
            "body": message.body,
            "sent_at": message.sent_at.isoformat(),
        }

    def start_thread(self, household_id: str, subject: str, body: str, actor: User, topic: str = "general") -> dict[str, Any]:
        if not subject.strip():
            raise ValidationError("A subject is required.")
        thread = MessageThread(household_id=household_id, subject=subject.strip(), topic=topic, status="open")
        self.db.add(thread)
        self.db.flush()
        self.send(thread.id, body, actor)
        return self.thread(thread.id)

    def mark_read(self, thread_id: str, actor: User) -> int:
        thread = self.db.get(MessageThread, thread_id)
        if not thread:
            raise NotFoundError("Conversation not found.")
        now = datetime.now(timezone.utc)
        count = 0
        for message in thread.messages:
            if message.read_at is None and message.sender_id != actor.id:
                message.read_at = now
                count += 1
        self.db.commit()
        return count


class MeetingService:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)

    def list(self, household_id: str) -> dict[str, Any]:
        rows = self.db.execute(
            select(Meeting).where(Meeting.household_id == household_id).order_by(Meeting.starts_at.desc())
        ).scalars().all()
        now = datetime.now(timezone.utc)

        def normalise(dt: datetime) -> datetime:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        upcoming = [m for m in rows if normalise(m.starts_at) >= now and m.status == "scheduled"]
        past = [m for m in rows if normalise(m.starts_at) < now or m.status != "scheduled"]

        return {
            "upcoming": [self.serialise(m) for m in sorted(upcoming, key=lambda m: m.starts_at)],
            "past": [self.serialise(m) for m in past],
            "next_meeting": self.serialise(sorted(upcoming, key=lambda m: m.starts_at)[0]) if upcoming else None,
        }

    def serialise(self, meeting: Meeting) -> dict[str, Any]:
        advisor = self.db.get(User, meeting.advisor_id) if meeting.advisor_id else None
        items = self.db.execute(select(ActionItem).where(ActionItem.meeting_id == meeting.id)).scalars().all()
        return {
            "id": meeting.id,
            "title": meeting.title,
            "meeting_type": meeting.meeting_type,
            "starts_at": meeting.starts_at.isoformat(),
            "duration_minutes": meeting.duration_minutes,
            "location": meeting.location,
            "status": meeting.status,
            "agenda": meeting.agenda or [],
            "notes": meeting.notes,
            "summary": meeting.summary,
            "attendees": meeting.attendees or [],
            "advisor": advisor.full_name if advisor else None,
            "action_items": [
                {
                    "id": a.id,
                    "title": a.title,
                    "owner": a.owner,
                    "status": a.status,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                    "notes": a.notes,
                }
                for a in items
            ],
        }

    def detail(self, meeting_id: str, household_id: str | None = None) -> dict[str, Any]:
        meeting = self.db.get(Meeting, meeting_id)
        if not meeting:
            raise NotFoundError("Meeting not found.")
        if household_id and meeting.household_id != household_id:
            raise ForbiddenError("This meeting belongs to another household.")
        return self.serialise(meeting)

    def complete_action_item(self, item_id: str, actor: User) -> dict[str, Any]:
        item = self.db.get(ActionItem, item_id)
        if not item:
            raise NotFoundError("Action item not found.")
        item.status = "complete"
        self.audit.record(
            action=AuditAction.UPDATE,
            entity_type="action_item",
            entity_id=item.id,
            entity_label=item.title,
            actor=actor,
            household_id=item.household_id,
            summary=f"Action item completed: {item.title}",
            after={"status": "complete"},
            commit=False,
        )
        self.db.commit()
        return {"id": item.id, "status": item.status}
