"""Advisor workstation (§20), Client 360 (§21) and rebalancing (§23)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, AuditService
from app.calculations import advisory as calc
from app.core.constants import ApprovalStatus, EntityType, RebalanceStatus, Role
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.collab import ActionItem, Document, Meeting, Message, MessageThread
from app.models.estate import Beneficiary
from app.models.identity import AdvisorAssignment, Client, Household, HouseholdMember, User
from app.models.planning import Goal, Recommendation, Task
from app.models.tax import Harvest, TaxOpportunity
from app.models.wealth import Account, Security
from app.models.workflow import Alert, Approval, Rebalance, RebalanceTrade
from app.services.estate_service import EstateService
from app.services.goal_service import GoalService
from app.services.portfolio_service import PortfolioService
from app.services.tax_service import TaxService
from app.workflows.approval_engine import ApprovalEngine


class AdvisorService:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.portfolio = PortfolioService(db)
        self.goals = GoalService(db, self.audit)
        self.tax = TaxService(db, self.audit)
        self.estate = EstateService(db, self.audit)
        self.approvals = ApprovalEngine(db, self.audit)

    # -- book of business ---------------------------------------------
    def households(self, household_ids: Sequence[str] | None) -> list[Household]:
        stmt = select(Household)
        if household_ids is not None:
            stmt = stmt.where(Household.id.in_(list(household_ids)))
        return list(self.db.execute(stmt.order_by(Household.name)).scalars().all())

    def client_rows(self, household_ids: Sequence[str] | None) -> list[dict[str, Any]]:
        rows = []
        for household in self.households(household_ids):
            accounts = self.db.execute(
                select(Account).where(Account.household_id == household.id)
            ).scalars().all()
            assets = sum(a.balance for a in accounts if not a.is_liability)
            liabilities = sum(a.balance for a in accounts if a.is_liability)
            clients = self.db.execute(
                select(Client).where(Client.household_id == household.id)
            ).scalars().all()
            goals = self.db.execute(select(Goal).where(Goal.household_id == household.id)).scalars().all()
            open_approvals = self.db.execute(
                select(Approval).where(
                    Approval.household_id == household.id,
                    Approval.status.in_([ApprovalStatus.SUBMITTED, ApprovalStatus.UNDER_REVIEW]),
                )
            ).scalars().all()
            advisor = self.db.get(User, household.primary_advisor_id) if household.primary_advisor_id else None
            next_meeting = self.db.execute(
                select(Meeting)
                .where(Meeting.household_id == household.id, Meeting.status == "scheduled")
                .order_by(Meeting.starts_at)
            ).scalars().first()

            rows.append(
                {
                    "household_id": household.id,
                    "name": household.name,
                    "segment": household.segment,
                    "risk_profile": household.risk_profile,
                    "city": household.city,
                    "state": household.state,
                    "since": household.since.isoformat() if household.since else None,
                    "primary_advisor": advisor.full_name if advisor else "Unassigned",
                    "primary_contact": clients[0].full_name if clients else household.name,
                    "client_count": len(clients),
                    "account_count": len(accounts),
                    "total_assets": round(assets, 2),
                    "total_liabilities": round(liabilities, 2),
                    "net_worth": round(assets - liabilities, 2),
                    "goal_count": len(goals),
                    "goals_off_track": sum(1 for g in goals if g.status in {"at_risk", "off_track"}),
                    "pending_approvals": len(open_approvals),
                    "next_meeting": next_meeting.starts_at.isoformat() if next_meeting else None,
                    "status": clients[0].status if clients else "active",
                }
            )
        rows.sort(key=lambda r: r["total_assets"], reverse=True)
        return rows

    def dashboard(self, user: User, household_ids: Sequence[str] | None) -> dict[str, Any]:
        clients = self.client_rows(household_ids)
        ids = [c["household_id"] for c in clients]

        approvals_stmt = select(Approval).where(
            Approval.status.in_([ApprovalStatus.SUBMITTED, ApprovalStatus.UNDER_REVIEW])
        )
        if household_ids is not None:
            approvals_stmt = approvals_stmt.where(Approval.household_id.in_(ids))
        pending = list(self.db.execute(approvals_stmt.order_by(Approval.created_at.desc())).scalars().all())

        meetings = list(
            self.db.execute(
                select(Meeting)
                .where(Meeting.household_id.in_(ids), Meeting.status == "scheduled")
                .order_by(Meeting.starts_at)
                .limit(8)
            ).scalars().all()
        )
        tasks = list(
            self.db.execute(
                select(Task).where(Task.status != "complete").order_by(Task.due_date).limit(12)
            ).scalars().all()
        )
        alerts = list(
            self.db.execute(
                select(Alert)
                .where(Alert.household_id.in_(ids), Alert.dismissed_at.is_(None))
                .order_by(Alert.created_at.desc())
                .limit(10)
            ).scalars().all()
        )
        opportunities = list(
            self.db.execute(
                select(TaxOpportunity)
                .where(TaxOpportunity.household_id.in_(ids), TaxOpportunity.status == "identified")
                .order_by(TaxOpportunity.estimated_benefit.desc())
                .limit(8)
            ).scalars().all()
        )

        household_lookup = {c["household_id"]: c["name"] for c in clients}
        today = date.today()

        return {
            "advisor": {"id": user.id, "name": user.full_name, "title": user.title, "role": user.role},
            "summary": {
                "client_count": len(clients),
                "household_count": len(clients),
                "total_aum": round(sum(c["total_assets"] for c in clients), 2),
                "average_relationship": round(
                    sum(c["total_assets"] for c in clients) / len(clients), 2
                )
                if clients
                else 0.0,
                "pending_approvals": len(pending),
                "open_alerts": len(alerts),
                "meetings_this_week": sum(
                    1 for m in meetings if m.starts_at.date() <= today + timedelta(days=7)
                ),
                "open_tasks": len(tasks),
                "overdue_tasks": sum(1 for t in tasks if t.due_date and t.due_date < today),
                "goals_off_track": sum(c["goals_off_track"] for c in clients),
                "opportunity_value": round(sum(o.estimated_benefit for o in opportunities), 2),
            },
            "clients": clients[:12],
            "pending_approvals": [
                {
                    "id": a.id,
                    "title": a.title,
                    "entity_type": a.entity_type,
                    "status": a.status,
                    "priority": a.priority,
                    "household": household_lookup.get(a.household_id, "—"),
                    "household_id": a.household_id,
                    "estimated_impact": a.estimated_impact,
                    "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                }
                for a in pending[:10]
            ],
            "meetings": [
                {
                    "id": m.id,
                    "title": m.title,
                    "household": household_lookup.get(m.household_id, "—"),
                    "household_id": m.household_id,
                    "starts_at": m.starts_at.isoformat(),
                    "meeting_type": m.meeting_type,
                    "location": m.location,
                }
                for m in meetings
            ],
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "category": t.category,
                    "priority": t.priority,
                    "status": t.status,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                    "household": household_lookup.get(t.household_id, "—"),
                    "household_id": t.household_id,
                    "is_overdue": bool(t.due_date and t.due_date < today),
                }
                for t in tasks
            ],
            "alerts": [
                {
                    "id": a.id,
                    "title": a.title,
                    "body": a.body,
                    "severity": a.severity,
                    "category": a.category,
                    "household": household_lookup.get(a.household_id, "—"),
                    "household_id": a.household_id,
                    "created_at": a.created_at.isoformat(),
                }
                for a in alerts
            ],
            "opportunities": [
                {
                    "id": o.id,
                    "title": o.title,
                    "opportunity_type": o.opportunity_type,
                    "estimated_benefit": round(o.estimated_benefit, 2),
                    "household": household_lookup.get(o.household_id, "—"),
                    "household_id": o.household_id,
                    "severity": o.severity,
                    "deadline": o.deadline.isoformat() if o.deadline else None,
                }
                for o in opportunities
            ],
        }

    # -- Client 360 (§21) ---------------------------------------------
    def client_360(self, household_id: str) -> dict[str, Any]:
        household = self.db.get(Household, household_id)
        if not household:
            raise NotFoundError("Household not found.")

        as_of = self.portfolio.as_of(household_id)
        clients = self.db.execute(select(Client).where(Client.household_id == household_id)).scalars().all()
        members = self.db.execute(
            select(HouseholdMember).where(HouseholdMember.household_id == household_id)
        ).scalars().all()
        assignments = self.db.execute(
            select(AdvisorAssignment).where(AdvisorAssignment.household_id == household_id)
        ).scalars().all()

        threads = self.db.execute(
            select(MessageThread)
            .where(MessageThread.household_id == household_id)
            .order_by(MessageThread.last_message_at.desc())
            .limit(5)
        ).scalars().all()
        meetings = self.db.execute(
            select(Meeting).where(Meeting.household_id == household_id).order_by(Meeting.starts_at.desc()).limit(6)
        ).scalars().all()
        tasks = self.db.execute(
            select(Task).where(Task.household_id == household_id).order_by(Task.due_date).limit(10)
        ).scalars().all()
        recommendations = self.db.execute(
            select(Recommendation)
            .where(Recommendation.household_id == household_id)
            .order_by(Recommendation.created_at.desc())
            .limit(10)
        ).scalars().all()
        documents = self.db.execute(
            select(Document).where(Document.household_id == household_id).order_by(Document.created_at.desc()).limit(8)
        ).scalars().all()

        timeline = self.audit.timeline_for_household(household_id, limit=30)

        return {
            "household": {
                "id": household.id,
                "name": household.name,
                "segment": household.segment,
                "risk_profile": household.risk_profile,
                "since": household.since.isoformat() if household.since else None,
                "city": household.city,
                "state": household.state,
                "notes": household.notes,
            },
            "profile": [
                {
                    "id": c.id,
                    "full_name": c.full_name,
                    "birth_date": c.birth_date.isoformat() if c.birth_date else None,
                    "age": (as_of.year - c.birth_date.year) if c.birth_date else None,
                    "retirement_age": c.retirement_age,
                    "filing_status": c.filing_status,
                    "marginal_tax_rate": c.marginal_tax_rate,
                    "annual_income": round(c.annual_income, 2),
                    "annual_savings": round(c.annual_savings, 2),
                    "risk_tolerance": c.risk_tolerance,
                    "status": c.status,
                    "segment": c.segment,
                }
                for c in clients
            ],
            "household_members": [
                {
                    "id": m.id,
                    "full_name": m.full_name,
                    "relationship": m.relationship_type,
                    "birth_date": m.birth_date.isoformat() if m.birth_date else None,
                    "is_dependent": m.is_dependent,
                }
                for m in members
            ],
            "team": [
                {
                    "advisor_id": a.advisor_id,
                    "name": (self.db.get(User, a.advisor_id).full_name if self.db.get(User, a.advisor_id) else "—"),
                    "role_on_account": a.role_on_account,
                    "is_primary": a.is_primary,
                }
                for a in assignments
            ],
            "accounts": self.portfolio.accounts_view(household_id),
            "net_worth": self.portfolio.net_worth(household_id),
            "portfolio": {
                "valuation": self.portfolio.valuation(household_id),
                "allocation": self.portfolio.allocation(household_id),
                "drift": self.portfolio.drift(household_id),
                "concentration": self.portfolio.concentration(household_id),
                "risk": self.portfolio.risk(household_id),
                "performance": self.portfolio.performance(household_id),
            },
            "goals": self.goals.summary(household_id, as_of),
            "tax": {
                "harvest": self.tax.overview(household_id, as_of)["harvest"],
                "opportunities": self.tax.opportunities(household_id, as_of.year),
            },
            "estate": self.estate.overview(household_id, as_of),
            "documents": [
                {
                    "id": d.id,
                    "name": d.name,
                    "category": d.category,
                    "review_status": d.review_status,
                    "uploaded_at": (d.uploaded_at or d.created_at).isoformat(),
                }
                for d in documents
            ],
            "messages": [
                {
                    "id": t.id,
                    "subject": t.subject,
                    "topic": t.topic,
                    "status": t.status,
                    "last_message_at": t.last_message_at.isoformat() if t.last_message_at else None,
                    "message_count": len(t.messages),
                }
                for t in threads
            ],
            "meetings": [
                {
                    "id": m.id,
                    "title": m.title,
                    "meeting_type": m.meeting_type,
                    "starts_at": m.starts_at.isoformat(),
                    "status": m.status,
                    "agenda": m.agenda,
                    "summary": m.summary,
                }
                for m in meetings
            ],
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "category": t.category,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                }
                for t in tasks
            ],
            "recommendations": [
                {
                    "id": r.id,
                    "title": r.title,
                    "category": r.category,
                    "severity": r.severity,
                    "status": r.status,
                    "summary": r.summary,
                    "impact_amount": r.impact_amount,
                    "created_at": r.created_at.isoformat(),
                }
                for r in recommendations
            ],
            "activity": [
                {
                    "id": e.id,
                    "action": e.action,
                    "entity_type": e.entity_type,
                    "entity_label": e.entity_label,
                    "actor_name": e.actor_name,
                    "actor_role": e.actor_role,
                    "status": e.status,
                    "summary": e.summary,
                    "created_at": e.created_at.isoformat(),
                }
                for e in timeline
            ],
            "as_of": as_of.isoformat(),
        }

    # -- rebalancing (§23) --------------------------------------------
    def propose_rebalance(
        self, household_id: str, actor: User, *, name: str | None = None, note: str | None = None
    ) -> dict[str, Any]:
        portfolio = self.portfolio.get_portfolio(household_id)
        if not portfolio:
            raise NotFoundError("No portfolio exists for this household.")

        as_of = self.portfolio.as_of(household_id)
        positions = self.portfolio.positions(household_id)
        targets = self.portfolio.allocation_targets(household_id)
        if not targets:
            raise ValidationError("No strategic allocation targets are configured for this portfolio.")

        client = self.db.execute(
            select(Client).where(Client.household_id == household_id).order_by(Client.created_at)
        ).scalars().first()
        plan = calc.build_rebalance_plan(
            positions,
            targets,
            as_of,
            cash=self.portfolio.cash_balance(household_id),
            marginal_rate=client.marginal_tax_rate if client else 0.35,
            ltcg_rate=client.ltcg_tax_rate if client else 0.20,
        )

        rebalance = Rebalance(
            household_id=household_id,
            portfolio_id=portfolio.id,
            name=name or f"Rebalance to policy — {as_of.isoformat()}",
            strategy_note=note or "Return each asset class to its strategic target within tolerance.",
            status=RebalanceStatus.DRAFT,
            max_drift=plan.result["max_drift"],
            turnover_amount=plan.result["turnover_amount"],
            estimated_tax_cost=plan.result["estimated_tax_cost"],
            estimated_trading_cost=plan.result["estimated_trading_cost"],
            cash_impact=plan.result["cash_impact"],
            created_by_id=actor.id,
            as_of=datetime.now(timezone.utc),
            is_simulated=True,
        )
        self.db.add(rebalance)
        self.db.flush()

        for trade in plan.result["trades"]:
            self.db.add(
                RebalanceTrade(
                    rebalance_id=rebalance.id,
                    account_id=trade["account_id"],
                    security_id=trade["security_id"],
                    side=trade["side"],
                    quantity=trade["quantity"],
                    estimated_price=trade["estimated_price"],
                    estimated_amount=trade["estimated_amount"],
                    realized_gain=trade["realized_gain"],
                    tax_impact=trade["tax_impact"],
                    rationale=trade["rationale"],
                )
            )

        approval = self.approvals.create(
            entity_type=EntityType.REBALANCE,
            entity_id=rebalance.id,
            title=rebalance.name,
            summary=(
                f"{plan.result['trade_count']} trades, {plan.result['turnover_amount']:,.0f} turnover, "
                f"{plan.result['estimated_tax_cost']:,.0f} estimated tax cost."
            ),
            household_id=household_id,
            requested_by=actor,
            required_role=Role.INVESTMENT_TEAM,
            priority="medium",
            payload={"rebalance_id": rebalance.id, "max_drift": plan.result["max_drift"]},
            estimated_impact=plan.result["estimated_tax_cost"],
            status=ApprovalStatus.DRAFT,
            commit=False,
        )
        rebalance.approval_id = approval.id

        self.audit.record(
            action=AuditAction.REBALANCE_CREATED,
            entity_type=EntityType.REBALANCE,
            entity_id=rebalance.id,
            entity_label=rebalance.name,
            actor=actor,
            household_id=household_id,
            summary=f"Rebalance proposal created with {plan.result['trade_count']} trades",
            after={
                "max_drift": plan.result["max_drift"],
                "turnover": plan.result["turnover_amount"],
                "trade_count": plan.result["trade_count"],
            },
            commit=False,
        )
        self.db.commit()
        self.db.refresh(rebalance)
        return self.rebalance_detail(rebalance.id, calculation=plan.to_dict())

    def list_rebalances(self, household_ids: Sequence[str] | None, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(Rebalance)
        if household_ids is not None:
            stmt = stmt.where(Rebalance.household_id.in_(list(household_ids)))
        if status:
            stmt = stmt.where(Rebalance.status == status)
        rows = self.db.execute(stmt.order_by(Rebalance.created_at.desc())).scalars().all()
        return [self._rebalance_summary(r) for r in rows]

    def _rebalance_summary(self, rebalance: Rebalance) -> dict[str, Any]:
        household = self.db.get(Household, rebalance.household_id)
        return {
            "id": rebalance.id,
            "name": rebalance.name,
            "household_id": rebalance.household_id,
            "household": household.name if household else "—",
            "status": rebalance.status,
            "max_drift": rebalance.max_drift,
            "turnover_amount": round(rebalance.turnover_amount, 2),
            "estimated_tax_cost": round(rebalance.estimated_tax_cost, 2),
            "estimated_trading_cost": round(rebalance.estimated_trading_cost, 2),
            "trade_count": len(rebalance.trades),
            "approval_id": rebalance.approval_id,
            "is_simulated": rebalance.is_simulated,
            "created_at": rebalance.created_at.isoformat(),
            "executed_at": rebalance.executed_at.isoformat() if rebalance.executed_at else None,
        }

    def rebalance_detail(self, rebalance_id: str, calculation: dict[str, Any] | None = None) -> dict[str, Any]:
        rebalance = self.db.get(Rebalance, rebalance_id)
        if not rebalance:
            raise NotFoundError("Rebalance proposal not found.")

        trades = []
        for trade in rebalance.trades:
            security = self.db.get(Security, trade.security_id)
            account = self.db.get(Account, trade.account_id)
            trades.append(
                {
                    "id": trade.id,
                    "account_id": trade.account_id,
                    "account_name": account.name if account else "—",
                    "symbol": security.symbol if security else "—",
                    "name": security.name if security else "—",
                    "asset_class": security.asset_class if security else None,
                    "side": trade.side,
                    "quantity": round(trade.quantity, 4),
                    "estimated_price": round(trade.estimated_price, 2),
                    "estimated_amount": round(trade.estimated_amount, 2),
                    "realized_gain": round(trade.realized_gain, 2),
                    "tax_impact": round(trade.tax_impact, 2),
                    "rationale": trade.rationale,
                    "status": trade.status,
                }
            )

        return {
            **self._rebalance_summary(rebalance),
            "strategy_note": rebalance.strategy_note,
            "trades": trades,
            "current_allocation": self.portfolio.allocation(rebalance.household_id),
            "target_allocation": self.portfolio.allocation_targets(rebalance.household_id),
            "drift": self.portfolio.drift(rebalance.household_id),
            "calculation": calculation,
            "execution_note": (
                "Nexgile WealthAgent never routes orders to a custodian or broker. Approved proposals are "
                "marked as executed in simulation for demonstration purposes."
            ),
        }

    def execute_rebalance(self, rebalance_id: str, actor: User) -> dict[str, Any]:
        rebalance = self.db.get(Rebalance, rebalance_id)
        if not rebalance:
            raise NotFoundError("Rebalance proposal not found.")
        if rebalance.status not in {RebalanceStatus.APPROVED, "approved"}:
            raise ConflictError("Only an approved rebalance can be executed.")

        rebalance.status = RebalanceStatus.SUBMITTED
        for trade in rebalance.trades:
            trade.status = "filled_simulated"
        rebalance.status = RebalanceStatus.COMPLETED
        rebalance.executed_at = datetime.now(timezone.utc)

        if rebalance.approval_id:
            approval = self.db.get(Approval, rebalance.approval_id)
            if approval and approval.status == ApprovalStatus.APPROVED:
                self.approvals.transition(
                    approval.id, ApprovalStatus.COMPLETED, actor=actor, note="Simulated execution recorded"
                )

        self.audit.record(
            action=AuditAction.REBALANCE_EXECUTED,
            entity_type=EntityType.REBALANCE,
            entity_id=rebalance.id,
            entity_label=rebalance.name,
            actor=actor,
            household_id=rebalance.household_id,
            summary="Rebalance executed in simulation; no orders were sent to a custodian.",
            before={"status": "approved"},
            after={"status": "completed", "simulated": True, "trade_count": len(rebalance.trades)},
            commit=False,
        )
        self.db.commit()
        return self.rebalance_detail(rebalance.id)

    # -- tasks --------------------------------------------------------
    def tasks(self, household_ids: Sequence[str] | None, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(Task)
        if household_ids is not None:
            stmt = stmt.where(Task.household_id.in_(list(household_ids)))
        if status:
            stmt = stmt.where(Task.status == status)
        rows = self.db.execute(stmt.order_by(Task.due_date.nullslast())).scalars().all()
        today = date.today()
        result = []
        for t in rows:
            household = self.db.get(Household, t.household_id) if t.household_id else None
            assignee = self.db.get(User, t.assignee_id) if t.assignee_id else None
            result.append(
                {
                    "id": t.id,
                    "title": t.title,
                    "description": t.description,
                    "category": t.category,
                    "priority": t.priority,
                    "status": t.status,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                    "is_overdue": bool(t.due_date and t.due_date < today and t.status != "complete"),
                    "household": household.name if household else "—",
                    "household_id": t.household_id,
                    "assignee": assignee.full_name if assignee else "Unassigned",
                    "sla_days": t.sla_days,
                }
            )
        return result

    def update_task(self, task_id: str, status: str, actor: User) -> dict[str, Any]:
        task = self.db.get(Task, task_id)
        if not task:
            raise NotFoundError("Task not found.")
        if status not in {"open", "in_progress", "blocked", "complete"}:
            raise ValidationError("Unknown task status.")
        before = task.status
        task.status = status
        if status == "complete":
            task.completed_at = datetime.now(timezone.utc)

        self.audit.record(
            action=AuditAction.UPDATE,
            entity_type="task",
            entity_id=task.id,
            entity_label=task.title,
            actor=actor,
            household_id=task.household_id,
            summary=f"Task moved from {before} to {status}",
            before={"status": before},
            after={"status": status},
            commit=False,
        )
        self.db.commit()
        return {"id": task.id, "status": task.status}
