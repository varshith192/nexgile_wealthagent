"""Global search (§36).

Results are always scoped to what the caller is allowed to see, and the scope
is applied in the query rather than filtered out afterwards.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import Role
from app.models.collab import Document, Meeting, MessageThread
from app.models.identity import Client, Household, User
from app.models.institutional import Participant, Plan
from app.models.planning import Goal, Recommendation, Task
from app.models.wealth import Account, Holding, Security
from app.models.workflow import Approval, Rebalance, Report, SavedView, SearchHistory

CATEGORIES = [
    "clients",
    "households",
    "accounts",
    "holdings",
    "goals",
    "plans",
    "participants",
    "documents",
    "messages",
    "tasks",
    "reports",
    "trades",
    "approvals",
]

MAX_PER_CATEGORY = 6


class SearchService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search(
        self,
        query: str,
        user: User,
        household_ids: Sequence[str] | None,
        *,
        categories: Sequence[str] | None = None,
        limit_per_category: int = MAX_PER_CATEGORY,
    ) -> dict[str, Any]:
        term = (query or "").strip()
        if len(term) < 2:
            return {"query": term, "groups": [], "total": 0, "message": "Enter at least two characters."}

        needle = f"%{term.lower()}%"
        wanted = set(categories or CATEGORIES)
        groups: list[dict[str, Any]] = []

        def scoped(stmt, column):
            return stmt.where(column.in_(list(household_ids))) if household_ids is not None else stmt

        def add(category: str, label: str, rows: list[dict[str, Any]]) -> None:
            if rows:
                groups.append({"category": category, "label": label, "count": len(rows), "results": rows[:limit_per_category]})

        if "households" in wanted or "clients" in wanted:
            stmt = select(Household).where(Household.name.ilike(needle))
            if household_ids is not None:
                stmt = stmt.where(Household.id.in_(list(household_ids)))
            add(
                "households",
                "Households",
                [
                    {
                        "id": h.id,
                        "title": h.name,
                        "subtitle": f"{h.segment.replace('_', ' ').title()} · {h.city or ''}".strip(" ·"),
                        "route": f"/advisor/clients/{h.id}" if user.role != Role.CLIENT else "/dashboard",
                    }
                    for h in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if "clients" in wanted:
            stmt = scoped(select(Client).where(Client.full_name.ilike(needle)), Client.household_id)
            add(
                "clients",
                "Clients",
                [
                    {
                        "id": c.id,
                        "title": c.full_name,
                        "subtitle": f"{c.segment.replace('_', ' ').title()} · {c.status}",
                        "route": f"/advisor/clients/{c.household_id}" if user.role != Role.CLIENT else "/dashboard",
                    }
                    for c in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if "accounts" in wanted:
            stmt = scoped(select(Account).where(Account.name.ilike(needle)), Account.household_id)
            add(
                "accounts",
                "Accounts",
                [
                    {
                        "id": a.id,
                        "title": a.name,
                        "subtitle": f"{a.account_type.replace('_', ' ').title()} · {a.account_number_masked} · ${a.balance:,.0f}",
                        "route": f"/accounts/{a.id}",
                    }
                    for a in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if "holdings" in wanted:
            stmt = (
                select(Holding, Security, Account)
                .join(Security, Holding.security_id == Security.id)
                .join(Account, Holding.account_id == Account.id)
                .where((Security.symbol.ilike(needle)) | (Security.name.ilike(needle)))
            )
            if household_ids is not None:
                stmt = stmt.where(Account.household_id.in_(list(household_ids)))
            add(
                "holdings",
                "Holdings",
                [
                    {
                        "id": h.id,
                        "title": f"{s.symbol} — {s.name}",
                        "subtitle": f"{a.name} · {h.quantity:,.2f} shares · ${h.quantity * s.last_price:,.0f}",
                        "route": "/holdings",
                    }
                    for h, s, a in self.db.execute(stmt.limit(20)).all()
                ],
            )

        if "goals" in wanted:
            stmt = scoped(select(Goal).where(Goal.name.ilike(needle)), Goal.household_id)
            add(
                "goals",
                "Goals",
                [
                    {
                        "id": g.id,
                        "title": g.name,
                        "subtitle": f"{g.goal_type.replace('_', ' ').title()} · target ${g.target_amount:,.0f} by {g.target_date.year}",
                        "route": f"/goals/{g.id}",
                    }
                    for g in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if "documents" in wanted:
            stmt = scoped(
                select(Document).where((Document.name.ilike(needle)) | (Document.document_type.ilike(needle))),
                Document.household_id,
            )
            add(
                "documents",
                "Documents",
                [
                    {
                        "id": d.id,
                        "title": d.name,
                        "subtitle": f"{d.category.title()} · {d.document_type or 'Document'}",
                        "route": "/documents",
                    }
                    for d in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if "messages" in wanted:
            stmt = scoped(select(MessageThread).where(MessageThread.subject.ilike(needle)), MessageThread.household_id)
            add(
                "messages",
                "Messages",
                [
                    {
                        "id": t.id,
                        "title": t.subject,
                        "subtitle": f"{t.topic.replace('_', ' ').title()} · {t.status}",
                        "route": "/messages",
                    }
                    for t in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if "tasks" in wanted:
            stmt = scoped(select(Task).where(Task.title.ilike(needle)), Task.household_id)
            add(
                "tasks",
                "Tasks",
                [
                    {
                        "id": t.id,
                        "title": t.title,
                        "subtitle": f"{t.priority.title()} priority · {t.status.replace('_', ' ')}",
                        "route": "/advisor/tasks",
                    }
                    for t in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if "reports" in wanted:
            stmt = scoped(select(Report).where(Report.title.ilike(needle)), Report.household_id)
            add(
                "reports",
                "Reports",
                [
                    {
                        "id": r.id,
                        "title": r.title,
                        "subtitle": f"{r.period_start} to {r.period_end}",
                        "route": "/reports",
                    }
                    for r in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if "trades" in wanted:
            stmt = scoped(select(Rebalance).where(Rebalance.name.ilike(needle)), Rebalance.household_id)
            add(
                "trades",
                "Rebalancing",
                [
                    {
                        "id": r.id,
                        "title": r.name,
                        "subtitle": f"{r.status.replace('_', ' ').title()} · ${r.turnover_amount:,.0f} turnover",
                        "route": "/advisor/rebalancing",
                    }
                    for r in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if "approvals" in wanted:
            stmt = scoped(select(Approval).where(Approval.title.ilike(needle)), Approval.household_id)
            add(
                "approvals",
                "Approvals",
                [
                    {
                        "id": a.id,
                        "title": a.title,
                        "subtitle": f"{a.entity_type.replace('_', ' ').title()} · {a.status.replace('_', ' ')}",
                        "route": "/approvals",
                    }
                    for a in self.db.execute(stmt.limit(20)).scalars().all()
                ],
            )

        if user.role in {Role.PLAN_SPONSOR, Role.COMPLIANCE, Role.ADMIN, Role.ADVISOR, Role.OPERATIONS}:
            if "plans" in wanted:
                add(
                    "plans",
                    "Retirement Plans",
                    [
                        {
                            "id": p.id,
                            "title": p.name,
                            "subtitle": f"{p.plan_type.upper()} · ${p.total_assets:,.0f}",
                            "route": "/institutional/plans",
                        }
                        for p in self.db.execute(select(Plan).where(Plan.name.ilike(needle)).limit(20)).scalars().all()
                    ],
                )
            if "participants" in wanted:
                add(
                    "participants",
                    "Participants",
                    [
                        {
                            "id": p.id,
                            "title": p.full_name,
                            "subtitle": f"Balance ${p.account_balance:,.0f} · {p.deferral_rate:.1%} deferral",
                            "route": "/institutional/participants",
                        }
                        for p in self.db.execute(
                            select(Participant).where(Participant.full_name.ilike(needle)).limit(20)
                        ).scalars().all()
                    ],
                )

        total = sum(g["count"] for g in groups)
        self.db.add(SearchHistory(user_id=user.id, query=term, result_count=total))
        self.db.commit()

        return {
            "query": term,
            "groups": sorted(groups, key=lambda g: g["count"], reverse=True),
            "total": total,
        }

    def suggestions(self, user: User) -> dict[str, Any]:
        recent = self.db.execute(
            select(SearchHistory)
            .where(SearchHistory.user_id == user.id)
            .order_by(SearchHistory.created_at.desc())
            .limit(8)
        ).scalars().all()
        saved = self.db.execute(select(SavedView).where(SavedView.user_id == user.id)).scalars().all()

        defaults_by_role = {
            Role.CLIENT: ["Retirement", "Brokerage", "Tax return", "Education fund"],
            Role.ADVISOR: ["Pending approvals", "Off track goals", "Harvest candidates", "Quarterly review"],
            Role.PLAN_SPONSOR: ["Form 5500", "ADP test", "Participation", "Fund watch list"],
            Role.PARTICIPANT: ["Contributions", "Loans", "Beneficiaries", "Vesting"],
            Role.COMPLIANCE: ["Overdue filings", "Approvals", "Audit trail", "Top heavy"],
        }

        seen: set[str] = set()
        recent_queries = []
        for row in recent:
            if row.query.lower() in seen:
                continue
            seen.add(row.query.lower())
            recent_queries.append({"query": row.query, "result_count": row.result_count})

        return {
            "recent": recent_queries,
            "suggested": defaults_by_role.get(user.role, ["Accounts", "Documents", "Reports"]),
            "categories": CATEGORIES,
            "saved_views": [
                {"id": v.id, "name": v.name, "query": v.query, "categories": v.categories, "is_pinned": v.is_pinned}
                for v in saved
            ],
        }

    def save_view(self, user: User, name: str, query: str, categories: Sequence[str] | None = None) -> dict[str, Any]:
        view = SavedView(user_id=user.id, name=name, query=query, categories=list(categories or []))
        self.db.add(view)
        self.db.commit()
        self.db.refresh(view)
        return {"id": view.id, "name": view.name, "query": view.query, "categories": view.categories}
