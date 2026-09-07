"""Report generation (§25).

A report is a dated, reproducible snapshot: the same period always renders the
same figures, and every section carries the assumptions behind it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, AuditService
from app.core.constants import EntityType
from app.core.errors import NotFoundError, ValidationError
from app.models.identity import Household, User
from app.models.workflow import Report
from app.services.estate_service import EstateService
from app.services.goal_service import GoalService
from app.services.portfolio_service import PortfolioService
from app.services.tax_service import TaxService

REPORT_TYPES: dict[str, dict[str, Any]] = {
    "portfolio": {
        "label": "Portfolio Report",
        "description": "Holdings, allocation, concentration and risk as of a chosen date.",
        "sections": ["Summary", "Allocation", "Holdings", "Concentration", "Risk", "Assumptions"],
    },
    "performance": {
        "label": "Performance Report",
        "description": "Time-weighted returns by period against the benchmark.",
        "sections": ["Summary", "Returns by period", "Benchmark comparison", "Risk statistics", "Assumptions"],
    },
    "goal": {
        "label": "Goal Report",
        "description": "Funding progress and forecast for every goal.",
        "sections": ["Summary", "Goals", "Projections", "Scenarios", "Assumptions"],
    },
    "tax": {
        "label": "Tax Report",
        "description": "Realised gains, harvesting activity and the year-end estimate.",
        "sections": ["Summary", "Realised gains", "Opportunities", "Projection", "Assumptions"],
    },
    "household": {
        "label": "Household Report",
        "description": "Net worth, accounts, goals and estate in one document.",
        "sections": ["Net worth", "Accounts", "Portfolio", "Goals", "Estate", "Assumptions"],
    },
    "quarterly_review": {
        "label": "Quarterly Review",
        "description": "The full review pack: performance, goals, tax and next steps.",
        "sections": ["Executive summary", "Performance", "Allocation", "Goals", "Tax", "Actions", "Assumptions"],
    },
}


class ReportService:
    def __init__(self, db: Session, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.portfolio = PortfolioService(db)
        self.goals = GoalService(db, self.audit)
        self.tax = TaxService(db, self.audit)
        self.estate = EstateService(db, self.audit)

    def catalogue(self) -> list[dict[str, Any]]:
        return [{"key": key, **meta} for key, meta in REPORT_TYPES.items()]

    def list(self, household_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(Report)
            .where(Report.household_id == household_id)
            .order_by(Report.generated_at.desc().nullslast(), Report.created_at.desc())
            .limit(limit)
        ).scalars().all()
        return [self.serialise(r, include_payload=False) for r in rows]

    def serialise(self, report: Report, include_payload: bool = True) -> dict[str, Any]:
        meta = REPORT_TYPES.get(report.report_type, {})
        payload = {
            "id": report.id,
            "household_id": report.household_id,
            "report_type": report.report_type,
            "report_label": meta.get("label", report.report_type.replace("_", " ").title()),
            "title": report.title,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "benchmark_code": report.benchmark_code,
            "status": report.status,
            "sections": report.sections,
            "assumptions": report.assumptions,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        }
        if include_payload:
            payload["payload"] = report.payload
        return payload

    def get(self, report_id: str) -> dict[str, Any]:
        report = self.db.get(Report, report_id)
        if not report:
            raise NotFoundError("Report not found.")
        return self.serialise(report)

    def generate(
        self,
        *,
        household_id: str,
        report_type: str,
        period_start: date,
        period_end: date,
        actor: User,
        benchmark_code: str | None = None,
    ) -> dict[str, Any]:
        if report_type not in REPORT_TYPES:
            raise ValidationError(
                f"Unknown report type {report_type!r}.", details={"available": list(REPORT_TYPES.keys())}
            )
        if period_end < period_start:
            raise ValidationError("The period end must fall on or after the period start.")

        household = self.db.get(Household, household_id)
        if not household:
            raise NotFoundError("Household not found.")

        as_of = self.portfolio.as_of(household_id)
        meta = REPORT_TYPES[report_type]
        payload, assumptions = self._build_payload(report_type, household_id, as_of, period_start, period_end)

        report = Report(
            household_id=household_id,
            report_type=report_type,
            title=f"{meta['label']} — {household.name}",
            period_start=period_start,
            period_end=period_end,
            benchmark_code=benchmark_code,
            status="ready",
            generated_by_id=actor.id,
            generated_at=datetime.now(timezone.utc),
            sections=meta["sections"],
            payload=payload,
            assumptions=assumptions,
        )
        self.db.add(report)
        self.db.flush()

        self.audit.record(
            action=AuditAction.REPORT_GENERATED,
            entity_type=EntityType.REPORT,
            entity_id=report.id,
            entity_label=report.title,
            actor=actor,
            household_id=household_id,
            summary=f"Generated {meta['label']} for {period_start} to {period_end}",
            after={"report_type": report_type, "period_end": period_end.isoformat()},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(report)
        return self.serialise(report)

    def _build_payload(
        self, report_type: str, household_id: str, as_of: date, period_start: date, period_end: date
    ) -> tuple[dict[str, Any], list[str]]:
        household = self.db.get(Household, household_id)
        assumptions: list[str] = [
            f"Figures are as of {as_of.isoformat()} and reflect positions held in the platform on that date.",
            "Performance is time-weighted and net of investment-management fees.",
        ]
        header = {
            "household": household.name,
            "as_of": as_of.isoformat(),
            "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
            "prepared_on": date.today().isoformat(),
        }

        if report_type == "portfolio":
            valuation = self.portfolio.valuation(household_id)
            allocation = self.portfolio.allocation(household_id)
            concentration = self.portfolio.concentration(household_id)
            risk = self.portfolio.risk(household_id)
            holdings = self.portfolio.holdings_table(household_id, page_size=100)
            assumptions += valuation["assumptions"] + risk["assumptions"]
            return (
                {
                    **header,
                    "valuation": valuation,
                    "allocation": allocation,
                    "concentration": concentration,
                    "risk": risk,
                    "holdings": holdings["rows"],
                    "holdings_totals": holdings["totals"],
                },
                sorted(set(assumptions)),
            )

        if report_type == "performance":
            performance = self.portfolio.performance(household_id)
            assumptions += performance["risk_adjusted"]["assumptions"]
            return {**header, "performance": performance}, sorted(set(assumptions))

        if report_type == "goal":
            summary = self.goals.summary(household_id, as_of)
            assumptions += summary["assumptions"]
            return {**header, "goals": summary}, sorted(set(assumptions))

        if report_type == "tax":
            overview = self.tax.overview(household_id, as_of)
            assumptions += overview["tax_estimate"]["assumptions"] + overview["harvest"]["assumptions"]
            return (
                {
                    **header,
                    "realized_gains": overview["realized_gains"],
                    "tax_estimate": overview["tax_estimate"],
                    "harvest": overview["harvest"],
                    "opportunities": overview["opportunities"],
                    "projection": overview["projection"],
                },
                sorted(set(assumptions)),
            )

        if report_type == "household":
            return (
                {
                    **header,
                    "net_worth": self.portfolio.net_worth(household_id),
                    "accounts": self.portfolio.accounts_view(household_id),
                    "valuation": self.portfolio.valuation(household_id),
                    "goals": self.goals.summary(household_id, as_of),
                    "estate": self.estate.overview(household_id, as_of)["projection"],
                },
                sorted(set(assumptions)),
            )

        # quarterly_review
        performance = self.portfolio.performance(household_id)
        goals = self.goals.summary(household_id, as_of)
        tax_overview = self.tax.overview(household_id, as_of)
        assumptions += goals["assumptions"] + tax_overview["harvest"]["assumptions"]
        return (
            {
                **header,
                "net_worth": self.portfolio.net_worth(household_id),
                "valuation": self.portfolio.valuation(household_id),
                "performance": performance,
                "allocation": self.portfolio.allocation(household_id),
                "drift": self.portfolio.drift(household_id),
                "goals": goals,
                "tax": {
                    "realized_gains": tax_overview["realized_gains"],
                    "harvest": tax_overview["harvest"],
                    "projection": tax_overview["projection"],
                },
            },
            sorted(set(assumptions)),
        )
