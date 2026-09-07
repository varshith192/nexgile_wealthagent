"""Client experience: dashboard, accounts, portfolio, holdings, goals."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.constants import Permission
from app.core.deps import CurrentUser, DbSession, require, resolve_household_id
from app.core.errors import NotFoundError
from app.models.wealth import Account
from app.notifications.service import NotificationService
from app.schemas.requests import GoalCreateRequest, GoalUpdateRequest, ScenarioRequest
from app.services.auth_service import AuthService
from app.services.collaboration_service import MeetingService, MessagingService
from app.services.goal_service import GoalService
from app.services.portfolio_service import PortfolioService
from app.services.tax_service import TaxService
from app.services.wealthagent_service import WealthAgentService

router = APIRouter(tags=["client"])

WealthRead = Annotated[object, Depends(require(Permission.VIEW_OWN_WEALTH, Permission.VIEW_CLIENT_WEALTH))]


@router.get("/dashboard")
def dashboard(
    db: DbSession,
    user: CurrentUser,
    _: WealthRead,
    household_id: str | None = Query(default=None),
) -> dict:
    """Everything the client dashboard renders, from one authorised call (§10)."""
    hid = resolve_household_id(db, user, household_id)
    portfolio = PortfolioService(db)
    agent = WealthAgentService(db)
    as_of = portfolio.as_of(hid)

    context = agent.build_context(hid)
    insights = [i.model_dump(mode="json") for i in agent.ai.insights(context)]
    notifications = NotificationService(db).list(user, limit=8, household_ids=[hid])

    upcoming = MeetingService(db).list(hid)
    goals = GoalService(db).summary(hid, as_of)

    needs_attention = [
        {
            "key": i["key"],
            "title": i["title"],
            "category": i["category"],
            "severity": i["severity"],
            "summary": i["summary"],
            "action_url": i.get("action_url"),
        }
        for i in insights
        if i["severity"] in {"critical", "high", "medium"}
    ][:6]

    return {
        "household": {"id": hid, "name": context.household_name},
        "as_of": as_of.isoformat(),
        "net_worth": portfolio.net_worth(hid),
        "net_worth_trend": portfolio.net_worth_trend(hid),
        "portfolio": portfolio.valuation(hid),
        "allocation": portfolio.allocation(hid),
        "concentration": portfolio.concentration(hid),
        "risk": portfolio.risk(hid),
        "performance": portfolio.performance(hid),
        "top_holdings": portfolio.holdings_table(hid, page_size=5)["rows"],
        "goals": goals,
        "needs_attention": needs_attention,
        "wealthagent": {
            "provider": agent.ai.info.model_dump(),
            "insights": insights[:4],
            "actions": [a.model_dump(mode="json") for a in agent.ai.actions(context)][:4],
        },
        "notifications": notifications,
        "next_meeting": upcoming["next_meeting"],
        "data_freshness": portfolio.data_freshness(hid),
    }


# ---------------------------------------------------------------- accounts
@router.get("/accounts")
def accounts(db: DbSession, user: CurrentUser, _: WealthRead, household_id: str | None = None) -> dict:
    hid = resolve_household_id(db, user, household_id)
    return PortfolioService(db).accounts_view(hid)


@router.get("/accounts/{account_id}")
def account_detail(account_id: str, db: DbSession, user: CurrentUser, _: WealthRead) -> dict:
    account = db.get(Account, account_id)
    if not account:
        raise NotFoundError("Account not found.")
    # Proves the caller may see this household before any figures are returned.
    resolve_household_id(db, user, account.household_id)
    return PortfolioService(db).account_detail(account_id)


# --------------------------------------------------------------- portfolio
@router.get("/portfolio")
def portfolio_overview(db: DbSession, user: CurrentUser, _: WealthRead, household_id: str | None = None) -> dict:
    hid = resolve_household_id(db, user, household_id)
    service = PortfolioService(db)
    return {
        "household_id": hid,
        "as_of": service.as_of(hid).isoformat(),
        "valuation": service.valuation(hid),
        "allocation": service.allocation(hid, "asset_class"),
        "sector_allocation": service.allocation(hid, "sector"),
        "geography_allocation": service.allocation(hid, "region"),
        "drift": service.drift(hid),
        "concentration": service.concentration(hid),
        "risk": service.risk(hid),
        "income": service.income(hid),
        "performance": service.performance(hid),
        "targets": service.allocation_targets(hid),
        "data_freshness": service.data_freshness(hid),
    }


@router.get("/portfolio/performance")
def portfolio_performance(
    db: DbSession,
    user: CurrentUser,
    _: WealthRead,
    household_id: str | None = None,
    period: str | None = Query(default=None, pattern="^(1D|1W|1M|3M|YTD|1Y|3Y|5Y)$"),
) -> dict:
    hid = resolve_household_id(db, user, household_id)
    return PortfolioService(db).performance(hid, period)


@router.get("/portfolio/analytics")
def portfolio_analytics(db: DbSession, user: CurrentUser, _: WealthRead, household_id: str | None = None) -> dict:
    """Advisor-grade analytics: correlation, frontier, stress, liquidity, ESG (§22)."""
    hid = resolve_household_id(db, user, household_id)
    return PortfolioService(db).advisory_analytics(hid)


# ---------------------------------------------------------------- holdings
@router.get("/holdings")
def holdings(
    db: DbSession,
    user: CurrentUser,
    _: WealthRead,
    household_id: str | None = None,
    search: str | None = None,
    asset_class: str | None = None,
    account_id: str | None = None,
    sort_by: str = Query(default="market_value"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=5, le=200),
) -> dict:
    hid = resolve_household_id(db, user, household_id)
    allowed_sorts = {
        "symbol", "name", "quantity", "price", "market_value", "cost_basis",
        "gain_loss", "gain_loss_percent", "weight", "asset_class", "day_change",
    }
    if sort_by not in allowed_sorts:
        sort_by = "market_value"
    return PortfolioService(db).holdings_table(
        hid,
        search=search,
        asset_class=asset_class,
        account_id=account_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get("/holdings/{holding_id}")
def holding_detail(holding_id: str, db: DbSession, user: CurrentUser, _: WealthRead) -> dict:
    return PortfolioService(db).holding_detail(holding_id)


# ------------------------------------------------------------------- goals
@router.get("/goals")
def list_goals(db: DbSession, user: CurrentUser, _: WealthRead, household_id: str | None = None) -> dict:
    hid = resolve_household_id(db, user, household_id)
    service = GoalService(db)
    as_of = PortfolioService(db).as_of(hid)
    return service.summary(hid, as_of)


@router.post("/goals", status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreateRequest,
    db: DbSession,
    user: Annotated[object, Depends(require(Permission.MANAGE_GOALS))],
) -> dict:
    hid = resolve_household_id(db, user, payload.household_id)
    goal = GoalService(db).create(hid, payload.model_dump(exclude={"household_id"}), user)
    as_of = PortfolioService(db).as_of(hid)
    return GoalService(db).detail(goal.id, as_of)


@router.get("/goals/{goal_id}")
def goal_detail(goal_id: str, db: DbSession, user: CurrentUser, _: WealthRead) -> dict:
    service = GoalService(db)
    goal = service.get(goal_id)
    resolve_household_id(db, user, goal.household_id)
    return service.detail(goal_id, PortfolioService(db).as_of(goal.household_id))


@router.patch("/goals/{goal_id}")
def update_goal(
    goal_id: str,
    payload: GoalUpdateRequest,
    db: DbSession,
    user: Annotated[object, Depends(require(Permission.MANAGE_GOALS))],
) -> dict:
    service = GoalService(db)
    goal = service.get(goal_id)
    resolve_household_id(db, user, goal.household_id)
    service.update(goal_id, payload.model_dump(exclude_none=True), user)
    return service.detail(goal_id, PortfolioService(db).as_of(goal.household_id))


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: str, db: DbSession, user: Annotated[object, Depends(require(Permission.MANAGE_GOALS))]
) -> None:
    service = GoalService(db)
    goal = service.get(goal_id)
    resolve_household_id(db, user, goal.household_id)
    service.delete(goal_id, user)


@router.post("/goals/{goal_id}/scenarios")
def run_goal_scenarios(
    goal_id: str, payload: ScenarioRequest, db: DbSession, user: CurrentUser, _: WealthRead
) -> dict:
    """Scenarios are projections only and never alter the books of record (§4)."""
    service = GoalService(db)
    goal = service.get(goal_id)
    resolve_household_id(db, user, goal.household_id)
    as_of = PortfolioService(db).as_of(goal.household_id)
    return service.run_scenarios(
        goal_id, as_of, scenario_keys=payload.scenario_keys, actor=user, persist=payload.persist
    )
