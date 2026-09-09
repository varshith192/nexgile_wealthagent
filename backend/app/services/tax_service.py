"""Tax Center (§15) and the tax-loss/gain harvesting workflow (§24).

Nothing here places a trade or files a return. An opportunity becomes an
action only after review, recommendation, approval and an explicitly
simulated execution step.

India has no wash-sale rule, so harvesting a loss and immediately
repurchasing is legitimate; the same is true of harvesting a long-term
equity gain inside the unused section 112A exemption. Both are surfaced
side by side by `app.calculations.tax.harvest_opportunities`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, AuditService
from app.calculations import tax as calc
from app.core.constants import ApprovalStatus, EntityType, Role
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.identity import Client, User
from app.models.tax import Harvest, NpsAnnuitization, TaxOpportunity
from app.models.wealth import Account, Holding, Security, TaxLot, Transaction
from app.models.workflow import Approval
from app.workflows.approval_engine import ApprovalEngine

MINIMUM_HARVEST_LOSS = 25_000.0
MINIMUM_HARVEST_GAIN = 10_000.0
DEFAULT_GAIN_BUDGET = 5_00_000.0


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

    def _rates(self, household_id: str) -> tuple[float, float]:
        """(marginal slab rate, long-term equity capital gains rate)."""
        client = self._primary_client(household_id)
        if not client:
            return 0.30, calc.LTCG_EQUITY_RATE
        return client.marginal_tax_rate, client.ltcg_tax_rate

    def _open_lots(self, household_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(TaxLot, Holding, Security, Account)
            .join(Holding, TaxLot.holding_id == Holding.id)
            .join(Security, Holding.security_id == Security.id)
            .join(Account, Holding.account_id == Account.id)
            .where(Account.household_id == household_id, TaxLot.is_open.is_(True), Account.tax_treatment == "taxable")
        ).all()

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
                    "asset_class": security.asset_class,
                    "quantity": lot.quantity,
                    "cost_per_share": lot.cost_per_share,
                    "price": security.last_price,
                    "acquired_on": lot.acquired_on,
                    "replacement_symbol": replacement.symbol if replacement else None,
                    "replacement_security_id": replacement.id if replacement else None,
                    "tax_treatment": account.tax_treatment,
                }
            )
        return lots

    def _replacement_for(self, security: Security) -> Security | None:
        """A same-exposure, not substantially identical, alternative.

        India has no wash-sale rule, so this is offered purely for style
        continuity while the household is briefly out of the position.
        """
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
        tax_year = tax_year or calc.financial_year_bounds(as_of)[0].year
        client = self._primary_client(household_id)
        marginal, ltcg = self._rates(household_id)
        total_income = client.annual_income if client else 0.0

        transactions = self.db.execute(
            select(Transaction, Security)
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Security, Transaction.security_id == Security.id)
            .where(Account.household_id == household_id)
        ).all()
        realized = calc.realized_gains(
            [
                {
                    "trade_date": t.trade_date,
                    "realized_gain": t.realized_gain,
                    "is_long_term": t.is_long_term,
                    "asset_class": s.asset_class if s else "indian_equity",
                }
                for t, s in transactions
            ],
            as_of,
        ).to_dict()
        rg = realized["result"]

        estimate = calc.estimate_capital_gains_tax(
            equity_stcg=rg["equity_stcg"],
            equity_ltcg=rg["equity_ltcg"],
            other_stcg=rg["other_stcg"],
            other_ltcg=rg["other_ltcg"],
            slab_rate=marginal,
            total_income=total_income,
            as_of=as_of,
        ).to_dict()

        exemption_remaining = float(estimate["result"]["exemption_remaining"])
        harvest = calc.harvest_opportunities(
            self._open_lots(household_id),
            slab_rate=marginal,
            ltcg_exemption_remaining=exemption_remaining,
            as_of=as_of,
            minimum_loss=MINIMUM_HARVEST_LOSS,
            minimum_gain=MINIMUM_HARVEST_GAIN,
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
            marginal,
            as_of,
        ).to_dict()

        budget = calc.capital_gains_budget(
            realized_net=rg["net_gain"], budget=DEFAULT_GAIN_BUDGET, pending_gains=0.0, as_of=as_of
        ).to_dict()

        tax_free_income = sum(
            h.quantity * s.last_price * (s.dividend_yield or 0) for h, s, _ in positions if s.is_tax_free
        )

        regime = calc.compare_regimes(
            gross_income=total_income,
            deductions=self._estimated_chapter_via_total(household_id, client),
            age=self._age(client, as_of),
            as_of=as_of,
        ).to_dict() if client else None

        advance_tax = calc.advance_tax_schedule(
            estimated_annual_tax=estimate["result"]["total_tax"]
            + (regime["result"]["new_regime_tax"] if regime else 0.0),
            tax_paid=0.0,
            as_of=as_of,
        ).to_dict()

        return {
            "tax_year": tax_year,
            "financial_year": calc.financial_year(as_of),
            "as_of": as_of.isoformat(),
            "rates": {"marginal": marginal, "long_term_capital_gains": ltcg, "regime": client.tax_regime if client else "new"},
            "realized_gains": realized,
            "tax_estimate": estimate,
            "harvest": harvest,
            "asset_location": location,
            "capital_gains_budget": budget,
            "tax_free_income": round(tax_free_income, 2),
            "opportunities": self.opportunities(household_id, tax_year),
            "nps_annuitization": self.nps_annuitization_status(household_id, tax_year),
            "regime_comparison": regime,
            "advance_tax": advance_tax,
            "charitable_securities": self.charitable_securities(household_id, tax_year),
            "projection": self.projection(household_id, as_of, tax_year),
        }

    def _age(self, client: Client | None, as_of: date) -> int:
        if not client or not client.birth_date:
            return 35
        return as_of.year - client.birth_date.year

    def _estimated_chapter_via_total(self, household_id: str, client: Client | None) -> float:
        """A planning estimate of Chapter VI-A deductions from linked accounts.

        Actual contributions are not itemised per client, so headroom on the
        big-ticket sections (80C via EPF/PPF, 80D) is estimated from account
        presence and typical usage. This keeps the regime comparison useful
        without requiring a separate data-entry flow.
        """
        if not client:
            return 0.0
        accounts = self.db.execute(
            select(Account).where(Account.household_id == household_id, Account.is_liability.is_(False))
        ).scalars().all()
        has_epf = any(a.account_type == "epf" for a in accounts)
        has_ppf = any(a.account_type == "ppf" for a in accounts)
        home_loan = self.db.execute(
            select(Account).where(Account.household_id == household_id, Account.account_type == "home_loan")
        ).scalars().first()

        eighty_c = calc.SECTION_80C_LIMIT if (has_epf or has_ppf) else 0.0
        section_24b = min((home_loan.balance * (home_loan.interest_rate or 0.08)), calc.SECTION_24B_LIMIT) if home_loan else 0.0
        health = calc.SECTION_80D_SELF_LIMIT
        return round(eighty_c + section_24b + health, 2)

    def chapter_via_summary(self, household_id: str, as_of: date) -> dict[str, Any]:
        """Detailed section-by-section Chapter VI-A view for the tax page."""
        client = self._primary_client(household_id)
        accounts = self.db.execute(
            select(Account).where(Account.household_id == household_id, Account.is_liability.is_(False))
        ).scalars().all()
        epf_account = next((a for a in accounts if a.account_type == "epf"), None)
        ppf_account = next((a for a in accounts if a.account_type == "ppf"), None)
        sukanya_account = next((a for a in accounts if a.account_type == "sukanya"), None)
        home_loan = self.db.execute(
            select(Account).where(Account.household_id == household_id, Account.account_type == "home_loan")
        ).scalars().first()

        income = client.annual_income if client else 0.0
        return calc.chapter_via_summary(
            epf_contribution=min(income * 0.06, calc.SECTION_80C_LIMIT) if epf_account else 0.0,
            ppf_contribution=calc.PPF_ANNUAL_LIMIT if ppf_account else 0.0,
            elss_investment=0.0,
            life_insurance_premium=0.0,
            home_loan_principal=0.0,
            sukanya_contribution=calc.SUKANYA_ANNUAL_LIMIT if sukanya_account else 0.0,
            tuition_fees=0.0,
            nps_additional=0.0,
            health_insurance_premium=calc.SECTION_80D_SELF_LIMIT,
            home_loan_interest=min((home_loan.balance * (home_loan.interest_rate or 0.08)), calc.SECTION_24B_LIMIT)
            if home_loan
            else 0.0,
            savings_interest=0.0,
            age=self._age(client, as_of),
            as_of=as_of,
        ).to_dict()

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

    def nps_annuitization_status(self, household_id: str, tax_year: int) -> dict[str, Any]:
        """NPS exit annuitization: at least 40% of the corpus buys an annuity.

        Tracked the way a US platform tracks a required minimum distribution —
        a statutory, deadline-driven event against a retirement account.
        """
        rows = self.db.execute(
            select(NpsAnnuitization)
            .join(Client, NpsAnnuitization.client_id == Client.id)
            .where(Client.household_id == household_id, NpsAnnuitization.tax_year == tax_year)
        ).scalars().all()

        required = sum(r.required_annuity_amount for r in rows)
        purchased = sum(r.annuity_purchased_amount for r in rows)

        return {
            "required_amount": round(required, 2),
            "purchased_amount": round(purchased, 2),
            "remaining": round(max(required - purchased, 0.0), 2),
            "is_required": required > 0,
            "status": "satisfied" if required and purchased >= required else ("pending" if required else "not_applicable"),
            "accounts": [
                {
                    "id": r.id,
                    "account_id": r.account_id,
                    "corpus_at_exit": round(r.corpus_at_exit, 2),
                    "required_annuity_amount": round(r.required_annuity_amount, 2),
                    "annuity_purchased_amount": round(r.annuity_purchased_amount, 2),
                    "exit_deadline": r.exit_deadline.isoformat(),
                    "status": r.status,
                    "annuity_provider": r.annuity_provider,
                }
                for r in rows
            ],
        }

    def regime_comparison(self, household_id: str, as_of: date, gross_income: float | None = None) -> dict[str, Any]:
        """Old vs. new regime — chosen afresh each financial year."""
        client = self._primary_client(household_id)
        income = gross_income if gross_income is not None else (client.annual_income if client else 0.0)
        return calc.compare_regimes(
            gross_income=income,
            deductions=self._estimated_chapter_via_total(household_id, client),
            age=self._age(client, as_of),
            as_of=as_of,
        ).to_dict()

    def charitable_securities(self, household_id: str, tax_year: int) -> list[dict[str, Any]]:
        """Long-term appreciated positions that make efficient charitable gifts under section 80G."""
        rows = self.db.execute(
            select(Holding, Security, Account)
            .join(Security, Holding.security_id == Security.id)
            .join(Account, Holding.account_id == Account.id)
            .where(Account.household_id == household_id, Account.tax_treatment == "taxable")
        ).all()
        _, ltcg = self._rates(household_id)
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
                    "capital_gains_tax_avoided": round(gain * ltcg * (1 + calc.HEALTH_EDUCATION_CESS), 2),
                    "holding_period": "long_term",
                }
            )
        candidates.sort(key=lambda c: c["capital_gains_tax_avoided"], reverse=True)
        return candidates[:8]

    def projection(self, household_id: str, as_of: date, tax_year: int) -> dict[str, Any]:
        """Year-end tax picture: realised to date, plus estimated remaining."""
        client = self._primary_client(household_id)
        marginal, ltcg = self._rates(household_id)
        income = client.annual_income if client else 0.0

        transactions = self.db.execute(
            select(Transaction, Security)
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Security, Transaction.security_id == Security.id)
            .where(Account.household_id == household_id)
        ).all()
        realized = calc.realized_gains(
            [
                {
                    "trade_date": t.trade_date,
                    "realized_gain": t.realized_gain,
                    "is_long_term": t.is_long_term,
                    "asset_class": s.asset_class if s else "indian_equity",
                }
                for t, s in transactions
            ],
            as_of,
        ).result

        gains_tax = calc.estimate_capital_gains_tax(
            equity_stcg=realized["equity_stcg"],
            equity_ltcg=realized["equity_ltcg"],
            other_stcg=realized["other_stcg"],
            other_ltcg=realized["other_ltcg"],
            slab_rate=marginal,
            total_income=income,
            as_of=as_of,
        ).result

        income_tax = calc.slab_tax(
            gross_income=income,
            regime=client.tax_regime if client else "new",
            deductions=self._estimated_chapter_via_total(household_id, client),
            age=self._age(client, as_of),
            as_of=as_of,
        ).result

        return {
            "tax_year": tax_year,
            "financial_year": calc.financial_year(as_of),
            "regime": client.tax_regime if client else "new",
            "estimated_income_tax": income_tax["total_tax"],
            "estimated_capital_gains_tax": gains_tax["total_tax"],
            "estimated_total_tax": round(income_tax["total_tax"] + gains_tax["total_tax"], 2),
            "effective_rate": round(
                (income_tax["total_tax"] + gains_tax["total_tax"]) / income, 4
            ) if income else 0.0,
            "assumptions": [
                "Chapter VI-A deductions are estimated from linked accounts, not itemised entries.",
                "House property income, HRA and other exempt allowances are not modelled.",
            ],
            "limitations": ["A planning estimate only. It is not a computation of your income tax return."],
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
            # Positive for a gain-harvest row, negative for a loss-harvest row.
            "unrealized_loss": round(harvest.unrealized_loss, 2),
            "strategy": "harvest_gain" if harvest.unrealized_loss >= 0 else "harvest_loss",
            "holding_period": harvest.holding_period,
            "estimated_tax_benefit": round(harvest.estimated_tax_benefit, 2),
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
        """Turn an identified loss-harvest opportunity into a reviewable proposal."""
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
            raise ValidationError("This lot holds an unrealised gain, not a loss; it cannot be loss-harvested.")

        marginal, _ = self._rates(household_id)
        period = calc.holding_period(lot.acquired_on, as_of, security.asset_class)
        is_equity = security.asset_class in {"indian_equity", "intl_equity"}
        if is_equity:
            rate = calc.STCG_EQUITY_RATE if period == "short_term" else calc.LTCG_EQUITY_RATE
        else:
            rate = marginal if period == "short_term" else calc.LTCG_OTHER_RATE
        benefit = abs(loss) * rate * (1 + calc.HEALTH_EDUCATION_CESS)

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
            wash_sale_risk="clear",  # India has no wash-sale rule.
            wash_sale_window_ends=None,
            status="proposed",
            tax_year=calc.financial_year_bounds(as_of)[0].year,
            notes=f"Replacement candidate: {replacement.symbol if replacement else 'none identified'}. "
            "India has no wash-sale rule; a repurchase immediately after the sale is permitted.",
        )
        self.db.add(harvest)
        self.db.flush()

        approval = self.approvals.create(
            entity_type=EntityType.HARVEST,
            entity_id=harvest.id,
            title=f"Harvest {security.symbol} loss in {account.name}",
            summary=(
                f"Realise a Rs {abs(loss):,.0f} loss for an estimated Rs {benefit:,.0f} tax benefit, "
                f"replacing with {replacement.symbol if replacement else 'cash'}."
            ),
            household_id=household_id,
            requested_by=actor,
            required_role=Role.TAX_SPECIALIST,
            priority="medium",
            payload={"harvest_id": harvest.id},
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
            summary=(
                "Harvest executed in simulation; no order was sent to a custodian. India has no wash-sale "
                "rule, so the replacement position may be repurchased immediately."
            ),
            before={"status": "approved"},
            after={"status": "executed", "simulated": True},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(harvest)
        return self._serialise_harvest(harvest)
