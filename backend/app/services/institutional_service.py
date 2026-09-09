"""Institutional workspace (§29-§35): sponsor, fiduciary, compliance, fees,
participant portal, retirement readiness and education.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, AuditService
from app.calculations import institutional as calc
from app.calculations import retirement as ret_calc
from app.core.constants import ComplianceStatus, EntityType
from app.core.errors import NotFoundError, ValidationError
from app.models.identity import User
from app.models.institutional import (
    ComplianceTest,
    Contribution,
    EducationContent,
    EducationProgress,
    Fee,
    FiduciaryReview,
    Filing,
    InvestmentOption,
    Participant,
    ParticipantLoan,
    Plan,
    Sponsor,
)


class InstitutionalService:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)

    # -- plans --------------------------------------------------------
    def plans(self) -> list[dict[str, Any]]:
        rows = self.db.execute(select(Plan).order_by(Plan.name)).scalars().all()
        return [self.serialise_plan(p) for p in rows]

    def get_plan(self, plan_id: str | None = None) -> Plan:
        if plan_id:
            plan = self.db.get(Plan, plan_id)
        else:
            plan = self.db.execute(select(Plan).order_by(Plan.name)).scalars().first()
        if not plan:
            raise NotFoundError("Plan not found.")
        return plan

    def serialise_plan(self, plan: Plan) -> dict[str, Any]:
        sponsor = self.db.get(Sponsor, plan.sponsor_id)
        return {
            "id": plan.id,
            "name": plan.name,
            "plan_number": plan.plan_number,
            "plan_type": plan.plan_type,
            "sponsor": sponsor.name if sponsor else "—",
            "sponsor_id": plan.sponsor_id,
            "industry": sponsor.industry if sponsor else None,
            "plan_year_end": plan.plan_year_end.isoformat(),
            "total_assets": round(plan.total_assets, 2),
            "eligible_employees": plan.eligible_employees,
            "participating_employees": plan.participating_employees,
            "participation_rate": round(plan.participating_employees / plan.eligible_employees, 4)
            if plan.eligible_employees
            else 0.0,
            "average_deferral_rate": plan.average_deferral_rate,
            "employer_match_formula": plan.employer_match_formula,
            "vesting_schedule": plan.vesting_schedule,
            "auto_enrollment": plan.auto_enrollment,
            "auto_enrollment_rate": plan.auto_enrollment_rate,
            "auto_escalation": plan.auto_escalation,
            "auto_escalation_cap": plan.auto_escalation_cap,
            "loans_allowed": plan.loans_allowed,
            "hardship_allowed": plan.hardship_allowed,
            "recordkeeper": plan.recordkeeper,
            "status": plan.status,
        }

    def sponsor_dashboard(self, plan_id: str | None, as_of: date) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        participants = self.db.execute(
            select(Participant).where(Participant.plan_id == plan.id)
        ).scalars().all()
        loans = self.db.execute(
            select(ParticipantLoan).join(Participant, ParticipantLoan.participant_id == Participant.id)
            .where(Participant.plan_id == plan.id)
        ).scalars().all()

        active = [p for p in participants if p.status == "active"]
        total_balance = sum(p.account_balance for p in participants)
        avg_balance = total_balance / len(participants) if participants else 0.0
        with_beneficiary = sum(1 for p in participants if p.has_beneficiary)

        health = calc.plan_health(
            eligible_employees=plan.eligible_employees,
            enrolled_employees=plan.participating_employees,
            average_contribution_rate=plan.average_deferral_rate,
            average_balance=avg_balance,
            members_with_nomination=with_beneficiary,
            uan_seeded=sum(1 for p in participants if p.is_auto_enrolled),
            nps_corporate_offered=plan.plan_type in {"epf_nps", "nps"},
            voluntary_pf_offered=True,
            as_of=as_of,
        ).to_dict()

        contributions = self.db.execute(
            select(Contribution).where(Contribution.plan_id == plan.id, Contribution.tax_year == as_of.year)
        ).scalars().all()

        return {
            "plan": self.serialise_plan(plan),
            "as_of": as_of.isoformat(),
            "health": health,
            "metrics": {
                "total_assets": round(plan.total_assets, 2),
                "participant_count": len(participants),
                "active_participants": len(active),
                "average_balance": round(avg_balance, 2),
                "median_balance": round(
                    sorted(p.account_balance for p in participants)[len(participants) // 2], 2
                )
                if participants
                else 0.0,
                "average_deferral_rate": plan.average_deferral_rate,
                "vpf_adoption": round(
                    sum(1 for p in participants if p.vpf_contribution_rate > 0) / len(participants), 4
                )
                if participants
                else 0.0,
                "employer_contributions_ytd": round(
                    sum(c.employer_match + c.employer_profit_sharing for c in contributions), 2
                ),
                "employee_contributions_ytd": round(
                    sum(c.employee_pretax + c.employee_vpf + c.employee_catchup for c in contributions), 2
                ),
                "loans_outstanding": len([l for l in loans if l.status == "current"]),
                "loan_balance": round(sum(l.outstanding_balance for l in loans), 2),
                "hardship_count": sum(1 for l in loans if l.loan_type == "hardship"),
                "nomination_coverage": round(with_beneficiary / len(participants), 4) if participants else 0.0,
                "auto_enrolled": sum(1 for p in participants if p.is_auto_enrolled),
                "average_engagement": round(
                    sum(p.engagement_score for p in participants) / len(participants), 3
                )
                if participants
                else 0.0,
                # "Excluded employee" is the EPF Act term for a member whose wage
                # at joining exceeded the statutory ceiling, for whom EPF is optional.
                "excluded_employee_count": sum(1 for p in participants if p.is_hce),
                "fully_vested": sum(1 for p in participants if p.vested_percentage >= 1.0),
            },
            "vesting_distribution": self._vesting_distribution(participants),
            "deferral_distribution": self._deferral_distribution(participants),
            "compliance_summary": self.compliance_summary(plan.id, as_of),
        }

    def _vesting_distribution(self, participants: Sequence[Participant]) -> list[dict[str, Any]]:
        buckets = {"0%": 0, "1-49%": 0, "50-99%": 0, "100%": 0}
        for p in participants:
            v = p.vested_percentage
            if v <= 0:
                buckets["0%"] += 1
            elif v < 0.5:
                buckets["1-49%"] += 1
            elif v < 1.0:
                buckets["50-99%"] += 1
            else:
                buckets["100%"] += 1
        return [{"bucket": k, "count": v} for k, v in buckets.items()]

    def _deferral_distribution(self, participants: Sequence[Participant]) -> list[dict[str, Any]]:
        buckets = {"0%": 0, "1-3%": 0, "4-6%": 0, "7-10%": 0, "10%+": 0}
        for p in participants:
            rate = p.deferral_rate
            if rate <= 0:
                buckets["0%"] += 1
            elif rate <= 0.03:
                buckets["1-3%"] += 1
            elif rate <= 0.06:
                buckets["4-6%"] += 1
            elif rate <= 0.10:
                buckets["7-10%"] += 1
            else:
                buckets["10%+"] += 1
        return [{"bucket": k, "count": v} for k, v in buckets.items()]

    # -- participants -------------------------------------------------
    def participants(
        self,
        plan_id: str | None = None,
        *,
        search: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        stmt = select(Participant).where(Participant.plan_id == plan.id)
        if status:
            stmt = stmt.where(Participant.status == status)
        rows = list(self.db.execute(stmt.order_by(Participant.full_name)).scalars().all())
        if search:
            needle = search.lower()
            rows = [r for r in rows if needle in r.full_name.lower()]

        total = len(rows)
        start = max(page - 1, 0) * page_size
        return {
            "participants": [self.serialise_participant(p) for p in rows[start : start + page_size]],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max((total + page_size - 1) // page_size, 1),
            "plan": self.serialise_plan(plan),
        }

    def serialise_participant(self, p: Participant) -> dict[str, Any]:
        return {
            "id": p.id,
            "full_name": p.full_name,
            "employee_id_masked": p.employee_id_masked,
            "age": date.today().year - p.birth_date.year,
            "hire_date": p.hire_date.isoformat(),
            "years_of_service": round((date.today() - p.hire_date).days / 365.25, 1),
            "annual_salary": round(p.annual_salary, 2),
            "deferral_rate": p.deferral_rate,
            "vpf_contribution_rate": p.vpf_contribution_rate,
            "account_balance": round(p.account_balance, 2),
            "vpf_balance": round(p.vpf_balance, 2),
            "employer_balance": round(p.employer_balance, 2),
            "vested_percentage": p.vested_percentage,
            "is_excluded_employee": p.is_hce,
            "is_auto_enrolled": p.is_auto_enrolled,
            "has_beneficiary": p.has_beneficiary,
            "retirement_age": p.retirement_age,
            "status": p.status,
            "engagement_score": p.engagement_score,
        }

    def participant_portal(self, user: User, as_of: date) -> dict[str, Any]:
        participant = self.db.execute(
            select(Participant).where(Participant.user_id == user.id)
        ).scalars().first()
        if not participant:
            participant = self.db.execute(select(Participant).order_by(Participant.full_name)).scalars().first()
        if not participant:
            raise NotFoundError("No participant record is linked to this account.")

        plan = self.db.get(Plan, participant.plan_id)
        contributions = self.db.execute(
            select(Contribution)
            .where(Contribution.participant_id == participant.id)
            .order_by(Contribution.period_end.desc())
            .limit(24)
        ).scalars().all()
        loans = self.db.execute(
            select(ParticipantLoan).where(ParticipantLoan.participant_id == participant.id)
        ).scalars().all()
        options = self.db.execute(
            select(InvestmentOption).where(InvestmentOption.plan_id == plan.id)
        ).scalars().all()

        age = as_of.year - participant.birth_date.year
        ytd = [c for c in contributions if c.tax_year == as_of.year]
        ytd_deferral = sum(c.employee_pretax + c.employee_vpf + c.employee_catchup for c in ytd)
        monthly_basic = participant.annual_salary / 12 * 0.5  # basic pay is typically ~50% of CTC

        capacity = ret_calc.contribution_capacity(
            age=age,
            monthly_basic=monthly_basic,
            epf_rate=participant.deferral_rate,
            ppf_contributed=0.0,
            nps_contributed=0.0,
            elss_contributed=0.0,
            as_of=as_of,
        ).to_dict()

        vesting = ret_calc.vesting_status(hire_date=participant.hire_date, as_of=as_of).to_dict()

        readiness = self.retirement_readiness(participant.id, as_of)

        return {
            "participant": self.serialise_participant(participant),
            "plan": self.serialise_plan(plan),
            "as_of": as_of.isoformat(),
            "contributions": {
                "ytd_employee": round(ytd_deferral, 2),
                "ytd_employer": round(sum(c.employer_match + c.employer_profit_sharing for c in ytd), 2),
                "history": [
                    {
                        "period_end": c.period_end.isoformat(),
                        "employee_pretax": round(c.employee_pretax, 2),
                        "employee_vpf": round(c.employee_vpf, 2),
                        "employee_catchup": round(c.employee_catchup, 2),
                        "employer_match": round(c.employer_match, 2),
                        "employer_profit_sharing": round(c.employer_profit_sharing, 2),
                        "total": round(
                            c.employee_pretax
                            + c.employee_vpf
                            + c.employee_catchup
                            + c.employer_match
                            + c.employer_profit_sharing,
                            2,
                        ),
                    }
                    for c in reversed(contributions)
                ],
                "capacity": capacity,
            },
            "vesting": vesting,
            "loans": [
                {
                    "id": l.id,
                    "original_amount": round(l.original_amount, 2),
                    "outstanding_balance": round(l.outstanding_balance, 2),
                    "interest_rate": l.interest_rate,
                    "term_months": l.term_months,
                    "payment_amount": round(l.payment_amount, 2),
                    "issued_on": l.issued_on.isoformat(),
                    "matures_on": l.matures_on.isoformat(),
                    "loan_type": l.loan_type,
                    "status": l.status,
                }
                for l in loans
            ],
            "investments": [
                {
                    "id": o.id,
                    "name": o.name,
                    "ticker": o.ticker,
                    "asset_category": o.asset_category,
                    "expense_ratio": o.expense_ratio,
                    "three_year_return": o.three_year_return,
                    "five_year_return": o.five_year_return,
                    "is_default_scheme": o.is_default_scheme,
                    "ips_status": o.ips_status,
                }
                for o in options
            ],
            "readiness": readiness,
            "beneficiaries": {
                "has_beneficiary": participant.has_beneficiary,
                "note": "Confirm your designation each year and after any life event.",
            },
            "education": self.education_for_participant(participant.id),
        }

    def retirement_readiness(
        self, participant_id: str, as_of: date, overrides: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        participant = self.db.get(Participant, participant_id)
        if not participant:
            raise NotFoundError("Participant not found.")
        plan = self.db.get(Plan, participant.plan_id)
        overrides = overrides or {}

        age = int(overrides.get("current_age") or (as_of.year - participant.birth_date.year))
        retirement_age = int(overrides.get("retirement_age") or participant.retirement_age)
        salary = overrides.get("annual_income") or participant.annual_salary
        deferral = overrides.get("deferral_rate")
        deferral = deferral if deferral is not None else participant.deferral_rate + participant.vpf_contribution_rate
        monthly_basic = salary / 12 * 0.5  # basic pay is typically ~50% of CTC
        annual_contribution = monthly_basic * 12 * deferral
        expected_return = overrides.get("expected_return", 0.08)

        years_of_service_now = (as_of - participant.hire_date).days / 365.25
        service_at_retirement = years_of_service_now + max(retirement_age - age, 0)
        employer_contribution = overrides.get(
            "employer_contribution", monthly_basic * 12 * ret_calc.EPF_EMPLOYER_RATE
        )
        eps_pension_annual = overrides.get(
            "eps_pension_annual",
            ret_calc.eps_pension(
                pensionable_salary=monthly_basic, pensionable_service=int(service_at_retirement), as_of=as_of
            ).result["annual_pension"],
        )

        def run_projection(
            current_savings: float, contribution: float, employer: float, rate: float, ret_age: int
        ) -> dict[str, Any]:
            return ret_calc.retirement_projection(
                current_age=age,
                retirement_age=ret_age,
                current_savings=current_savings,
                annual_contribution=contribution,
                employer_contribution=employer,
                expected_return=rate,
                current_income=salary,
                eps_pension_annual=eps_pension_annual,
                nps_annuity_annual=overrides.get("nps_annuity_annual", 0.0),
                rental_income_annual=overrides.get("rental_income_annual", 0.0),
                healthcare_annual=overrides.get("healthcare_annual", 1_00_000.0),
                inflation=overrides.get("inflation", 0.06),
                as_of=as_of,
            ).result

        current_savings = overrides.get("current_savings", participant.account_balance)
        base_result = run_projection(current_savings, annual_contribution, employer_contribution, expected_return, retirement_age)
        projection = {"result": base_result}

        monte_carlo = ret_calc.monte_carlo_projection(
            starting_balance=current_savings,
            annual_contribution=annual_contribution + employer_contribution,
            years=max(retirement_age - age, 1),
            expected_return=expected_return,
            volatility=overrides.get("volatility", 0.13),
            as_of=as_of,
            trials=1000,
            success_threshold=base_result["required_corpus"],
        ).to_dict()

        scenarios = [{"label": "Base case", **base_result, "is_baseline": True}]
        for label, alt_deferral, alt_retirement_age, alt_return in (
            ("Contribute 2% more", deferral + 0.02, retirement_age, expected_return),
            ("Retire 3 years later", deferral, retirement_age + 3, expected_return),
            ("Returns 1.5% lower", deferral, retirement_age, expected_return - 0.015),
        ):
            alt_contribution = monthly_basic * 12 * alt_deferral
            alt_result = run_projection(current_savings, alt_contribution, employer_contribution, alt_return, alt_retirement_age)
            scenarios.append({"label": label, **alt_result, "is_baseline": False})

        return {
            "projection": projection,
            "monte_carlo": monte_carlo,
            "scenarios": scenarios,
            "inputs": {
                "current_age": age,
                "retirement_age": retirement_age,
                "annual_income": round(salary, 2),
                "deferral_rate": deferral,
                "current_savings": round(current_savings, 2),
                "eps_pension_annual": round(eps_pension_annual, 2),
                "employer_match_formula": plan.employer_match_formula if plan else None,
                "expected_return": expected_return,
            },
        }

    # -- fiduciary + compliance ---------------------------------------
    def investment_lineup(self, plan_id: str | None, as_of: date) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        options = self.db.execute(
            select(InvestmentOption).where(InvestmentOption.plan_id == plan.id)
        ).scalars().all()
        monitor = calc.scheme_monitor(
            [
                {
                    "id": o.id,
                    "name": o.name,
                    "ticker": o.ticker,
                    "asset_category": o.asset_category,
                    "three_year_return": o.three_year_return,
                    "five_year_return": o.five_year_return,
                    "benchmark_three_year": o.benchmark_three_year,
                    "peer_rank_percentile": o.peer_rank_percentile,
                    "expense_ratio": o.expense_ratio,
                    "category_median_expense": o.category_median_expense,
                    "plan_assets": o.plan_assets,
                    "participants_invested": o.participants_invested,
                    "is_qdia": o.is_default_scheme,
                }
                for o in options
            ],
            as_of,
        ).to_dict()

        # Keep the stored status in step with the screen result.
        by_id = {o.id: o for o in options}
        for row in monitor["result"]["options"]:
            option = by_id.get(row["id"])
            if option and option.ips_status != row["ips_status"]:
                option.ips_status = row["ips_status"]
                option.watch_reason = "; ".join(row["reasons"]) or None
        if options:
            self.db.commit()

        reviews = self.db.execute(
            select(FiduciaryReview).where(FiduciaryReview.plan_id == plan.id).order_by(FiduciaryReview.held_on.desc())
        ).scalars().all()

        return {
            "plan": self.serialise_plan(plan),
            "as_of": as_of.isoformat(),
            "monitor": monitor,
            "reviews": [
                {
                    "id": r.id,
                    "title": r.title,
                    "review_period": r.review_period,
                    "held_on": r.held_on.isoformat(),
                    "attendees": r.attendees,
                    "agenda": r.agenda,
                    "minutes": r.minutes,
                    "decisions": r.decisions,
                    "funds_on_watch": r.funds_on_watch,
                    "ips_compliant": r.ips_compliant,
                    "status": r.status,
                }
                for r in reviews
            ],
        }

    def compliance_summary(self, plan_id: str | None, as_of: date) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        tests = self.db.execute(
            select(ComplianceTest).where(ComplianceTest.plan_id == plan.id).order_by(ComplianceTest.due_date)
        ).scalars().all()
        filings = self.db.execute(
            select(Filing).where(Filing.plan_id == plan.id).order_by(Filing.due_date)
        ).scalars().all()

        def status_of(due: date | None, completed: date | None) -> str:
            if completed:
                return ComplianceStatus.COMPLETE
            if not due:
                return ComplianceStatus.PENDING
            if due < as_of:
                return ComplianceStatus.OVERDUE
            if (due - as_of).days <= 45:
                return ComplianceStatus.AT_RISK
            return ComplianceStatus.PENDING

        test_rows = [
            {
                "id": t.id,
                "test_type": t.test_type,
                "tax_year": t.tax_year,
                "hce_value": t.hce_value,
                "nhce_value": t.nhce_value,
                "threshold": t.threshold,
                "result": t.result,
                "status": str(status_of(t.due_date, t.completed_on)),
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "completed_on": t.completed_on.isoformat() if t.completed_on else None,
                "corrective_action": t.corrective_action,
                "method": t.method,
                "has_evidence": bool(t.evidence_document_id),
            }
            for t in tests
        ]
        filing_rows = [
            {
                "id": f.id,
                "filing_type": f.filing_type,
                "tax_year": f.tax_year,
                "due_date": f.due_date.isoformat(),
                "extended_due_date": f.extended_due_date.isoformat() if f.extended_due_date else None,
                "filed_on": f.filed_on.isoformat() if f.filed_on else None,
                "status": str(status_of(f.extended_due_date or f.due_date, f.filed_on)),
                "preparer": f.preparer,
                "auditor": f.auditor,
                "notes": f.notes,
            }
            for f in filings
        ]

        all_statuses = [r["status"] for r in test_rows + filing_rows]
        return {
            "plan_id": plan.id,
            "as_of": as_of.isoformat(),
            "tests": test_rows,
            "filings": filing_rows,
            "counts": {
                str(status): sum(1 for s in all_statuses if s == str(status)) for status in ComplianceStatus
            },
            "next_deadline": min(
                (r["due_date"] for r in test_rows + filing_rows if r["due_date"] and r["status"] != "complete"),
                default=None,
            ),
        }

    def run_compliance_test(self, test_id: str, actor: User, as_of: date) -> dict[str, Any]:
        test = self.db.get(ComplianceTest, test_id)
        if not test:
            raise NotFoundError("Compliance test not found.")

        participants = self.db.execute(
            select(Participant).where(Participant.plan_id == test.plan_id)
        ).scalars().all()
        key = test.test_type.lower()

        if "epf" in key or "contribution" in key:
            total_wages = sum(p.annual_salary * 0.5 for p in participants)  # basic ~ 50% of CTC
            employee_remitted = total_wages * calc.EPF_EMPLOYEE_RATE
            eps_remitted = (
                min(total_wages, calc.EPF_WAGE_CEILING_MONTHLY * 12 * len(participants)) * calc.EPS_DIVERSION_RATE
                if participants
                else 0.0
            )
            employer_remitted = total_wages * calc.EPF_EMPLOYER_RATE - eps_remitted
            result = calc.epf_contribution_check(
                total_wages=total_wages,
                employee_remitted=employee_remitted,
                employer_remitted=employer_remitted,
                eps_remitted=eps_remitted,
                member_count=len(participants),
                as_of=as_of,
            )
            result_value = result.result["result"]
            corrective_action = result.result.get("corrective_action")
        elif "nomination" in key:
            result = calc.nomination_coverage(
                [
                    {
                        "id": p.id,
                        "full_name": p.full_name,
                        "balance": p.account_balance,
                        "has_nomination": p.has_beneficiary,
                    }
                    for p in participants
                ],
                as_of,
            )
            coverage = result.result["nomination_coverage"]
            result_value = "pass" if coverage >= 0.90 else "fail"
            corrective_action = (
                None
                if coverage >= 0.90
                else f"Follow up with the {result.result['members_without_nomination']} member(s) without a nomination on file."
            )
        else:
            raise ValidationError(f"No automated calculation exists for the {test.test_type} test.")

        before = {"result": test.result, "status": test.status}
        test.result = result_value
        test.status = str(ComplianceStatus.COMPLETE)
        test.completed_on = as_of
        test.corrective_action = corrective_action

        self.audit.record(
            action=AuditAction.COMPLIANCE_ACTION,
            entity_type=EntityType.COMPLIANCE_TEST,
            entity_id=test.id,
            entity_label=f"{test.test_type} {test.tax_year}",
            actor=actor,
            summary=f"{test.test_type} test run: {test.result}",
            before=before,
            after={"result": test.result, "status": test.status},
            commit=False,
        )
        self.db.commit()
        return {"test_id": test.id, "calculation": result.to_dict()}

    # -- fees ---------------------------------------------------------
    def fee_review(self, plan_id: str | None, as_of: date) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        fees = self.db.execute(select(Fee).where(Fee.plan_id == plan.id)).scalars().all()
        options = self.db.execute(
            select(InvestmentOption).where(InvestmentOption.plan_id == plan.id)
        ).scalars().all()

        benchmark = calc.fee_benchmark(
            [
                {
                    "vendor": f.vendor,
                    "fee_type": f.fee_type,
                    "payer": f.payer,
                    "annual_amount": f.annual_amount,
                    "basis_points": f.basis_points,
                    "benchmark_basis_points": f.benchmark_basis_points,
                    "revenue_sharing": f.revenue_sharing,
                }
                for f in fees
            ],
            plan.total_assets,
            plan.participating_employees,
            as_of,
        ).to_dict()

        weighted_expense = (
            sum(o.expense_ratio * o.plan_assets for o in options) / sum(o.plan_assets for o in options)
            if options and sum(o.plan_assets for o in options)
            else 0.0
        )

        return {
            "plan": self.serialise_plan(plan),
            "as_of": as_of.isoformat(),
            "benchmark": benchmark,
            "investment_costs": {
                "weighted_expense_ratio": round(weighted_expense, 5),
                "total_revenue_sharing": round(
                    sum(o.revenue_share_bps / 10_000 * o.plan_assets for o in options), 2
                ),
                "options": [
                    {
                        "name": o.name,
                        "ticker": o.ticker,
                        "expense_ratio": o.expense_ratio,
                        "category_median_expense": o.category_median_expense,
                        "plan_assets": round(o.plan_assets, 2),
                        "revenue_share_bps": o.revenue_share_bps,
                        "above_median": o.expense_ratio > o.category_median_expense,
                    }
                    for o in sorted(options, key=lambda o: o.plan_assets, reverse=True)
                ],
            },
            "vendors": [
                {
                    "id": f.id,
                    "vendor": f.vendor,
                    "fee_type": f.fee_type,
                    "payer": f.payer,
                    "annual_amount": round(f.annual_amount, 2),
                    "per_participant_amount": round(f.per_participant_amount, 2),
                    "basis_points": f.basis_points,
                    "benchmark_basis_points": f.benchmark_basis_points,
                    "contract_end": f.contract_end.isoformat() if f.contract_end else None,
                    "sla_score": f.sla_score,
                    "notes": f.notes,
                }
                for f in fees
            ],
        }

    # -- education ----------------------------------------------------
    def education_catalogue(self) -> list[dict[str, Any]]:
        rows = self.db.execute(select(EducationContent).order_by(EducationContent.learning_path)).scalars().all()
        return [
            {
                "id": c.id,
                "title": c.title,
                "content_type": c.content_type,
                "learning_path": c.learning_path,
                "level": c.level,
                "duration_minutes": c.duration_minutes,
                "summary": c.summary,
                "body": c.body,
                "tags": c.tags,
                "published_on": c.published_on.isoformat() if c.published_on else None,
            }
            for c in rows
        ]

    def education_for_participant(self, participant_id: str) -> dict[str, Any]:
        catalogue = self.education_catalogue()
        progress = self.db.execute(
            select(EducationProgress).where(EducationProgress.participant_id == participant_id)
        ).scalars().all()
        by_content = {p.content_id: p for p in progress}

        items = []
        for entry in catalogue:
            record = by_content.get(entry["id"])
            items.append(
                {
                    **entry,
                    "status": record.status if record else "not_started",
                    "progress_percent": record.progress_percent if record else 0.0,
                    "score": record.score if record else None,
                    "completed_at": record.completed_at.isoformat() if record and record.completed_at else None,
                }
            )

        paths: dict[str, dict[str, Any]] = {}
        for item in items:
            path = paths.setdefault(
                item["learning_path"], {"learning_path": item["learning_path"], "total": 0, "completed": 0}
            )
            path["total"] += 1
            if item["status"] == "complete":
                path["completed"] += 1
        for path in paths.values():
            path["progress"] = round(path["completed"] / path["total"], 4) if path["total"] else 0.0

        return {
            "items": items,
            "paths": list(paths.values()),
            "completion_rate": round(
                sum(1 for i in items if i["status"] == "complete") / len(items), 4
            )
            if items
            else 0.0,
        }
