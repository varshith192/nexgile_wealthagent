"""Goal management, forecasting and scenario comparison (§14)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, AuditService
from app.calculations import goals as calc
from app.core.constants import EntityType
from app.core.errors import NotFoundError, ValidationError
from app.models.identity import User
from app.models.planning import Goal, GoalAccount, Scenario
from app.models.wealth import Account


class GoalService:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)

    # -- reads --------------------------------------------------------
    def _as_dict(self, goal: Goal) -> dict[str, Any]:
        return {
            "id": goal.id,
            "name": goal.name,
            "goal_type": goal.goal_type,
            "description": goal.description,
            "target_amount": goal.target_amount,
            "current_amount": goal.current_amount,
            "target_date": goal.target_date,
            "monthly_contribution": goal.monthly_contribution,
            "expected_return": goal.expected_return,
            "inflation_rate": goal.inflation_rate,
            "priority": goal.priority,
            "owner_label": goal.owner_label,
        }

    def get(self, goal_id: str) -> Goal:
        goal = self.db.get(Goal, goal_id)
        if not goal:
            raise NotFoundError("Goal not found.")
        return goal

    def list(self, household_id: str) -> list[Goal]:
        return list(
            self.db.execute(
                select(Goal).where(Goal.household_id == household_id).order_by(Goal.priority, Goal.target_date)
            ).scalars().all()
        )

    def summary(self, household_id: str, as_of: date) -> dict[str, Any]:
        goals = self.list(household_id)
        payload = calc.household_goal_summary([self._as_dict(g) for g in goals], as_of).to_dict()

        # Persist the derived status so list views and alerts agree.
        by_id = {g.id: g for g in goals}
        for row in payload["result"]["goals"]:
            goal = by_id.get(row["id"])
            if goal and goal.status != row["status"]:
                goal.status = row["status"]
        if goals:
            self.db.commit()
        return payload

    def detail(self, goal_id: str, as_of: date) -> dict[str, Any]:
        goal = self.get(goal_id)
        projection = calc.project_goal(self._as_dict(goal), as_of).to_dict()
        links = self.db.execute(select(GoalAccount).where(GoalAccount.goal_id == goal.id)).scalars().all()
        accounts = []
        for link in links:
            account = self.db.get(Account, link.account_id)
            if account:
                accounts.append(
                    {
                        "id": account.id,
                        "name": account.name,
                        "account_type": account.account_type,
                        "balance": round(account.balance, 2),
                        "allocation_percent": link.allocation_percent,
                        "contribution_to_goal": round(account.balance * link.allocation_percent, 2),
                    }
                )

        saved = self.db.execute(
            select(Scenario).where(Scenario.goal_id == goal.id).order_by(Scenario.created_at.desc()).limit(10)
        ).scalars().all()

        return {
            "goal": {
                "id": goal.id,
                "household_id": goal.household_id,
                "name": goal.name,
                "goal_type": goal.goal_type,
                "description": goal.description,
                "target_amount": round(goal.target_amount, 2),
                "current_amount": round(goal.current_amount, 2),
                "target_date": goal.target_date.isoformat(),
                "monthly_contribution": round(goal.monthly_contribution, 2),
                "expected_return": goal.expected_return,
                "inflation_rate": goal.inflation_rate,
                "priority": goal.priority,
                "status": goal.status,
                "owner_label": goal.owner_label,
            },
            "projection": projection,
            "linked_accounts": accounts,
            "saved_scenarios": [
                {
                    "id": s.id,
                    "name": s.name,
                    "scenario_key": s.scenario_key,
                    "inputs": s.inputs,
                    "assumptions": s.assumptions,
                    "result": s.result,
                    "method": s.method,
                    "is_baseline": s.is_baseline,
                    "run_at": s.run_at.isoformat() if s.run_at else None,
                }
                for s in saved
            ],
        }

    # -- scenarios ----------------------------------------------------
    def run_scenarios(
        self,
        goal_id: str,
        as_of: date,
        *,
        scenario_keys: Sequence[str] | None = None,
        actor: User | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Run what-ifs. Never writes back to the goal itself (§4)."""
        goal = self.get(goal_id)
        result = calc.compare_scenarios(self._as_dict(goal), as_of, scenario_keys).to_dict()

        if persist:
            now = datetime.now(timezone.utc)
            for row in result["result"]["scenarios"]:
                self.db.add(
                    Scenario(
                        goal_id=goal.id,
                        household_id=goal.household_id,
                        name=row["label"],
                        scenario_key=row["key"],
                        inputs={
                            "monthly_contribution": row["monthly_contribution"],
                            "expected_return": row["expected_return"],
                            "target_date": row["target_date"],
                        },
                        assumptions={"list": row["assumptions"]},
                        result={
                            "projected_value": row["projected_value"],
                            "gap": row["gap"],
                            "funded_ratio": row["funded_ratio"],
                            "status": row["status"],
                            "delta_vs_base": row["delta_vs_base"],
                        },
                        method=result["method"],
                        is_baseline=row["is_baseline"],
                        run_at=now,
                        created_by_id=getattr(actor, "id", None),
                    )
                )
            self.audit.record(
                action=AuditAction.SCENARIO_RUN,
                entity_type=EntityType.GOAL,
                entity_id=goal.id,
                entity_label=goal.name,
                actor=actor,
                household_id=goal.household_id,
                summary=f"Ran {len(result['result']['scenarios'])} scenarios (books of record unchanged)",
                after={"scenarios": [r["key"] for r in result["result"]["scenarios"]]},
                commit=False,
            )
            self.db.commit()

        return result

    # -- writes -------------------------------------------------------
    def create(self, household_id: str, payload: dict[str, Any], actor: User | None = None) -> Goal:
        target_date = payload["target_date"]
        if isinstance(target_date, str):
            target_date = date.fromisoformat(target_date)
        if target_date <= date.today():
            raise ValidationError("The target date must be in the future.")
        if float(payload.get("target_amount", 0)) <= 0:
            raise ValidationError("The target amount must be greater than zero.")

        goal = Goal(
            household_id=household_id,
            client_id=payload.get("client_id"),
            name=payload["name"],
            goal_type=payload["goal_type"],
            description=payload.get("description"),
            target_amount=float(payload["target_amount"]),
            current_amount=float(payload.get("current_amount") or 0.0),
            target_date=target_date,
            monthly_contribution=float(payload.get("monthly_contribution") or 0.0),
            expected_return=float(payload.get("expected_return") or 0.06),
            inflation_rate=float(payload.get("inflation_rate") or 0.025),
            priority=payload.get("priority", "medium"),
            owner_label=payload.get("owner_label"),
        )
        self.db.add(goal)
        self.db.flush()

        for account_id in payload.get("account_ids") or []:
            self.db.add(GoalAccount(goal_id=goal.id, account_id=account_id, allocation_percent=1.0))

        self.audit.record(
            action=AuditAction.CREATE,
            entity_type=EntityType.GOAL,
            entity_id=goal.id,
            entity_label=goal.name,
            actor=actor,
            household_id=household_id,
            summary=f"Goal created: {goal.name}",
            after={"target_amount": goal.target_amount, "target_date": goal.target_date},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def update(self, goal_id: str, payload: dict[str, Any], actor: User | None = None) -> Goal:
        goal = self.get(goal_id)
        before = {
            "target_amount": goal.target_amount,
            "monthly_contribution": goal.monthly_contribution,
            "target_date": goal.target_date,
            "expected_return": goal.expected_return,
        }

        for field in (
            "name",
            "description",
            "target_amount",
            "current_amount",
            "monthly_contribution",
            "expected_return",
            "inflation_rate",
            "priority",
            "owner_label",
        ):
            if field in payload and payload[field] is not None:
                setattr(goal, field, payload[field])
        if payload.get("target_date"):
            target_date = payload["target_date"]
            goal.target_date = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date

        self.audit.record(
            action=AuditAction.GOAL_UPDATED,
            entity_type=EntityType.GOAL,
            entity_id=goal.id,
            entity_label=goal.name,
            actor=actor,
            household_id=goal.household_id,
            summary=f"Goal updated: {goal.name}",
            before=before,
            after={
                "target_amount": goal.target_amount,
                "monthly_contribution": goal.monthly_contribution,
                "target_date": goal.target_date,
                "expected_return": goal.expected_return,
            },
            commit=False,
        )
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def delete(self, goal_id: str, actor: User | None = None) -> None:
        goal = self.get(goal_id)
        label, household_id = goal.name, goal.household_id
        self.db.delete(goal)
        self.audit.record(
            action=AuditAction.DELETE,
            entity_type=EntityType.GOAL,
            entity_id=goal_id,
            entity_label=label,
            actor=actor,
            household_id=household_id,
            summary=f"Goal removed: {label}",
            commit=False,
        )
        self.db.commit()
