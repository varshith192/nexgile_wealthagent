"""Tax Center (§15) and the tax-loss harvesting workflow (§24).

Nothing here places a trade. An opportunity becomes an action only after review,
recommendation, approval and an explicitly simulated execution step.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, AuditService
from app.calculations import tax as calc
from app.core.constants import ApprovalStatus, EntityType, Role
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.estate import Gift
from app.models.identity import Client, User
from app.models.tax import RMD, Harvest, TaxOpportunity, WashSaleWindow
from app.models.wealth import Account, Holding, Security, TaxLot, Transaction
from app.models.workflow import Approval
from app.workflows.approval_engine import ApprovalEngine

MINIMUM_HARVEST_LOSS = 1000.0
DEFAULT_GAIN_BUDGET = 250_000.0


class TaxService:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.approvals = ApprovalEngine(db, self.audit)

    # -- helpers ------------------------------------------------------
    def _primary_client(self, household_id: str) -> Client | None:
        return self.db.execute(
            select(Client).where(Client.household_id == household_id).order_by(Client.created_at)
        ).scalars().first()

    def _rates(self, household_id: str) -> tuple[float, float, float]:
        client = self._primary_client(household_id)
        if not client:
            return 0.35, 0.20, 0.05
        return client.marginal_tax_rate, client.ltcg_tax_rate, client.state_tax_rate

    def _open_lots(self, household_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(TaxLot, Holding, Security, Account)
            .join(Holding, TaxLot.holding_id == Holding.id)
            .join(Security, Holding.security_id == Security.id)
            .join(Account, Holding.account_id == Account.id)
            .where(Account.household_id == household_id, TaxLot.is_open.is_(True))
        ).all()

        blocked = self._active_wash_windows(household_id)
        lots = []
        for lot, holding, security, account in rows:
            replacement = self._replacement_for(security)
            lots.append(
                {
                    "id": lot.id,
                    "holding_id": holding.id,
                    "security_id": security.id,
                    "account_id": account.id,
                    "account_name": account.name,
                    "symbol": security.symbol,
                    "name": security.name,
                    "quantity": lot.quantity,
                    "cost_per_share": lot.cost_per_share,
                    "price": security.last_price,
                    "acquired_on": lot.acquired_on,
                    "wash_sale_risk": "blocked" if (account.id, security.id) in blocked else "clear",
                    "replacement_symbol": replacement.symbol if replacement else None,
                    "replacement_security_id": replacement.id if replacement else None,
                    "tax_treatment": account.tax_treatment,
                }
            )
        return lots

    def _active_wash_windows(self, household_id: str) -> set[tuple[str, str]]:
        rows = self.db.execute(
            select(WashSaleWindow, Account)
            .join(Account, WashSaleWindow.account_id == Account.id)
            .where(Account.household_id == household_id, WashSaleWindow.is_active.is_(True))
        ).all()
        today = date.today()
        return {
            (window.account_id, window.security_id)
            for window, _ in rows
            if window.window_start <= today <= window.window_end
        }

    def _replacement_for(self, security: Security) -> Security | None:
        """A same-exposure, not substantially identical, alternative."""
        return self.db.execute(
            select(Security)
            .where(
                Security.asset_class == security.asset_class,
                Security.id != security.id,
                Security.symbol != (security.substantially_identical_to or ""),
                (Security.substantially_identical_to.is_(None))
                | (Security.substantially_identical_to != security.symbol),
            )
            .order_by(Security.expense_ratio)
        ).scalars().first()

    # -- overview -----------------------------------------------------
    def overview(self, household_id: str, as_of: date, tax_year: int | None = None) -> dict[str, Any]:
        tax_year = tax_year or as_of.year
        marginal, ltcg, state = self._rates(household_id)

        transactions = self.db.execute(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.household_id == household_id)
        ).scalars().all()
        realized = calc.realized_gains(
            [
                {"trade_date": t.trade_date, "realized_gain": t.realized_gain, "is_long_term": t.is_long_term}
                for t in transactions
            ],
            tax_year,
            as_of,
        ).to_dict()

        estimate = calc.estimate_tax_on_gains(
            realized["result"]["short_term_gain"],
            realized["result"]["long_term_gain"],
            marginal,
            ltcg,
            state,
            as_of,
        ).to_dict()

        harvest = calc.harvest_opportunities(
            self._open_lots(household_id), marginal, ltcg, state, as_of, minimum_loss=MINIMUM_HARVEST_LOSS
        ).to_dict()

        positions = self.db.execute(
            select(Holding, Security, Account)
            .join(Security, Holding.security_id == Security.id)
            .join(Account, Holding.account_id == Account.id)
            .where(Account.household_id == household_id)
        ).all()
        location = calc.asset_location_review(
            [
                {
                    "symbol": s.symbol,
                    "name": s.name,
                    "asset_class": s.asset_class,
                    "quantity": h.quantity,
                    "price": s.last_price,
                    "dividend_yield": s.dividend_yield,
                    "tax_treatment": a.tax_treatment,
                }
                for h, s, a in positions
            ],
            as_of,
        ).to_dict()

        budget = calc.capital_gains_budget(
            realized["result"]["net_gain"], DEFAULT_GAIN_BUDGET, 0.0, as_of
        ).to_dict()

        municipal_income = sum(
            h.quantity * s.last_price * (s.dividend_yield or 0) for h, s, _ in positions if s.is_municipal
        )

        return {
            "tax_year": tax_year,
            "as_of": as_of.isoformat(),
            "rates": {"marginal": marginal, "long_term_capital_gains": ltcg, "state": state},
            "realized_gains": realized,
            "tax_estimate": estimate,
            "harvest": harvest,
            "asset_location": location,
            "capital_gains_budget": budget,
            "municipal_income": round(municipal_income, 2),
            "opportunities": self.opportunities(household_id, tax_year),
            "rmd": self.rmd_status(household_id, tax_year, as_of),
            "roth_conversion": self.roth_analysis(household_id, as_of),
            "wash_sale_windows": self.wash_sale_windows(household_id),
            "charitable_securities": self.charitable_securities(household_id, tax_year),
            "projection": self.projection(household_id, as_of, tax_year),
        }

    def opportunities(self, household_id: str, tax_year: int | None = None) -> list[dict[str, Any]]:
        stmt = select(TaxOpportunity).where(TaxOpportunity.household_id == household_id)
        if tax_year:
            stmt = stmt.where(TaxOpportunity.tax_year == tax_year)
        rows = self.db.execute(stmt.order_by(TaxOpportunity.estimated_benefit.desc())).scalars().all()
        return [
            {
                "id": row.id,
                "opportunity_type": row.opportunity_type,
                "title": row.title,
                "description": row.description,
                "estimated_benefit": round(row.estimated_benefit, 2),
                "tax_year": row.tax_year,
                "severity": row.severity,
                "status": row.status,
                "deadline": row.deadline.isoformat() if row.deadline else None,
                "method": row.method,
                "assumptions": row.assumptions,
                "supporting_data": row.supporting_data,
            }
            for row in rows
        ]

    def wash_sale_windows(self, household_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(WashSaleWindow, Account, Security)
            .join(Account, WashSaleWindow.account_id == Account.id)
            .join(Security, WashSaleWindow.security_id == Security.id)
            .where(Account.household_id == household_id)
            .order_by(WashSaleWindow.window_end.desc())
        ).all()
        today = date.today()
        return [
            {
                "id": window.id,
                "account_name": account.name,
                "symbol": security.symbol,
                "security_name": security.name,
                "window_start": window.window_start.isoformat(),
                "window_end": window.window_end.isoformat(),
                "reason": window.reason,
                "is_active": window.is_active and window.window_start <= today <= window.window_end,
                "days_remaining": max((window.window_end - today).days, 0),
            }
            for window, account, security in rows
        ]

    def check_wash_sale(self, household_id: str, security_id: str, sale_date: date | None = None) -> dict[str, Any]:
        security = self.db.get(Security, security_id)
        if not security:
            raise NotFoundError("Security not found.")
        sale_date = sale_date or date.today()

        purchases = self.db.execute(
            select(Transaction, Security)
            .join(Account, Transaction.account_id == Account.id)
            .join(Security, Transaction.security_id == Security.id)
            .where(Account.household_id == household_id, Transaction.transaction_type == "buy")
        ).all()

        identical = [security.substantially_identical_to] if security.substantially_identical_to else []
        identical += [
            s.symbol
            for s in self.db.execute(
                select(Security).where(Security.substantially_identical_to == security.symbol)
            ).scalars().all()
        ]

        return calc.wash_sale_check(
            security.symbol,
            sale_date,
            [{"symbol": s.symbol, "trade_date": t.trade_date, "quantity": t.quantity} for t, s in purchases],
            [s for s in identical if s],
        ).to_dict()

    def rmd_status(self, household_id: str, tax_year: int, as_of: date) -> dict[str, Any]:
        client = self._primary_client(household_id)
        rows = (
            self.db.execute(
                select(RMD).join(Client, RMD.client_id == Client.id).where(
                    Client.household_id == household_id, RMD.tax_year == tax_year
                )
            ).scalars().all()
            if client
            else []
        )
        required = sum(r.required_amount for r in rows)
        distributed = sum(r.distributed_amount for r in rows)
        age = None
        if client and client.birth_date:
            age = as_of.year - client.birth_date.year

        calculation = (
            calc.rmd_amount(age, rows[0].prior_year_end_balance, tax_year, as_of).to_dict()
            if rows and age
            else None
        )

        return {
            "required_amount": round(required, 2),
            "distributed_amount": round(distributed, 2),
            "remaining": round(max(required - distributed, 0.0), 2),
            "deadline": date(tax_year, 12, 31).isoformat(),
            "is_required": required > 0,
            "status": "satisfied" if required and distributed >= required else ("pending" if required else "not_applicable"),
            "accounts": [
                {
                    "id": r.id,
                    "account_id": r.account_id,
                    "required_amount": round(r.required_amount, 2),
                    "distributed_amount": round(r.distributed_amount, 2),
                    "life_expectancy_factor": r.life_expectancy_factor,
                    "prior_year_end_balance": round(r.prior_year_end_balance, 2),
                    "satisfied_by_qcd": round(r.satisfied_by_qcd, 2),
                    "status": r.status,
                    "method": r.method,
                }
                for r in rows
            ],
            "calculation": calculation,
        }

    def roth_analysis(self, household_id: str, as_of: date, amount: float | None = None) -> dict[str, Any]:
        client = self._primary_client(household_id)
        if not client:
            return {}
        years = max(client.retirement_age - (as_of.year - client.birth_date.year), 0) if client.birth_date else 10
        conversion = amount or 100_000.0
        return calc.roth_conversion(
            conversion,
            client.marginal_tax_rate,
            max(client.marginal_tax_rate - 0.05, 0.10),
            years,
            0.06,
            as_of,
        ).to_dict()

    def charitable_securities(self, household_id: str, tax_year: int) -> list[dict[str, Any]]:
        """Long-term appreciated positions that make efficient charitable gifts."""
        rows = self.db.execute(
            select(Holding, Security, Account)
            .join(Security, Holding.security_id == Security.id)
            .join(Account, Holding.account_id == Account.id)
            .where(Account.household_id == household_id, Account.tax_treatment == "taxable")
        ).all()
        _, ltcg, state = self._rates(household_id)
        today = date.today()

        candidates = []
        for holding, security, account in rows:
            gain = holding.quantity * (security.last_price - holding.average_cost)
            long_term = holding.acquired_on and (today - holding.acquired_on).days >= 366
            if gain <= 10_000 or not long_term:
                continue
            candidates.append(
                {
                    "holding_id": holding.id,
                    "symbol": security.symbol,
                    "name": security.name,
                    "account_name": account.name,
                    "market_value": round(holding.quantity * security.last_price, 2),
                    "cost_basis": round(holding.quantity * holding.average_cost, 2),
                    "unrealized_gain": round(gain, 2),
                    "gain_percent": round(gain / (holding.quantity * holding.average_cost), 4)
                    if holding.average_cost
                    else 0,
                    "capital_gains_tax_avoided": round(gain * (ltcg + state), 2),
                    "holding_period": "long_term",
                }
            )
        candidates.sort(key=lambda c: c["capital_gains_tax_avoided"], reverse=True)
        return candidates[:8]

    def projection(self, household_id: str, as_of: date, tax_year: int) -> dict[str, Any]:
        """Year-end tax picture: realised to date, plus estimated remaining."""
        client = self._primary_client(household_id)
        marginal, ltcg, state = self._rates(household_id)
        income = client.annual_income if client else 0.0

        transactions = self.db.execute(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.household_id == household_id)
        ).scalars().all()
        realized = calc.realized_gains(
            [
                {"trade_date": t.trade_date, "realized_gain": t.realized_gain, "is_long_term": t.is_long_term}
                for t in transactions
            ],
            tax_year,
            as_of,
        ).result

        gains_tax = calc.estimate_tax_on_gains(
            realized["short_term_gain"], realized["long_term_gain"], marginal, ltcg, state, as_of
        ).result
        ordinary_tax = income * marginal
        state_tax = income * state

        return {
            "tax_year": tax_year,
            "estimated_ordinary_income_tax": round(ordinary_tax, 2),
            "estimated_state_tax": round(state_tax, 2),
            "estimated_capital_gains_tax": gains_tax["total_tax"],
            "estimated_total_tax": round(ordinary_tax + state_tax + gains_tax["total_tax"], 2),
            "effective_rate": round(
                (ordinary_tax + state_tax + gains_tax["total_tax"]) / income, 4
            ) if income else 0.0,
            "assumptions": [
                "A flat marginal rate is applied to ordinary income rather than bracket-by-bracket calculation.",
                "Deductions, credits, AMT and the net investment income tax are not modelled.",
            ],
            "limitations": ["A planning estimate only. It is not a tax return calculation or tax advice."],
        }

    # -- harvesting workflow (§24) ------------------------------------
    def list_harvests(self, household_id: str, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(Harvest).where(Harvest.household_id == household_id)
        if status:
            stmt = stmt.where(Harvest.status == status)
        rows = self.db.execute(stmt.order_by(Harvest.estimated_tax_benefit.desc())).scalars().all()
        return [self._serialise_harvest(h) for h in rows]

    def _serialise_harvest(self, harvest: Harvest) -> dict[str, Any]:
        security = self.db.get(Security, harvest.security_id)
        replacement = (
            self.db.get(Security, harvest.replacement_security_id) if harvest.replacement_security_id else None
        )
        account = self.db.get(Account, harvest.account_id)
        return {
            "id": harvest.id,
            "account_id": harvest.account_id,
            "account_name": account.name if account else None,
            "security_id": harvest.security_id,
            "symbol": security.symbol if security else None,
            "security_name": security.name if security else None,
            "tax_lot_id": harvest.tax_lot_id,
            "quantity": round(harvest.quantity, 4),
            "cost_basis": round(harvest.cost_basis, 2),
            "market_value": round(harvest.market_value, 2),
            "unrealized_loss": round(harvest.unrealized_loss, 2),
            "holding_period": harvest.holding_period,
            "estimated_tax_benefit": round(harvest.estimated_tax_benefit, 2),
            "wash_sale_risk": harvest.wash_sale_risk,
            "wash_sale_window_ends": harvest.wash_sale_window_ends.isoformat()
            if harvest.wash_sale_window_ends
            else None,
            "replacement_security_id": harvest.replacement_security_id,
            "replacement_symbol": replacement.symbol if replacement else None,
            "replacement_name": replacement.name if replacement else None,
            "status": harvest.status,
            "tax_year": harvest.tax_year,
            "approval_id": harvest.approval_id,
            "is_simulated": harvest.is_simulated,
            "executed_at": harvest.executed_at.isoformat() if harvest.executed_at else None,
            "notes": harvest.notes,
        }

    def create_harvest(self, household_id: str, lot_id: str, actor: User, as_of: date) -> dict[str, Any]:
        """Turn an identified opportunity into a reviewable proposal."""
        lot = self.db.get(TaxLot, lot_id)
        if not lot:
            raise NotFoundError("Tax lot not found.")
        holding = self.db.get(Holding, lot.holding_id)
        security = self.db.get(Security, holding.security_id)
        account = self.db.get(Account, holding.account_id)
        if account.household_id != household_id:
            raise ValidationError("That tax lot does not belong to this household.")

        existing = self.db.execute(
            select(Harvest).where(
                Harvest.tax_lot_id == lot_id, Harvest.status.notin_(["rejected", "cancelled"])
            )
        ).scalars().first()
        if existing:
            raise ConflictError("A harvest proposal already exists for this tax lot.")

        market_value = lot.quantity * security.last_price
        cost_basis = lot.quantity * lot.cost_per_share
        loss = market_value - cost_basis
        if loss >= 0:
            raise ValidationError("This lot holds an unrealised gain, not a loss; it cannot be harvested.")

        marginal, ltcg, state = self._rates(household_id)
        period = calc.holding_period(lot.acquired_on, as_of)
        rate = ltcg if period == "long_term" else marginal
        benefit = abs(loss) * (rate + state)

        wash = self.check_wash_sale(household_id, security.id, as_of)
        replacement = self._replacement_for(security)

        harvest = Harvest(
            household_id=household_id,
            account_id=account.id,
            security_id=security.id,
            tax_lot_id=lot.id,
            replacement_security_id=replacement.id if replacement else None,
            quantity=lot.quantity,
            cost_basis=cost_basis,
            market_value=market_value,
            unrealized_loss=loss,
            holding_period=period,
            estimated_tax_benefit=benefit,
            wash_sale_risk=wash["result"]["risk"],
            wash_sale_window_ends=as_of + timedelta(days=30),
            status="proposed",
            tax_year=as_of.year,
            notes=f"Replacement candidate: {replacement.symbol if replacement else 'none identified'}",
        )
        self.db.add(harvest)
        self.db.flush()

        approval = self.approvals.create(
            entity_type=EntityType.HARVEST,
            entity_id=harvest.id,
            title=f"Harvest {security.symbol} loss in {account.name}",
            summary=(
                f"Realise a {abs(loss):,.0f} loss for an estimated {benefit:,.0f} tax benefit, "
                f"replacing with {replacement.symbol if replacement else 'cash'}."
            ),
            household_id=household_id,
            requested_by=actor,
            required_role=Role.TAX_SPECIALIST,
            priority="medium",
            payload={"harvest_id": harvest.id, "wash_sale": wash["result"]},
            estimated_impact=benefit,
            status=ApprovalStatus.DRAFT,
            commit=False,
        )
        harvest.approval_id = approval.id

        self.audit.record(
            action=AuditAction.HARVEST_CREATED,
            entity_type=EntityType.HARVEST,
            entity_id=harvest.id,
            entity_label=f"{security.symbol} harvest",
            actor=actor,
            household_id=household_id,
            summary=f"Harvest proposal created for {security.symbol}",
            after={"unrealized_loss": round(loss, 2), "estimated_benefit": round(benefit, 2)},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(harvest)
        return self._serialise_harvest(harvest)

    def execute_harvest(self, harvest_id: str, actor: User) -> dict[str, Any]:
        """Simulated execution. This platform never contacts a broker."""
        harvest = self.db.get(Harvest, harvest_id)
        if not harvest:
            raise NotFoundError("Harvest proposal not found.")
        if harvest.status != "approved":
            raise ConflictError("Only an approved harvest can be executed.")

        harvest.status = "executed"
        harvest.executed_at = datetime.now(timezone.utc)
        harvest.is_simulated = True

        security = self.db.get(Security, harvest.security_id)
        self.db.add(
            WashSaleWindow(
                account_id=harvest.account_id,
                security_id=harvest.security_id,
                window_start=date.today() - timedelta(days=30),
                window_end=date.today() + timedelta(days=30),
                reason="Loss realised; repurchase within 30 days would trigger a wash sale",
                is_active=True,
            )
        )

        if harvest.approval_id:
            approval = self.db.get(Approval, harvest.approval_id)
            if approval and approval.status == ApprovalStatus.APPROVED:
                self.approvals.transition(
                    approval.id, ApprovalStatus.COMPLETED, actor=actor, note="Simulated execution recorded"
                )

        self.audit.record(
            action=AuditAction.HARVEST_EXECUTED,
            entity_type=EntityType.HARVEST,
            entity_id=harvest.id,
            entity_label=f"{security.symbol if security else 'harvest'} executed (simulated)",
            actor=actor,
            household_id=harvest.household_id,
            summary="Harvest executed in simulation; no order was sent to a custodian.",
            before={"status": "approved"},
            after={"status": "executed", "simulated": True},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(harvest)
        return self._serialise_harvest(harvest)
