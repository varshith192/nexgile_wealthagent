"""Estate & trust (§16) and philanthropy (§17)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, AuditService
from app.calculations import institutional as calc
from app.core.constants import ApprovalStatus, EntityType, Role
from app.core.errors import NotFoundError, ValidationError
from app.models.estate import (
    DAF,
    Beneficiary,
    Charity,
    DistributionRequest,
    EstatePlan,
    Gift,
    GivingPlan,
    Grant,
    PowerOfAttorney,
    Trust,
)
from app.models.identity import Client, Household, HouseholdMember, User
from app.models.wealth import Account
from app.workflows.approval_engine import ApprovalEngine

# Account types where a missing beneficiary designation is a real problem.
DESIGNATION_REQUIRED = {"retirement", "trust", "education"}


class EstateService:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.approvals = ApprovalEngine(db, self.audit)

    # -- overview -----------------------------------------------------
    def overview(self, household_id: str, as_of: date) -> dict[str, Any]:
        household = self.db.get(Household, household_id)
        if not household:
            raise NotFoundError("Household not found.")

        accounts = self.db.execute(select(Account).where(Account.household_id == household_id)).scalars().all()
        gross_estate = sum(a.balance for a in accounts if not a.is_liability)
        liabilities = sum(a.balance for a in accounts if a.is_liability)

        client = self.db.execute(
            select(Client).where(Client.household_id == household_id).order_by(Client.created_at)
        ).scalars().first()
        gifts = self.db.execute(select(Gift).where(Gift.household_id == household_id)).scalars().all()
        lifetime_gifts = sum(g.amount for g in gifts if not g.charity_id)
        charitable = sum(g.amount for g in gifts if g.charity_id)

        projection = calc.estate_projection(
            gross_estate=gross_estate,
            liabilities=liabilities,
            lifetime_gifts_used=lifetime_gifts,
            charitable_bequests=charitable,
            is_married=bool(client and client.filing_status == "married_joint"),
            as_of=as_of,
        ).to_dict()

        plans = self.db.execute(select(EstatePlan).where(EstatePlan.household_id == household_id)).scalars().all()
        last_reviewed = max((p.last_reviewed_on for p in plans if p.last_reviewed_on), default=None)

        return {
            "as_of": as_of.isoformat(),
            "household": {"id": household.id, "name": household.name},
            "projection": projection,
            "documents": [
                {
                    "id": p.id,
                    "plan_name": p.plan_name,
                    "document_type": p.document_type,
                    "status": p.status,
                    "executed_on": p.executed_on.isoformat() if p.executed_on else None,
                    "last_reviewed_on": p.last_reviewed_on.isoformat() if p.last_reviewed_on else None,
                    "next_review_due": p.next_review_due.isoformat() if p.next_review_due else None,
                    "attorney": p.attorney,
                    "jurisdiction": p.jurisdiction,
                    "executor": p.executor,
                    "notes": p.notes,
                    "years_since_review": round((as_of - p.last_reviewed_on).days / 365.25, 1)
                    if p.last_reviewed_on
                    else None,
                    "review_overdue": bool(p.next_review_due and p.next_review_due < as_of),
                }
                for p in plans
            ],
            "trusts": self.trusts(household_id),
            "powers_of_attorney": self.powers_of_attorney(household_id),
            "beneficiaries": self.beneficiaries(household_id),
            "beneficiary_gaps": self.beneficiary_gaps(household_id),
            "family_tree": self.family_tree(household_id),
            "distributions": self.distributions(household_id),
            "gifts": self.gift_summary(household_id, as_of),
            "last_reviewed_on": last_reviewed.isoformat() if last_reviewed else None,
            "review_reminders": [
                {
                    "id": p.id,
                    "title": f"{p.plan_name} review",
                    "due": p.next_review_due.isoformat(),
                    "status": "overdue" if p.next_review_due < as_of else "upcoming",
                }
                for p in plans
                if p.next_review_due
            ],
        }

    def trusts(self, household_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(select(Trust).where(Trust.household_id == household_id)).scalars().all()
        return [
            {
                "id": t.id,
                "name": t.name,
                "trust_type": t.trust_type,
                "grantor": t.grantor,
                "trustee": t.trustee,
                "successor_trustee": t.successor_trustee,
                "funded_amount": round(t.funded_amount, 2),
                "is_funded": t.is_funded,
                "established_on": t.established_on.isoformat() if t.established_on else None,
                "situs": t.situs,
                "distribution_standard": t.distribution_standard,
                "status": t.status,
            }
            for t in rows
        ]

    def powers_of_attorney(self, household_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(PowerOfAttorney).where(PowerOfAttorney.household_id == household_id)
        ).scalars().all()
        return [
            {
                "id": p.id,
                "poa_type": p.poa_type,
                "principal": p.principal,
                "agent": p.agent,
                "successor_agent": p.successor_agent,
                "executed_on": p.executed_on.isoformat() if p.executed_on else None,
                "status": p.status,
                "notes": p.notes,
            }
            for p in rows
        ]

    def beneficiaries(self, household_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(Beneficiary).where(Beneficiary.household_id == household_id)
        ).scalars().all()
        result = []
        for b in rows:
            account = self.db.get(Account, b.account_id) if b.account_id else None
            result.append(
                {
                    "id": b.id,
                    "account_id": b.account_id,
                    "account_name": account.name if account else "Trust",
                    "account_type": account.account_type if account else "trust",
                    "trust_id": b.trust_id,
                    "full_name": b.full_name,
                    "relationship_type": b.relationship_type,
                    "designation": b.designation,
                    "percentage": b.percentage,
                    "pending_percentage": b.pending_percentage,
                    "is_charity": b.is_charity,
                    "status": b.status,
                    "approval_id": b.approval_id,
                    "last_confirmed_on": b.last_confirmed_on.isoformat() if b.last_confirmed_on else None,
                }
            )
        return result

    def beneficiary_gaps(self, household_id: str) -> list[dict[str, Any]]:
        """Accounts that require a designation but do not have a valid one."""
        accounts = self.db.execute(
            select(Account).where(
                Account.household_id == household_id, Account.account_type.in_(list(DESIGNATION_REQUIRED))
            )
        ).scalars().all()
        rows = self.db.execute(
            select(Beneficiary).where(Beneficiary.household_id == household_id)
        ).scalars().all()

        totals: dict[str, float] = defaultdict(float)
        for b in rows:
            if b.account_id and b.designation == "primary" and b.status == "completed":
                totals[b.account_id] += b.percentage

        gaps = []
        for account in accounts:
            total = totals.get(account.id, 0.0)
            if total == 0:
                reason = "No primary beneficiary on file"
            elif abs(total - 100.0) > 0.01:
                reason = f"Primary designations total {total:.0f}% rather than 100%"
            else:
                continue
            gaps.append(
                {
                    "account_id": account.id,
                    "account_name": account.name,
                    "account_type": account.account_type,
                    "balance": round(account.balance, 2),
                    "reason": reason,
                    "current_total": total,
                }
            )
        return gaps

    def family_tree(self, household_id: str) -> dict[str, Any]:
        household = self.db.get(Household, household_id)
        clients = self.db.execute(select(Client).where(Client.household_id == household_id)).scalars().all()
        members = self.db.execute(
            select(HouseholdMember).where(HouseholdMember.household_id == household_id)
        ).scalars().all()
        return {
            "household": household.name if household else "",
            "principals": [
                {"id": c.id, "name": c.full_name, "birth_date": c.birth_date.isoformat() if c.birth_date else None}
                for c in clients
            ],
            "members": [
                {
                    "id": m.id,
                    "name": m.full_name,
                    "relationship": m.relationship_type,
                    "birth_date": m.birth_date.isoformat() if m.birth_date else None,
                    "is_dependent": m.is_dependent,
                }
                for m in members
            ],
        }

    def distributions(self, household_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(DistributionRequest)
            .where(DistributionRequest.household_id == household_id)
            .order_by(DistributionRequest.requested_on.desc())
        ).scalars().all()
        return [
            {
                "id": d.id,
                "account_id": d.account_id,
                "trust_id": d.trust_id,
                "requested_by": d.requested_by,
                "beneficiary_name": d.beneficiary_name,
                "amount": round(d.amount, 2),
                "purpose": d.purpose,
                "distribution_type": d.distribution_type,
                "requested_on": d.requested_on.isoformat(),
                "status": d.status,
                "approval_id": d.approval_id,
                "tax_withholding": round(d.tax_withholding, 2),
                "notes": d.notes,
            }
            for d in rows
        ]

    def gift_summary(self, household_id: str, as_of: date) -> dict[str, Any]:
        gifts = self.db.execute(select(Gift).where(Gift.household_id == household_id)).scalars().all()
        client = self.db.execute(
            select(Client).where(Client.household_id == household_id).order_by(Client.created_at)
        ).scalars().first()
        usage = calc.gift_exclusion_usage(
            [
                {
                    "recipient": g.recipient,
                    "amount": g.amount,
                    "tax_year": g.tax_year,
                    "is_charity": bool(g.charity_id),
                }
                for g in gifts
            ],
            as_of.year,
            bool(client and client.filing_status == "married_joint"),
            as_of,
        ).to_dict()

        return {
            "usage": usage,
            "gifts": [
                {
                    "id": g.id,
                    "recipient": g.recipient,
                    "gift_type": g.gift_type,
                    "amount": round(g.amount, 2),
                    "gifted_on": g.gifted_on.isoformat(),
                    "tax_year": g.tax_year,
                    "is_qcd": g.is_qcd,
                    "deduction_amount": round(g.deduction_amount, 2),
                    "capital_gain_avoided": round(g.capital_gain_avoided, 2),
                    "notes": g.notes,
                }
                for g in sorted(gifts, key=lambda g: g.gifted_on, reverse=True)
            ],
        }

    # -- beneficiary workflow (§16) -----------------------------------
    def propose_beneficiary_change(
        self, household_id: str, beneficiary_id: str, new_percentage: float, actor: User, note: str | None = None
    ) -> dict[str, Any]:
        """Draft -> Review -> Approval -> Completed."""
        beneficiary = self.db.get(Beneficiary, beneficiary_id)
        if not beneficiary or beneficiary.household_id != household_id:
            raise NotFoundError("Beneficiary designation not found.")
        if not 0 <= new_percentage <= 100:
            raise ValidationError("A designation percentage must be between 0 and 100.")

        before = {"percentage": beneficiary.percentage, "status": beneficiary.status}
        beneficiary.pending_percentage = new_percentage
        beneficiary.status = "draft"
        self.db.flush()

        account = self.db.get(Account, beneficiary.account_id) if beneficiary.account_id else None
        approval = self.approvals.create(
            entity_type=EntityType.BENEFICIARY,
            entity_id=beneficiary.id,
            title=f"Beneficiary change: {beneficiary.full_name}",
            summary=(
                f"Change {beneficiary.full_name} from {beneficiary.percentage:.0f}% to {new_percentage:.0f}% on "
                f"{account.name if account else 'the trust'}."
            ),
            household_id=household_id,
            requested_by=actor,
            required_role=Role.ESTATE_TRUST,
            priority="high",
            payload={"beneficiary_id": beneficiary.id, "from": beneficiary.percentage, "to": new_percentage, "note": note},
            status=ApprovalStatus.DRAFT,
            commit=False,
        )
        beneficiary.approval_id = approval.id

        self.audit.record(
            action=AuditAction.BENEFICIARY_CHANGE,
            entity_type=EntityType.BENEFICIARY,
            entity_id=beneficiary.id,
            entity_label=beneficiary.full_name,
            actor=actor,
            household_id=household_id,
            summary="Beneficiary change drafted and routed for review",
            before=before,
            after={"pending_percentage": new_percentage, "status": "draft"},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(beneficiary)
        return {"beneficiary_id": beneficiary.id, "approval_id": approval.id, "status": beneficiary.status}


class PhilanthropyService:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)

    def overview(self, household_id: str, as_of: date) -> dict[str, Any]:
        vehicles = self.db.execute(select(DAF).where(DAF.household_id == household_id)).scalars().all()
        vehicle_ids = [v.id for v in vehicles]

        grants = (
            self.db.execute(
                select(Grant, Charity)
                .join(Charity, Grant.charity_id == Charity.id)
                .where(Grant.daf_id.in_(vehicle_ids))
                .order_by(Grant.granted_on.desc())
            ).all()
            if vehicle_ids
            else []
        )

        gifts = self.db.execute(select(Gift).where(Gift.household_id == household_id)).scalars().all()
        client = self.db.execute(
            select(Client).where(Client.household_id == household_id).order_by(Client.created_at)
        ).scalars().first()

        charitable_gifts = [g for g in gifts if g.charity_id or g.is_qcd]
        cash_gifts = sum(g.amount for g in charitable_gifts if g.gift_type == "cash")
        appreciated = [g for g in charitable_gifts if g.gift_type == "securities"]
        appreciated_fmv = sum(g.amount for g in appreciated)
        appreciated_basis = sum(g.cost_basis or 0.0 for g in appreciated)

        deduction = calc.charitable_deduction(
            cash_gifts=cash_gifts,
            appreciated_gifts_fmv=appreciated_fmv,
            appreciated_cost_basis=appreciated_basis,
            adjusted_gross_income=client.annual_income if client else 500_000.0,
            marginal_rate=client.marginal_tax_rate if client else 0.35,
            ltcg_rate=client.ltcg_tax_rate if client else 0.20,
            as_of=as_of,
        ).to_dict()

        by_mission: dict[str, float] = defaultdict(float)
        for grant, charity in grants:
            by_mission[charity.mission_area] += grant.amount

        plans = self.db.execute(
            select(GivingPlan).where(GivingPlan.household_id == household_id)
        ).scalars().all()

        return {
            "as_of": as_of.isoformat(),
            "summary": {
                "total_balance": round(sum(v.balance for v in vehicles), 2),
                "contributed_ytd": round(sum(v.contributed_ytd for v in vehicles), 2),
                "granted_ytd": round(sum(v.granted_ytd for v in vehicles), 2),
                "annual_grant_target": round(sum(v.annual_grant_target for v in vehicles), 2),
                "grant_count": len(grants),
                "charities_supported": len({c.id for _, c in grants}),
                "qcd_total": round(sum(g.amount for g in gifts if g.is_qcd), 2),
            },
            "vehicles": [
                {
                    "id": v.id,
                    "name": v.name,
                    "vehicle_type": v.vehicle_type,
                    "sponsor_organisation": v.sponsor_organisation,
                    "balance": round(v.balance, 2),
                    "contributed_ytd": round(v.contributed_ytd, 2),
                    "granted_ytd": round(v.granted_ytd, 2),
                    "annual_grant_target": round(v.annual_grant_target, 2),
                    "payout_requirement": v.payout_requirement,
                    "established_on": v.established_on.isoformat() if v.established_on else None,
                    "status": v.status,
                    "pacing": round(v.granted_ytd / v.annual_grant_target, 4) if v.annual_grant_target else 0.0,
                }
                for v in vehicles
            ],
            "grants": [
                {
                    "id": g.id,
                    "charity": c.name,
                    "mission_area": c.mission_area,
                    "location": c.location,
                    "amount": round(g.amount, 2),
                    "granted_on": g.granted_on.isoformat(),
                    "purpose": g.purpose,
                    "is_recurring": g.is_recurring,
                    "status": g.status,
                    "impact_note": g.impact_note,
                }
                for g, c in grants
            ],
            "mission_breakdown": [
                {"mission_area": area, "amount": round(amount, 2)}
                for area, amount in sorted(by_mission.items(), key=lambda kv: kv[1], reverse=True)
            ],
            "deduction_impact": deduction,
            "giving_plans": [
                {
                    "id": p.id,
                    "name": p.name,
                    "tax_year": p.tax_year,
                    "target_amount": round(p.target_amount, 2),
                    "committed_amount": round(p.committed_amount, 2),
                    "progress": round(p.committed_amount / p.target_amount, 4) if p.target_amount else 0.0,
                    "mission_focus": p.mission_focus,
                    "strategy": p.strategy,
                    "status": p.status,
                    "review_date": p.review_date.isoformat() if p.review_date else None,
                }
                for p in plans
            ],
            "qcds": [
                {
                    "id": g.id,
                    "recipient": g.recipient,
                    "amount": round(g.amount, 2),
                    "gifted_on": g.gifted_on.isoformat(),
                    "tax_year": g.tax_year,
                }
                for g in gifts
                if g.is_qcd
            ],
        }
