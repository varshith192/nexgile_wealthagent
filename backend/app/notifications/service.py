"""Notification centre (§28).

Alerts are generated from the same verified figures that drive the dashboard,
so what a user is told matches what they see.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.identity import User
from app.models.workflow import Alert

CATEGORY_LABELS = {
    "portfolio": "Portfolio",
    "goal": "Goals",
    "tax": "Tax",
    "estate": "Estate",
    "document": "Documents",
    "meeting": "Meetings",
    "approval": "Approvals",
    "plan": "Plan",
    "service": "Service",
    "compliance": "Compliance",
}


class NotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: str | None,
        category: str,
        title: str,
        body: str,
        severity: str = "info",
        household_id: str | None = None,
        plan_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action_url: str | None = None,
        due_date: date | None = None,
        commit: bool = True,
    ) -> Alert:
        alert = Alert(
            user_id=user_id,
            household_id=household_id,
            plan_id=plan_id,
            category=category,
            severity=severity,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
            due_date=due_date,
        )
        self.db.add(alert)
        if commit:
            self.db.commit()
            self.db.refresh(alert)
        else:
            self.db.flush()
        return alert

    def list(
        self,
        user: User,
        *,
        unread_only: bool = False,
        category: str | None = None,
        limit: int = 50,
        household_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        stmt = select(Alert).where(Alert.dismissed_at.is_(None))
        if household_ids is not None:
            stmt = stmt.where((Alert.user_id == user.id) | (Alert.household_id.in_(list(household_ids))))
        else:
            stmt = stmt.where((Alert.user_id == user.id) | (Alert.user_id.is_(None)))
        if unread_only:
            stmt = stmt.where(Alert.read_at.is_(None))
        if category:
            stmt = stmt.where(Alert.category == category)

        rows = list(self.db.execute(stmt.order_by(Alert.created_at.desc()).limit(limit)).scalars().all())
        by_category: dict[str, int] = {}
        for row in rows:
            by_category[row.category] = by_category.get(row.category, 0) + 1

        return {
            "notifications": [self.serialise(a) for a in rows],
            "unread_count": sum(1 for a in rows if a.read_at is None),
            "total": len(rows),
            "by_category": [
                {"key": key, "label": CATEGORY_LABELS.get(key, key.title()), "count": count}
                for key, count in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
            ],
        }

    def serialise(self, alert: Alert) -> dict[str, Any]:
        return {
            "id": alert.id,
            "category": alert.category,
            "category_label": CATEGORY_LABELS.get(alert.category, alert.category.title()),
            "severity": alert.severity,
            "title": alert.title,
            "body": alert.body,
            "entity_type": alert.entity_type,
            "entity_id": alert.entity_id,
            "action_url": alert.action_url,
            "due_date": alert.due_date.isoformat() if alert.due_date else None,
            "is_read": alert.read_at is not None,
            "created_at": alert.created_at.isoformat(),
        }

    def mark_read(self, alert_id: str, user: User) -> dict[str, Any]:
        alert = self.db.get(Alert, alert_id)
        if not alert:
            raise NotFoundError("Notification not found.")
        alert.read_at = datetime.now(timezone.utc)
        self.db.commit()
        return self.serialise(alert)

    def mark_all_read(self, user: User) -> int:
        rows = self.db.execute(
            select(Alert).where(Alert.user_id == user.id, Alert.read_at.is_(None))
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for row in rows:
            row.read_at = now
        self.db.commit()
        return len(rows)

    def dismiss(self, alert_id: str, user: User) -> None:
        alert = self.db.get(Alert, alert_id)
        if not alert:
            raise NotFoundError("Notification not found.")
        alert.dismissed_at = datetime.now(timezone.utc)
        self.db.commit()

    # -- generation ---------------------------------------------------
    def sync_from_context(self, *, household_id: str, user_id: str | None, insights: list[dict[str, Any]]) -> int:
        """Turn current high-severity insights into alerts, without duplicating."""
        existing = {
            (a.entity_type, a.title)
            for a in self.db.execute(
                select(Alert).where(Alert.household_id == household_id, Alert.dismissed_at.is_(None))
            ).scalars().all()
        }
        created = 0
        for insight in insights:
            if insight.get("severity") not in {"high", "critical", "medium"}:
                continue
            key = (insight.get("entity_type"), insight.get("title"))
            if key in existing:
                continue
            self.create(
                user_id=user_id,
                household_id=household_id,
                category=insight.get("category", "portfolio"),
                severity=insight.get("severity", "info"),
                title=insight["title"],
                body=insight["summary"],
                entity_type=insight.get("entity_type"),
                entity_id=insight.get("entity_id"),
                action_url=insight.get("action_url"),
                commit=False,
            )
            created += 1
        if created:
            self.db.commit()
        return created
