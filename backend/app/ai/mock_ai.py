"""Deterministic intelligence over the real dataset.

This is not a random text generator. Every insight below is a business rule
evaluated against figures the calculation engine already verified, and every
sentence it writes cites the number it came from. The same context always
produces the same output, which is what makes it safe to demonstrate and
straightforward to test.

When a hosted model is configured later it implements the same `AIProvider`
interface and receives the same `AIContext`. Nothing else in the product changes.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from app.ai.base import (
    AgentAnswer,
    AIContext,
    AIProvider,
    AIProviderInfo,
    DocumentClassification,
    Explanation,
    Insight,
    NextAction,
    RecommendationDraft,
    SupportingFact,
)

CONCENTRATION_THRESHOLD = 0.10
DRIFT_THRESHOLD = 0.05
CASH_DRAG_THRESHOLD = 0.08
UNDERPERFORMANCE_THRESHOLD = -0.02
DOCUMENT_EXPIRY_WINDOW_DAYS = 90
ESTATE_REVIEW_YEARS = 3


def _money(value: float | None, currency: str = "USD") -> str:
    if value is None:
        return "n/a"
    symbol = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}.get(currency, "")
    sign = "-" if value < 0 else ""
    amount = abs(float(value))
    if amount >= 1_000_000:
        return f"{sign}{symbol}{amount / 1_000_000:,.2f}M"
    if amount >= 1_000:
        return f"{sign}{symbol}{amount / 1_000:,.1f}K"
    return f"{sign}{symbol}{amount:,.0f}"


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _label(key: str) -> str:
    return key.replace("_", " ").title()


class MockAIService(AIProvider):
    """Rule-based provider used when AI_PROVIDER=mock (the default)."""

    name = "mock"
    mode = "mock"

    def info(self) -> AIProviderInfo:
        return AIProviderInfo(
            name="mock",
            mode="mock",
            model=None,
            description=(
                "Deterministic rules engine. Insights are derived from the platform's own verified "
                "calculations, not from a language model. Output is reproducible for the same data."
            ),
            capabilities=[
                "insights",
                "recommendations",
                "next_actions",
                "document_classification",
                "calculation_explanation",
                "grounded_question_answering",
            ],
            requires_api_key=False,
            is_configured=True,
        )

    # ------------------------------------------------------------------
    # Insights - "what changed?"
    # ------------------------------------------------------------------
    def generate_insights(self, context: AIContext) -> list[Insight]:
        insights: list[Insight] = []
        for rule in (
            self._insight_concentration,
            self._insight_drift,
            self._insight_cash_drag,
            self._insight_goal_risk,
            self._insight_tax_harvest,
            self._insight_performance,
            self._insight_rmd,
            self._insight_estate_review,
            self._insight_beneficiary_gap,
            self._insight_document_expiry,
            self._insight_charitable,
            self._insight_data_freshness,
        ):
            produced = rule(context)
            if produced:
                insights.extend(produced if isinstance(produced, list) else [produced])

        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        insights.sort(key=lambda i: (order.get(i.severity, 9), -i.confidence))
        return insights

    def _insight_concentration(self, ctx: AIContext) -> Insight | None:
        # Single-name risk drives this rule; a large index-fund position does not.
        top = (ctx.concentration or {}).get("top_single_name") or {}
        if not top or float(top.get("weight") or 0) <= CONCENTRATION_THRESHOLD:
            return None

        weight = float(top["weight"])
        value = float(top.get("market_value") or 0)
        severity = "high" if weight > 0.20 else "medium"

        return Insight(
            key="portfolio_concentration",
            title="Portfolio Concentration",
            category="portfolio",
            severity=severity,
            summary=(
                f"{top.get('name') or top.get('symbol')} represents {_percent(weight)} of the portfolio "
                f"({_money(value, ctx.currency)}), above the {_percent(CONCENTRATION_THRESHOLD)} single-position "
                "guideline in the investment policy."
            ),
            impact=(
                "Higher concentration risk. A large move in one holding drives an outsized share of portfolio "
                f"return. The top five positions account for {_percent((ctx.concentration or {}).get('top_five_weight'))} "
                "of assets."
            ),
            suggested_next_step="Review a staged reduction with your advisor, weighing the capital-gains cost against the risk reduction.",
            supporting_facts=[
                SupportingFact(label="Position", value=str(top.get("symbol")), as_of=ctx.as_of),
                SupportingFact(label="Weight", value=_percent(weight), raw_value=weight, as_of=ctx.as_of),
                SupportingFact(label="Market value", value=_money(value, ctx.currency), raw_value=value, as_of=ctx.as_of),
                SupportingFact(
                    label="Concentration index (HHI)",
                    value=f"{(ctx.concentration or {}).get('hhi', 0):.3f}",
                    raw_value=(ctx.concentration or {}).get("hhi"),
                    as_of=ctx.as_of,
                ),
            ],
            calculation_method="weight = position market value / total portfolio market value",
            assumptions=[f"Positions above {_percent(CONCENTRATION_THRESHOLD)} of the portfolio are flagged for review."],
            limitations=["Overlapping exposure inside funds is not aggregated into the position weight."],
            confidence=0.95,
            as_of=ctx.as_of,
            entity_type="portfolio",
            action_url="/portfolio",
        )

    def _insight_drift(self, ctx: AIContext) -> Insight | None:
        drift = ctx.drift or {}
        breaches = [row for row in drift.get("rows", []) if row.get("breached")]
        if not breaches:
            return None

        worst = max(breaches, key=lambda r: abs(float(r["drift"])))
        direction = "above" if float(worst["drift"]) > 0 else "below"

        return Insight(
            key="allocation_drift",
            title="Allocation Drift",
            category="portfolio",
            severity="medium" if abs(float(worst["drift"])) < 0.10 else "high",
            summary=(
                f"{_label(worst['asset_class'])} is {_percent(abs(float(worst['drift'])))} {direction} its "
                f"{_percent(float(worst['target_weight']))} target, outside the "
                f"{_percent(float(worst['tolerance_band']))} tolerance band. "
                f"{len(breaches)} asset class(es) currently breach their band."
            ),
            impact=(
                f"The portfolio's risk profile has moved away from the approved policy by "
                f"{_money(abs(float(worst.get('dollar_drift') or 0)), ctx.currency)} in this sleeve."
            ),
            suggested_next_step="Open the rebalancing workspace to model a trade set, then route it for approval.",
            supporting_facts=[
                SupportingFact(label="Asset class", value=_label(worst["asset_class"]), as_of=ctx.as_of),
                SupportingFact(label="Current weight", value=_percent(float(worst["current_weight"])), raw_value=float(worst["current_weight"]), as_of=ctx.as_of),
                SupportingFact(label="Target weight", value=_percent(float(worst["target_weight"])), raw_value=float(worst["target_weight"]), as_of=ctx.as_of),
                SupportingFact(label="Drift", value=_percent(float(worst["drift"])), raw_value=float(worst["drift"]), as_of=ctx.as_of),
            ],
            calculation_method="drift = current weight - strategic target weight; breach when |drift| exceeds the tolerance band",
            assumptions=["Targets come from the approved investment policy for this portfolio."],
            limitations=["Rebalancing may realise capital gains; the tax cost is estimated separately."],
            confidence=0.93,
            as_of=ctx.as_of,
            entity_type="portfolio",
            action_url="/portfolio",
        )

    def _insight_cash_drag(self, ctx: AIContext) -> Insight | None:
        cash_weight = float((ctx.risk or {}).get("cash_exposure") or 0)
        cash_value = float((ctx.portfolio or {}).get("cash") or 0)
        if cash_weight <= CASH_DRAG_THRESHOLD or cash_value <= 0:
            return None

        # Opportunity cost measured against the fixed-income CMA, not equities.
        estimated_drag = cash_value * 0.045 - cash_value * 0.036

        return Insight(
            key="cash_drag",
            title="Uninvested Cash",
            category="cash",
            severity="low" if cash_weight < 0.12 else "medium",
            summary=(
                f"Cash is {_percent(cash_weight)} of the portfolio ({_money(cash_value, ctx.currency)}), above the "
                f"{_percent(CASH_DRAG_THRESHOLD)} level typically held for liquidity."
            ),
            impact=(
                f"Holding this balance in cash rather than short-duration fixed income has an estimated opportunity "
                f"cost of {_money(estimated_drag, ctx.currency)} a year at current assumptions."
            ),
            suggested_next_step="Confirm near-term spending needs, then deploy the surplus into the target allocation.",
            supporting_facts=[
                SupportingFact(label="Cash balance", value=_money(cash_value, ctx.currency), raw_value=cash_value, as_of=ctx.as_of),
                SupportingFact(label="Cash weight", value=_percent(cash_weight), raw_value=cash_weight, as_of=ctx.as_of),
                SupportingFact(label="Estimated annual drag", value=_money(estimated_drag, ctx.currency), raw_value=estimated_drag, as_of=ctx.as_of),
            ],
            calculation_method="drag = cash balance x (fixed income expected return - cash expected return)",
            assumptions=["Capital market assumptions of 4.5% for short fixed income and 3.6% for cash."],
            limitations=["Cash earmarked for a known expense within twelve months should not be deployed."],
            confidence=0.82,
            as_of=ctx.as_of,
            entity_type="portfolio",
            action_url="/accounts",
        )

    def _insight_goal_risk(self, ctx: AIContext) -> list[Insight]:
        rows = (ctx.goals or {}).get("goals", [])
        results = []
        for goal in rows:
            if goal.get("status") not in {"at_risk", "off_track"}:
                continue
            gap = abs(float(goal.get("gap") or 0))
            extra = float(goal.get("additional_monthly_needed") or 0)
            results.append(
                Insight(
                    key=f"goal_risk_{goal.get('id')}",
                    title=f"{goal.get('name')} Funding Gap",
                    category="goal",
                    severity="high" if goal.get("status") == "off_track" else "medium",
                    summary=(
                        f"On current assumptions {goal.get('name')} is projected to reach "
                        f"{_money(float(goal.get('projected_value') or 0), ctx.currency)} against a target of "
                        f"{_money(float(goal.get('inflation_adjusted_target') or 0), ctx.currency)}, a shortfall of "
                        f"{_money(gap, ctx.currency)}."
                    ),
                    impact=f"Funded ratio is {_percent(float(goal.get('funded_ratio') or 0))} with "
                    f"{goal.get('years_to_target')} years to the target date.",
                    suggested_next_step=(
                        f"Increasing contributions by about {_money(extra, ctx.currency)} a month closes the gap on "
                        "these assumptions. Compare scenarios before deciding."
                    ),
                    supporting_facts=[
                        SupportingFact(label="Projected value", value=_money(float(goal.get("projected_value") or 0), ctx.currency), raw_value=goal.get("projected_value"), as_of=ctx.as_of),
                        SupportingFact(label="Target", value=_money(float(goal.get("inflation_adjusted_target") or 0), ctx.currency), raw_value=goal.get("inflation_adjusted_target"), as_of=ctx.as_of),
                        SupportingFact(label="Shortfall", value=_money(gap, ctx.currency), raw_value=gap, as_of=ctx.as_of),
                        SupportingFact(label="Additional monthly needed", value=_money(extra, ctx.currency), raw_value=extra, as_of=ctx.as_of),
                    ],
                    calculation_method="future value of current balance plus monthly contributions, compared with the inflation-adjusted target",
                    assumptions=[
                        "A constant expected return and uninterrupted contributions to the target date.",
                        "The target amount grows with the stated inflation rate.",
                    ],
                    limitations=[
                        "A deterministic projection, not a guarantee. Real returns vary and their order matters.",
                    ],
                    confidence=0.88,
                    as_of=ctx.as_of,
                    entity_type="goal",
                    entity_id=str(goal.get("id")),
                    action_url=f"/goals/{goal.get('id')}",
                )
            )
        return results

    def _insight_tax_harvest(self, ctx: AIContext) -> Insight | None:
        harvest = (ctx.tax or {}).get("harvest") or {}
        benefit = float(harvest.get("total_estimated_benefit") or 0)
        count = int(harvest.get("opportunity_count") or 0)
        if count == 0 or benefit <= 0:
            return None

        top = (harvest.get("opportunities") or [{}])[0]

        return Insight(
            key="tax_loss_harvest",
            title="Tax-Loss Harvesting Opportunity",
            category="tax",
            severity="medium",
            summary=(
                f"{count} position(s) hold unrealised losses totalling "
                f"{_money(abs(float(harvest.get('total_harvestable_loss') or 0)), ctx.currency)}. Harvesting them "
                f"could reduce this year's tax by an estimated {_money(benefit, ctx.currency)}."
            ),
            impact=(
                f"The largest single candidate is {top.get('symbol')} with an unrealised loss of "
                f"{_money(abs(float(top.get('unrealized_loss') or 0)), ctx.currency)}."
            ),
            suggested_next_step="Review the candidates and their replacement securities in the Tax Center, then submit for approval.",
            supporting_facts=[
                SupportingFact(label="Candidates", value=str(count), raw_value=count, as_of=ctx.as_of),
                SupportingFact(label="Harvestable loss", value=_money(abs(float(harvest.get("total_harvestable_loss") or 0)), ctx.currency), as_of=ctx.as_of),
                SupportingFact(label="Estimated tax benefit", value=_money(benefit, ctx.currency), raw_value=benefit, as_of=ctx.as_of),
                SupportingFact(label="Wash-sale status", value=str(top.get("wash_sale_risk", "clear")), as_of=ctx.as_of),
            ],
            calculation_method="benefit = |unrealised loss| x (applicable capital-gains rate + state rate) per open tax lot",
            assumptions=["Harvested losses are usable against gains of the same character this year."],
            limitations=[
                "Each candidate must clear a wash-sale check across all linked accounts.",
                "Nothing is traded by this platform; execution is simulated after approval.",
            ],
            confidence=0.9,
            as_of=ctx.as_of,
            entity_type="tax_opportunity",
            action_url="/tax",
        )

    def _insight_performance(self, ctx: AIContext) -> Insight | None:
        ytd = (ctx.performance or {}).get("YTD") or {}
        excess = ytd.get("excess_return")
        if excess is None:
            return None
        excess = float(excess)
        if abs(excess) < 0.005:
            return None

        trailing = excess < UNDERPERFORMANCE_THRESHOLD
        return Insight(
            key="benchmark_relative_performance",
            title="Performance vs Benchmark",
            category="portfolio",
            severity="medium" if trailing else "info",
            summary=(
                f"Year to date the portfolio returned {_percent(float(ytd.get('return') or 0))} against "
                f"{_percent(float(ytd.get('benchmark_return') or 0))} for the benchmark, "
                f"{'trailing' if excess < 0 else 'ahead'} by {_percent(abs(excess))}."
            ),
            impact=(
                "Sustained divergence from the benchmark warrants a look at allocation and manager selection."
                if trailing
                else "The portfolio is tracking ahead of its benchmark for the period."
            ),
            suggested_next_step=(
                "Review attribution by asset class in the performance tab."
                if trailing
                else "No action needed; review at the next scheduled meeting."
            ),
            supporting_facts=[
                SupportingFact(label="Portfolio YTD", value=_percent(float(ytd.get("return") or 0)), raw_value=ytd.get("return"), as_of=ctx.as_of),
                SupportingFact(label="Benchmark YTD", value=_percent(float(ytd.get("benchmark_return") or 0)), raw_value=ytd.get("benchmark_return"), as_of=ctx.as_of),
                SupportingFact(label="Excess return", value=_percent(excess), raw_value=excess, as_of=ctx.as_of),
            ],
            calculation_method="time-weighted return chained from daily returns, less the benchmark return over the same window",
            assumptions=["Returns are net of investment-management fees."],
            limitations=["A single period is not evidence of skill or its absence."],
            confidence=0.86,
            as_of=ctx.as_of,
            entity_type="portfolio",
            action_url="/portfolio",
        )

    def _insight_rmd(self, ctx: AIContext) -> Insight | None:
        rmd = (ctx.tax or {}).get("rmd") or {}
        required = float(rmd.get("required_amount") or 0)
        distributed = float(rmd.get("distributed_amount") or 0)
        if required <= 0 or distributed >= required:
            return None

        remaining = required - distributed
        deadline = rmd.get("deadline")
        return Insight(
            key="rmd_outstanding",
            title="Required Minimum Distribution Outstanding",
            category="tax",
            severity="high",
            summary=(
                f"{_money(remaining, ctx.currency)} of this year's required minimum distribution has not yet been taken "
                f"(required {_money(required, ctx.currency)}, taken {_money(distributed, ctx.currency)})."
            ),
            impact="A shortfall at the deadline is subject to an excise tax on the amount not distributed.",
            suggested_next_step=f"Schedule the remaining distribution before {deadline}. A qualified charitable distribution can satisfy it.",
            supporting_facts=[
                SupportingFact(label="Required", value=_money(required, ctx.currency), raw_value=required, as_of=ctx.as_of),
                SupportingFact(label="Distributed", value=_money(distributed, ctx.currency), raw_value=distributed, as_of=ctx.as_of),
                SupportingFact(label="Remaining", value=_money(remaining, ctx.currency), raw_value=remaining, as_of=ctx.as_of),
                SupportingFact(label="Deadline", value=str(deadline), as_of=ctx.as_of),
            ],
            calculation_method="prior 31 December balance / IRS Uniform Lifetime Table factor",
            assumptions=["The Uniform Lifetime Table applies to this account owner."],
            limitations=["Inherited-account rules differ; confirm with your tax adviser."],
            confidence=0.94,
            as_of=ctx.as_of,
            entity_type="rmd",
            action_url="/tax",
        )

    def _insight_estate_review(self, ctx: AIContext) -> Insight | None:
        estate = ctx.estate or {}
        last_reviewed = estate.get("last_reviewed_on")
        if not last_reviewed:
            return None
        try:
            reviewed = date.fromisoformat(str(last_reviewed))
        except ValueError:
            return None

        years = (ctx.as_of - reviewed).days / 365.25
        if years < ESTATE_REVIEW_YEARS:
            return None

        return Insight(
            key="estate_review_due",
            title="Estate Documents Due for Review",
            category="estate",
            severity="medium",
            summary=f"The estate plan was last reviewed {years:.1f} years ago, on {reviewed.isoformat()}.",
            impact=(
                f"Documents older than {ESTATE_REVIEW_YEARS} years may not reflect current family circumstances, "
                f"asset ownership or tax law. The estate is currently valued at "
                f"{_money(float(estate.get('gross_estate') or 0), ctx.currency)}."
            ),
            suggested_next_step="Schedule a review with your estate attorney and confirm beneficiary designations across all accounts.",
            supporting_facts=[
                SupportingFact(label="Last reviewed", value=reviewed.isoformat(), as_of=ctx.as_of),
                SupportingFact(label="Years since review", value=f"{years:.1f}", raw_value=years, as_of=ctx.as_of),
                SupportingFact(label="Projected estate tax", value=_money(float(estate.get("estimated_federal_tax") or 0), ctx.currency), as_of=ctx.as_of),
            ],
            calculation_method="elapsed time since the recorded review date, compared with the three-year review cadence",
            assumptions=["A three-year review cadence is the practice standard used here."],
            limitations=["A life event such as a marriage, birth or move should trigger a review sooner."],
            confidence=0.9,
            as_of=ctx.as_of,
            entity_type="estate_plan",
            action_url="/estate",
        )

    def _insight_beneficiary_gap(self, ctx: AIContext) -> Insight | None:
        gaps = (ctx.estate or {}).get("beneficiary_gaps") or []
        if not gaps:
            return None

        return Insight(
            key="beneficiary_gap",
            title="Beneficiary Designations Incomplete",
            category="estate",
            severity="high",
            summary=f"{len(gaps)} account(s) have missing or incomplete beneficiary designations.",
            impact="Accounts without a valid designation pass through probate rather than directly to the intended person.",
            suggested_next_step="Complete the designation for each account listed; changes route through review and approval.",
            supporting_facts=[
                SupportingFact(label="Accounts affected", value=str(len(gaps)), raw_value=len(gaps), as_of=ctx.as_of),
                *[SupportingFact(label=str(g.get("account_name")), value=str(g.get("reason")), as_of=ctx.as_of) for g in gaps[:4]],
            ],
            calculation_method="accounts are checked for at least one primary beneficiary summing to 100%",
            assumptions=["Retirement, trust and transfer-on-death accounts require a designation."],
            limitations=["Designations held directly at a custodian and not synced here cannot be verified."],
            confidence=0.92,
            as_of=ctx.as_of,
            entity_type="beneficiary",
            action_url="/estate",
        )

    def _insight_document_expiry(self, ctx: AIContext) -> Insight | None:
        expiring = (ctx.documents or {}).get("expiring_soon") or []
        if not expiring:
            return None

        return Insight(
            key="documents_expiring",
            title="Documents Approaching Expiration",
            category="document",
            severity="low",
            summary=f"{len(expiring)} document(s) expire within the next {DOCUMENT_EXPIRY_WINDOW_DAYS} days.",
            impact="Expired insurance or authority documents can interrupt coverage or delay a transaction.",
            suggested_next_step="Upload refreshed copies to the document vault.",
            supporting_facts=[
                SupportingFact(label=str(d.get("name")), value=f"expires {d.get('expires_on')}", as_of=ctx.as_of)
                for d in expiring[:5]
            ],
            calculation_method=f"documents with an expiration date inside the next {DOCUMENT_EXPIRY_WINDOW_DAYS} days",
            assumptions=["Expiration dates are as recorded when each document was filed."],
            limitations=["Documents without a recorded expiration date are not monitored."],
            confidence=0.97,
            as_of=ctx.as_of,
            entity_type="document",
            action_url="/documents",
        )

    def _insight_charitable(self, ctx: AIContext) -> Insight | None:
        giving = ctx.philanthropy or {}
        target = float(giving.get("annual_grant_target") or 0)
        granted = float(giving.get("granted_ytd") or 0)
        balance = float(giving.get("daf_balance") or 0)
        if target <= 0 or granted >= target or balance <= 0:
            return None

        remaining = target - granted
        return Insight(
            key="charitable_grant_pacing",
            title="Charitable Granting Behind Plan",
            category="philanthropy",
            severity="low",
            summary=(
                f"{_money(granted, ctx.currency)} of a {_money(target, ctx.currency)} annual grant target has been "
                f"distributed, leaving {_money(remaining, ctx.currency)} with "
                f"{_money(balance, ctx.currency)} available in the donor-advised fund."
            ),
            impact="Undistributed balances delay funding to the causes the household has chosen to support.",
            suggested_next_step="Review the giving plan and recommend grants to the charities already on file.",
            supporting_facts=[
                SupportingFact(label="Granted year to date", value=_money(granted, ctx.currency), raw_value=granted, as_of=ctx.as_of),
                SupportingFact(label="Annual target", value=_money(target, ctx.currency), raw_value=target, as_of=ctx.as_of),
                SupportingFact(label="DAF balance", value=_money(balance, ctx.currency), raw_value=balance, as_of=ctx.as_of),
            ],
            calculation_method="remaining = annual grant target - grants made year to date",
            assumptions=["The grant target is the amount agreed in the current giving plan."],
            limitations=["Multi-year pledges may intentionally back-load grants."],
            confidence=0.85,
            as_of=ctx.as_of,
            entity_type="daf",
            action_url="/philanthropy",
        )

    def _insight_data_freshness(self, ctx: AIContext) -> Insight | None:
        freshness = ctx.data_freshness or {}
        stale = [k for k, v in freshness.items() if v in {"stale", "unavailable"}]
        if not stale:
            return None

        return Insight(
            key="data_freshness",
            title="Some Data Is Not Current",
            category="portfolio",
            severity="medium",
            summary=f"{len(stale)} data source(s) are stale or unavailable: {', '.join(_label(s) for s in stale)}.",
            impact="Figures that depend on these sources may not reflect today's position.",
            suggested_next_step="Reconnect the affected accounts, or treat the affected figures as indicative until the feed recovers.",
            supporting_facts=[SupportingFact(label=_label(k), value=str(v), as_of=ctx.as_of) for k, v in freshness.items()],
            calculation_method="each feed is compared against its expected refresh interval",
            assumptions=["Custodian feeds are expected to refresh each business day."],
            limitations=["A stale feed does not necessarily mean the underlying position has changed."],
            confidence=1.0,
            as_of=ctx.as_of,
            entity_type="account",
            action_url="/accounts",
        )

    # ------------------------------------------------------------------
    # Recommendations - "what should I consider?"
    # ------------------------------------------------------------------
    def generate_recommendations(self, context: AIContext) -> list[RecommendationDraft]:
        drafts: list[RecommendationDraft] = []
        currency = context.currency

        top = (context.concentration or {}).get("top_single_name")
        if top and float(top.get("weight") or 0) > CONCENTRATION_THRESHOLD:
            weight = float(top["weight"])
            value = float(top.get("market_value") or 0)
            trim_to = CONCENTRATION_THRESHOLD
            trim_amount = value * (1 - trim_to / weight)
            drafts.append(
                RecommendationDraft(
                    key="trim_concentrated_position",
                    title=f"Reduce {top.get('symbol')} toward the policy limit",
                    category="portfolio",
                    severity="high" if weight > 0.20 else "medium",
                    summary=(
                        f"Trim approximately {_money(trim_amount, currency)} of {top.get('symbol')} to bring the "
                        f"position from {_percent(weight)} to the {_percent(trim_to)} policy guideline."
                    ),
                    rationale=(
                        f"{top.get('symbol')} is the largest single source of portfolio risk at {_percent(weight)} of "
                        "assets. Reducing it lowers single-name risk while keeping the strategic allocation intact."
                    ),
                    suggested_action="Stage the reduction across two tax years, harvesting offsetting losses where available.",
                    impact_amount=trim_amount,
                    impact_label="Estimated proceeds to reallocate",
                    confidence=0.88,
                    supporting_data={"position": top, "concentration": context.concentration},
                    assumptions=["Trades execute at the last available price.", "The policy single-position limit is 10%."],
                    limitations=[
                        "Selling realises capital gains; model the tax cost before acting.",
                        "This platform does not place trades. Approved actions are simulated.",
                    ],
                    entity_type="portfolio",
                )
            )

        harvest = (context.tax or {}).get("harvest") or {}
        if int(harvest.get("opportunity_count") or 0) > 0:
            benefit = float(harvest.get("total_estimated_benefit") or 0)
            drafts.append(
                RecommendationDraft(
                    key="harvest_losses",
                    title="Harvest available tax losses before year end",
                    category="tax",
                    severity="medium",
                    summary=(
                        f"Harvesting {harvest.get('opportunity_count')} loss position(s) is estimated to reduce this "
                        f"year's tax by {_money(benefit, currency)}."
                    ),
                    rationale=(
                        "Realising losses offsets realised gains of the same character and up to $3,000 of ordinary "
                        "income, with any excess carried forward."
                    ),
                    suggested_action="Approve the harvest set and hold the replacement securities through the 31-day wash-sale window.",
                    impact_amount=benefit,
                    impact_label="Estimated tax reduction",
                    confidence=0.9,
                    supporting_data={"harvest": harvest},
                    assumptions=["Losses are usable against gains of the same character this year."],
                    limitations=["Each candidate must clear a wash-sale check across every linked account."],
                    entity_type="harvest",
                )
            )

        drift = context.drift or {}
        if int(drift.get("breach_count") or 0) > 0:
            drafts.append(
                RecommendationDraft(
                    key="rebalance_to_policy",
                    title="Rebalance the portfolio back to policy targets",
                    category="portfolio",
                    severity="medium",
                    summary=(
                        f"{drift.get('breach_count')} asset class(es) sit outside their tolerance band, with a maximum "
                        f"drift of {_percent(float(drift.get('max_drift') or 0))}."
                    ),
                    rationale="Restoring the strategic allocation keeps portfolio risk aligned with the agreed investment policy.",
                    suggested_action="Generate a trade proposal in the rebalancing workspace and submit it for approval.",
                    impact_label="Return portfolio to policy risk",
                    confidence=0.86,
                    supporting_data={"drift": drift},
                    assumptions=["The strategic targets on file remain appropriate for the household."],
                    limitations=["Rebalancing in taxable accounts may realise gains."],
                    entity_type="rebalance",
                )
            )

        for goal in (context.goals or {}).get("goals", []):
            if goal.get("status") not in {"at_risk", "off_track"}:
                continue
            extra = float(goal.get("additional_monthly_needed") or 0)
            drafts.append(
                RecommendationDraft(
                    key=f"increase_contribution_{goal.get('id')}",
                    title=f"Increase funding for {goal.get('name')}",
                    category="goal",
                    severity="high" if goal.get("status") == "off_track" else "medium",
                    summary=f"An additional {_money(extra, currency)} a month closes the projected shortfall on current assumptions.",
                    rationale=(
                        f"The goal is projected to reach {_percent(float(goal.get('funded_ratio') or 0))} of its "
                        f"inflation-adjusted target by {goal.get('target_date')}."
                    ),
                    suggested_action="Compare the higher-savings and lower-return scenarios, then adjust the funding plan.",
                    impact_amount=extra,
                    impact_label="Additional monthly contribution",
                    confidence=0.85,
                    supporting_data={"goal": goal},
                    assumptions=["Return and inflation assumptions on the goal remain unchanged."],
                    limitations=["Projections are illustrative; actual outcomes vary."],
                    entity_type="goal",
                    entity_id=str(goal.get("id")),
                )
            )

        location = (context.tax or {}).get("asset_location") or {}
        drag = float(location.get("total_estimated_drag") or 0)
        if drag > 1000:
            drafts.append(
                RecommendationDraft(
                    key="improve_asset_location",
                    title="Move income-producing assets to tax-deferred accounts",
                    category="tax",
                    severity="low",
                    summary=f"Repositioning income assets is estimated to save {_money(drag, currency)} a year in tax drag.",
                    rationale="Taxable bond and alternative income is taxed at ordinary rates; sheltering it improves after-tax return.",
                    suggested_action="Reposition gradually using new contributions to avoid realising gains.",
                    impact_amount=drag,
                    impact_label="Estimated annual tax drag avoided",
                    confidence=0.78,
                    supporting_data={"asset_location": location},
                    assumptions=["Income is taxed at a 35% ordinary rate."],
                    limitations=["Moving existing positions may realise gains that exceed the benefit."],
                    entity_type="tax_opportunity",
                )
            )

        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        drafts.sort(key=lambda d: (order.get(d.severity, 9), -(d.impact_amount or 0)))
        return drafts

    # ------------------------------------------------------------------
    # Actions - "what can I do next?"
    # ------------------------------------------------------------------
    def suggest_actions(self, context: AIContext) -> list[NextAction]:
        actions: list[NextAction] = []

        if int((context.drift or {}).get("breach_count") or 0) > 0:
            actions.append(
                NextAction(
                    key="open_rebalance",
                    label="Model a rebalance",
                    description="Build a trade proposal that returns the portfolio to its policy targets.",
                    route="/advisor/rebalancing",
                    category="portfolio",
                    requires_approval=True,
                    severity="medium",
                )
            )
        if int(((context.tax or {}).get("harvest") or {}).get("opportunity_count") or 0) > 0:
            actions.append(
                NextAction(
                    key="review_harvest",
                    label="Review harvesting candidates",
                    description="Check wash-sale status and replacement securities, then submit for approval.",
                    route="/tax",
                    category="tax",
                    requires_approval=True,
                    severity="medium",
                )
            )
        if (context.goals or {}).get("goals_off_track"):
            actions.append(
                NextAction(
                    key="run_goal_scenarios",
                    label="Run goal scenarios",
                    description="Compare base case, higher savings, lower return and an earlier target date.",
                    route="/goals",
                    category="goal",
                    severity="medium",
                )
            )
        if (context.estate or {}).get("beneficiary_gaps"):
            actions.append(
                NextAction(
                    key="complete_beneficiaries",
                    label="Complete beneficiary designations",
                    description="Fill the gaps found on accounts without a valid primary beneficiary.",
                    route="/estate",
                    category="estate",
                    requires_approval=True,
                    severity="high",
                )
            )
        if (context.documents or {}).get("expiring_soon"):
            actions.append(
                NextAction(
                    key="refresh_documents",
                    label="Refresh expiring documents",
                    description="Upload current copies of documents nearing their expiration date.",
                    route="/documents",
                    category="document",
                    severity="low",
                )
            )
        if context.meetings:
            actions.append(
                NextAction(
                    key="prepare_meeting",
                    label="Prepare for the next review",
                    description=f"Next meeting: {context.meetings[0].get('title')} on {context.meetings[0].get('starts_at')}.",
                    route="/meetings",
                    category="service",
                    severity="info",
                )
            )

        actions.append(
            NextAction(
                key="generate_report",
                label="Generate a portfolio report",
                description="Produce a dated report covering holdings, performance, goals and assumptions.",
                route="/reports",
                category="reporting",
                severity="info",
            )
        )
        return actions

    # ------------------------------------------------------------------
    # Document classification (§18)
    # ------------------------------------------------------------------
    CATEGORY_PATTERNS: list[tuple[str, str, list[str], float]] = [
        ("tax", "Tax Return", [r"1040", r"tax[_\s-]?return", r"return[_\s-]?\d{4}"], 0.96),
        ("tax", "Form 1099", [r"1099", r"consolidated[_\s-]?statement"], 0.94),
        ("tax", "Form W-2", [r"\bw-?2\b"], 0.95),
        ("tax", "Schedule K-1", [r"k-?1\b"], 0.93),
        ("estate", "Trust Agreement", [r"trust", r"trust[_\s-]?agreement"], 0.92),
        ("estate", "Will", [r"\bwill\b", r"last[_\s-]?will", r"testament"], 0.93),
        ("estate", "Power of Attorney", [r"power[_\s-]?of[_\s-]?attorney", r"\bpoa\b"], 0.94),
        ("investment", "Account Statement", [r"statement", r"brokerage", r"portfolio[_\s-]?review"], 0.88),
        ("investment", "Trade Confirmation", [r"trade[_\s-]?confirm", r"confirmation"], 0.9),
        ("insurance", "Insurance Policy", [r"policy", r"insurance", r"umbrella", r"life[_\s-]?ins"], 0.9),
        ("banking", "Bank Statement", [r"bank", r"checking", r"savings", r"deposit"], 0.87),
        ("retirement", "Retirement Statement", [r"401k", r"403b", r"\bira\b", r"pension", r"retirement"], 0.91),
        ("legal", "Legal Agreement", [r"agreement", r"contract", r"deed", r"llc", r"partnership"], 0.84),
    ]

    def classify_document(self, filename: str, metadata: dict[str, Any] | None = None) -> DocumentClassification:
        haystack = filename.lower()
        metadata = metadata or {}
        if metadata.get("description"):
            haystack = f"{haystack} {str(metadata['description']).lower()}"

        best: tuple[str, str, float, list[str]] | None = None
        for category, doc_type, patterns, confidence in self.CATEGORY_PATTERNS:
            matched = [p for p in patterns if re.search(p, haystack)]
            if not matched:
                continue
            # More matched patterns means a stronger signal, capped at 0.98.
            score = min(confidence + 0.01 * (len(matched) - 1), 0.98)
            if best is None or score > best[2]:
                best = (
                    category,
                    doc_type,
                    score,
                    [f"Filename contains a pattern characteristic of a {doc_type.lower()}."],
                )

        year_match = re.search(r"(19|20)\d{2}", filename)
        detected_year = int(year_match.group(0)) if year_match else metadata.get("tax_year")

        if best is None:
            return DocumentClassification(
                suggested_category="other",
                suggested_document_type="Unclassified",
                detected_year=detected_year,
                confidence=0.35,
                reasons=["No filing pattern matched the filename; a person should categorise this document."],
                suggested_tags=[],
                source="mock_rules",
            )

        category, doc_type, confidence, reasons = best
        if detected_year:
            reasons.append(f"Detected the year {detected_year} in the filename.")
            confidence = min(confidence + 0.01, 0.98)

        tags = [category, doc_type.lower().replace(" ", "-")]
        if detected_year:
            tags.append(str(detected_year))

        return DocumentClassification(
            suggested_category=category,
            suggested_document_type=doc_type,
            detected_year=detected_year,
            confidence=round(confidence, 2),
            reasons=reasons,
            suggested_tags=tags,
            source="mock_rules",
        )

    # ------------------------------------------------------------------
    # Explanation of a verified calculation
    # ------------------------------------------------------------------
    def explain(self, calculation: dict[str, Any], audience: str = "client") -> Explanation:
        method = str(calculation.get("method", "calculation"))
        result = calculation.get("result", {})
        as_of_raw = calculation.get("as_of")
        as_of = None
        if isinstance(as_of_raw, str):
            try:
                as_of = date.fromisoformat(as_of_raw)
            except ValueError:
                as_of = None
        elif isinstance(as_of_raw, date):
            as_of = as_of_raw

        if isinstance(result, dict):
            highlights = [f"{_label(k)}: {v}" for k, v in list(result.items())[:5] if not isinstance(v, (dict, list))]
        else:
            highlights = [str(result)]

        register = (
            "The figure is calculated as follows"
            if audience == "client"
            else "Method and inputs, for the record"
        )

        body_lines = [
            f"{register}: {method}.",
            "",
            "Key figures:",
            *[f"  - {line}" for line in highlights],
        ]
        if calculation.get("inputs"):
            body_lines += ["", "Inputs used:", *[f"  - {_label(k)}: {v}" for k, v in list(calculation["inputs"].items())[:8]]]

        return Explanation(
            headline=f"How this figure was calculated{f' (as of {as_of.isoformat()})' if as_of else ''}",
            body="\n".join(body_lines),
            method=method,
            as_of=as_of,
            assumptions=list(calculation.get("assumptions") or []),
            limitations=list(calculation.get("limitations") or []),
            source=str(calculation.get("source", "nexgile_calculation_engine")),
        )

    # ------------------------------------------------------------------
    # Grounded question answering (§19)
    # ------------------------------------------------------------------
    INTENTS: list[tuple[str, list[str]]] = [
        ("net_worth", ["net worth", "how much am i worth", "total assets", "liabilities", "balance sheet"]),
        ("performance", ["perform", "return", "how did", "benchmark", "ytd", "year to date", "beat", "gain this year"]),
        ("allocation", ["allocation", "allocated", "asset class", "diversif", "mix", "exposure"]),
        ("concentration", ["concentration", "concentrated", "largest position", "biggest holding", "risk"]),
        ("goals", ["goal", "retire", "retirement", "education", "college", "on track"]),
        ("tax", ["tax", "harvest", "loss", "capital gain", "rmd", "roth", "wash sale"]),
        ("estate", ["estate", "trust", "will", "beneficiar", "inherit"]),
        ("philanthropy", ["charit", "giving", "donat", "daf", "grant", "philanthrop"]),
        ("cash", ["cash", "liquidity", "liquid", "spend"]),
        ("income", ["income", "dividend", "yield", "interest"]),
        ("documents", ["document", "statement", "upload", "file", "vault"]),
    ]

    def _detect_intent(self, question: str) -> str:
        q = question.lower()
        scores = {intent: sum(1 for kw in keywords if kw in q) for intent, keywords in self.INTENTS}
        best = max(scores.items(), key=lambda kv: kv[1])
        return best[0] if best[1] > 0 else "overview"

    def answer(self, question: str, context: AIContext) -> AgentAnswer:
        intent = self._detect_intent(question)
        currency = context.currency
        facts: list[SupportingFact] = []
        routes: list[NextAction] = []
        followups: list[str] = []

        def fact(label: str, value: str, raw: float | None = None) -> None:
            facts.append(SupportingFact(label=label, value=value, raw_value=raw, as_of=context.as_of))

        if intent == "net_worth":
            nw = context.net_worth or {}
            answer = (
                f"Net worth is {_money(float(nw.get('net_worth') or 0), currency)} as of "
                f"{context.as_of.isoformat()} — {_money(float(nw.get('total_assets') or 0), currency)} in assets "
                f"less {_money(float(nw.get('total_liabilities') or 0), currency)} of liabilities."
            )
            fact("Net worth", _money(float(nw.get("net_worth") or 0), currency), nw.get("net_worth"))
            fact("Total assets", _money(float(nw.get("total_assets") or 0), currency), nw.get("total_assets"))
            fact("Total liabilities", _money(float(nw.get("total_liabilities") or 0), currency), nw.get("total_liabilities"))
            followups = ["What is driving the change in net worth?", "How is my portfolio allocated?"]
            routes = [NextAction(key="accounts", label="View accounts", description="See every linked account and balance.", route="/accounts", category="accounts")]

        elif intent == "performance":
            ytd = (context.performance or {}).get("YTD") or {}
            answer = (
                f"Year to date the portfolio returned {_percent(float(ytd.get('return') or 0))} against "
                f"{_percent(float(ytd.get('benchmark_return') or 0))} for the benchmark — "
                f"{'ahead' if float(ytd.get('excess_return') or 0) >= 0 else 'behind'} by "
                f"{_percent(abs(float(ytd.get('excess_return') or 0)))}. "
                f"Portfolio value is {_money(float((context.portfolio or {}).get('market_value') or 0), currency)}."
            )
            fact("YTD return", _percent(float(ytd.get("return") or 0)), ytd.get("return"))
            fact("Benchmark YTD", _percent(float(ytd.get("benchmark_return") or 0)), ytd.get("benchmark_return"))
            fact("Excess return", _percent(float(ytd.get("excess_return") or 0)), ytd.get("excess_return"))
            followups = ["How does that compare over one year?", "What drove the difference?"]
            routes = [NextAction(key="portfolio", label="Open performance", description="Full performance history and benchmark comparison.", route="/portfolio", category="portfolio")]

        elif intent == "allocation":
            rows = (context.allocation or {}).get("rows", [])[:5]
            listed = ", ".join(f"{_label(str(r['key']))} {_percent(float(r['weight']))}" for r in rows)
            answer = f"The portfolio is allocated as follows: {listed}." if listed else "No allocation data is available."
            for r in rows:
                fact(_label(str(r["key"])), _percent(float(r["weight"])), r.get("weight"))
            breaches = int((context.drift or {}).get("breach_count") or 0)
            if breaches:
                answer += f" {breaches} asset class(es) currently sit outside their tolerance band."
            followups = ["Am I drifting from my targets?", "What would a rebalance look like?"]
            routes = [NextAction(key="portfolio", label="Open portfolio", description="Allocation, sector and geography breakdowns.", route="/portfolio", category="portfolio")]

        elif intent == "concentration":
            top = (context.concentration or {}).get("top_single_name") or (context.concentration or {}).get("top_position") or {}
            answer = (
                f"The largest position is {top.get('symbol')} at {_percent(float(top.get('weight') or 0))} of the "
                f"portfolio ({_money(float(top.get('market_value') or 0), currency)}). The top five holdings account "
                f"for {_percent(float((context.concentration or {}).get('top_five_weight') or 0))}. "
                f"Portfolio beta is {(context.risk or {}).get('beta', 'n/a')}."
            )
            fact("Largest position", str(top.get("symbol") or "n/a"))
            fact("Weight", _percent(float(top.get("weight") or 0)), top.get("weight"))
            fact("Top five weight", _percent(float((context.concentration or {}).get("top_five_weight") or 0)))
            followups = ["How would trimming it affect my taxes?", "What is my portfolio beta?"]
            routes = [NextAction(key="holdings", label="View holdings", description="Every position with weight and gain/loss.", route="/holdings", category="portfolio")]

        elif intent == "goals":
            goals = (context.goals or {}).get("goals", [])
            if goals:
                lines = [
                    f"{g.get('name')} is {_percent(float(g.get('funded_ratio') or 0))} funded ({str(g.get('status')).replace('_', ' ')})"
                    for g in goals[:4]
                ]
                answer = "Across the goals on file: " + "; ".join(lines) + "."
                for g in goals[:4]:
                    fact(str(g.get("name")), f"{_percent(float(g.get('funded_ratio') or 0))} funded", g.get("funded_ratio"))
            else:
                answer = "No goals have been set up yet."
            followups = ["What if I save more each month?", "What if returns are lower than expected?"]
            routes = [NextAction(key="goals", label="Open goals", description="Track progress and compare scenarios.", route="/goals", category="goal")]

        elif intent == "tax":
            harvest = (context.tax or {}).get("harvest") or {}
            gains = (context.tax or {}).get("realized") or {}
            answer = (
                f"Realised gains this year total {_money(float(gains.get('net_gain') or 0), currency)} "
                f"({_money(float(gains.get('short_term_gain') or 0), currency)} short term, "
                f"{_money(float(gains.get('long_term_gain') or 0), currency)} long term). "
                f"There are {harvest.get('opportunity_count', 0)} harvesting candidate(s) with an estimated benefit of "
                f"{_money(float(harvest.get('total_estimated_benefit') or 0), currency)}."
            )
            fact("Net realised gain", _money(float(gains.get("net_gain") or 0), currency), gains.get("net_gain"))
            fact("Harvest candidates", str(harvest.get("opportunity_count", 0)))
            fact("Estimated benefit", _money(float(harvest.get("total_estimated_benefit") or 0), currency))
            followups = ["Which lots should I harvest first?", "Am I at risk of a wash sale?"]
            routes = [NextAction(key="tax", label="Open Tax Center", description="Opportunities, harvesting and projections.", route="/tax", category="tax", requires_approval=True)]

        elif intent == "estate":
            estate = context.estate or {}
            answer = (
                f"The estate is valued at {_money(float(estate.get('gross_estate') or 0), currency)} with an estimated "
                f"federal estate tax of {_money(float(estate.get('estimated_federal_tax') or 0), currency)}. "
                f"Documents were last reviewed on {estate.get('last_reviewed_on', 'an unrecorded date')}."
            )
            fact("Gross estate", _money(float(estate.get("gross_estate") or 0), currency))
            fact("Estimated federal tax", _money(float(estate.get("estimated_federal_tax") or 0), currency))
            gaps = estate.get("beneficiary_gaps") or []
            if gaps:
                answer += f" {len(gaps)} account(s) still need a beneficiary designation."
                fact("Beneficiary gaps", str(len(gaps)), len(gaps))
            followups = ["Which accounts are missing beneficiaries?", "When should I next review my documents?"]
            routes = [NextAction(key="estate", label="Open estate", description="Wills, trusts, POAs and beneficiaries.", route="/estate", category="estate")]

        elif intent == "philanthropy":
            giving = context.philanthropy or {}
            answer = (
                f"The donor-advised fund holds {_money(float(giving.get('daf_balance') or 0), currency)}. "
                f"{_money(float(giving.get('granted_ytd') or 0), currency)} has been granted this year against a target "
                f"of {_money(float(giving.get('annual_grant_target') or 0), currency)}."
            )
            fact("DAF balance", _money(float(giving.get("daf_balance") or 0), currency))
            fact("Granted year to date", _money(float(giving.get("granted_ytd") or 0), currency))
            followups = ["What is the tax benefit of giving appreciated stock?", "Which charities have I supported?"]
            routes = [NextAction(key="philanthropy", label="Open philanthropy", description="Giving dashboard, grants and deduction impact.", route="/philanthropy", category="philanthropy")]

        elif intent == "cash":
            cash_value = float((context.portfolio or {}).get("cash") or 0)
            answer = (
                f"Cash holdings total {_money(cash_value, currency)}, "
                f"{_percent(float((context.risk or {}).get('cash_exposure') or 0))} of the portfolio."
            )
            fact("Cash", _money(cash_value, currency), cash_value)
            followups = ["Should I deploy some of this cash?", "What is my liquidity profile?"]
            routes = [NextAction(key="accounts", label="View accounts", description="Balances across banking and brokerage.", route="/accounts", category="accounts")]

        elif intent == "income":
            income = context.income or {}
            answer = (
                f"The portfolio is projected to generate {_money(float(income.get('annual_income') or 0), currency)} "
                f"over the next twelve months, a yield of {_percent(float(income.get('portfolio_yield') or 0))}. "
                f"{_money(float(income.get('municipal_income') or 0), currency)} of that is municipal income."
            )
            fact("Projected annual income", _money(float(income.get("annual_income") or 0), currency))
            fact("Portfolio yield", _percent(float(income.get("portfolio_yield") or 0)))
            followups = ["Which holdings generate the most income?", "How much of my income is tax exempt?"]
            routes = [NextAction(key="portfolio", label="Open income view", description="Income by holding and tax character.", route="/portfolio", category="portfolio")]

        elif intent == "documents":
            docs = context.documents or {}
            answer = (
                f"The vault holds {docs.get('total', 0)} document(s). "
                f"{len(docs.get('expiring_soon') or [])} expire within 90 days and "
                f"{docs.get('pending_review', 0)} are awaiting review."
            )
            fact("Documents", str(docs.get("total", 0)))
            followups = ["Which documents expire soon?", "What still needs my review?"]
            routes = [NextAction(key="documents", label="Open document vault", description="Search, upload and share documents.", route="/documents", category="document")]

        else:
            nw = context.net_worth or {}
            pf = context.portfolio or {}
            answer = (
                f"Here is the picture as of {context.as_of.isoformat()}: net worth "
                f"{_money(float(nw.get('net_worth') or 0), currency)}, portfolio value "
                f"{_money(float(pf.get('market_value') or 0), currency)}, unrealised gain "
                f"{_money(float(pf.get('unrealized_gain') or 0), currency)}. "
                "Ask about performance, allocation, goals, tax or estate for detail on any of these."
            )
            fact("Net worth", _money(float(nw.get("net_worth") or 0), currency), nw.get("net_worth"))
            fact("Portfolio value", _money(float(pf.get("market_value") or 0), currency), pf.get("market_value"))
            followups = [
                "How is my portfolio performing this year?",
                "Am I on track for retirement?",
                "Are there tax opportunities available?",
            ]
            routes = [NextAction(key="dashboard", label="Open dashboard", description="Net worth, portfolio, goals and alerts.", route="/dashboard", category="overview")]

        return AgentAnswer(
            answer=answer,
            intent=intent,
            grounded_facts=facts,
            related_routes=routes,
            followups=followups,
            confidence=0.9 if intent != "overview" else 0.7,
            source="mock_rules",
        )
