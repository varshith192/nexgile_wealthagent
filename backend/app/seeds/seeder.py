"""Builds the complete demonstration dataset.

Deterministic: a fixed random seed means the same command always produces the
same numbers, so screenshots, tests and demos stay in agreement.

Consistency rule: derived values are computed, never transcribed. Account
balances come from holdings; goal balances come from linked accounts; plan
assets come from participants; the performance series ends on the portfolio's
actual market value.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    ROLE_HOME,
    ROLE_LABELS,
    ROLE_PERMISSIONS,
    ApprovalStatus,
    ComplianceStatus,
    Permission,
    RebalanceStatus,
    Role,
)
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import engine
from app.models.collab import (
    ActionItem,
    Document,
    DocumentRequest,
    DocumentVersion,
    Meeting,
    Message,
    MessageThread,
)
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
from app.models.identity import (
    AdvisorAssignment,
    AdvisorTeam,
    Client,
    Household,
    HouseholdMember,
    PermissionRecord,
    RolePermission,
    RoleRecord,
    User,
)
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
from app.models.planning import Goal, GoalAccount, Recommendation, Scenario, Task
from app.models.tax import RMD, Harvest, TaxOpportunity, WashSaleWindow
from app.models.wealth import (
    Account,
    AllocationTarget,
    Benchmark,
    Custodian,
    Holding,
    PerformancePoint,
    Portfolio,
    PortfolioPosition,
    Security,
    TaxLot,
    Transaction,
)
from app.models.workflow import (
    Alert,
    Approval,
    ApprovalEvent,
    AuditEvent,
    Rebalance,
    RebalanceTrade,
    Report,
    SavedView,
    SearchHistory,
)
from app.seeds.households import HOUSEHOLDS
from app.seeds.reference import (
    BENCHMARKS,
    CHARITIES,
    CUSTODIANS,
    EDUCATION_CONTENT,
    FIRST_NAMES,
    LAST_NAMES,
    SECURITIES,
)

SEED = 20260907
PERFORMANCE_YEARS = 3
TRADING_DAYS_PER_YEAR = 252

# Every staff account uses the same demo password. Never a production credential.
STAFF = [
    ("marcus.webb@nexgile.example", "Marcus Webb", Role.ADVISOR, "Senior Wealth Advisor", "Advisor Demo", True),
    ("elena.vargas@nexgile.example", "Elena Vargas", Role.ADVISOR, "Wealth Advisor", None, False),
    ("priya.raman@nexgile.example", "Priya Raman", Role.COMPLIANCE, "Head of Compliance", "Compliance Demo", True),
    ("ellen.sorensen@nexgile.example", "Ellen Sorensen", Role.ADMIN, "Managing Director", "Admin Demo", True),
    ("tobias.frank@nexgile.example", "Tobias Frank", Role.INVESTMENT_TEAM, "Portfolio Strategist", "Investment Team Demo", False),
    ("hana.mori@nexgile.example", "Hana Mori", Role.TAX_SPECIALIST, "Director of Tax Planning", "Tax Specialist Demo", False),
    ("declan.ross@nexgile.example", "Declan Ross", Role.ESTATE_TRUST, "Trust & Estate Counsel", "Estate Demo", False),
    ("noor.haddad@nexgile.example", "Noor Haddad", Role.OPERATIONS, "Client Service Manager", "Operations Demo", False),
    ("diane.ellis@brightpath.example", "Diane Ellis", Role.PLAN_SPONSOR, "VP People Operations", "Sponsor Demo", True),
    ("andre.fitzgerald@brightpath.example", "Andre Fitzgerald", Role.PARTICIPANT, "Senior Engineer", "Participant Demo", True),
]

TABLES_IN_DELETE_ORDER = [
    AuditEvent, ApprovalEvent, Approval, RebalanceTrade, Rebalance, Report, Alert, SavedView, SearchHistory,
    EducationProgress, EducationContent, ParticipantLoan, FiduciaryReview, Filing, ComplianceTest, Fee,
    InvestmentOption, Contribution, Participant, Plan, Sponsor,
    ActionItem, Message, MessageThread, Meeting, DocumentRequest, DocumentVersion, Document,
    Grant, GivingPlan, Gift, DAF, Charity, DistributionRequest, Beneficiary, PowerOfAttorney, Trust, EstatePlan,
    WashSaleWindow, Harvest, RMD, TaxOpportunity,
    Scenario, GoalAccount, Goal, Task, Recommendation,
    PerformancePoint, PortfolioPosition, AllocationTarget, Transaction, TaxLot, Holding, Portfolio,
    Account, Security, Benchmark, Custodian,
    AdvisorAssignment, AdvisorTeam, HouseholdMember, Client, Household,
    RolePermission, PermissionRecord, RoleRecord, User,
]


class DemoSeeder:
    def __init__(self, db: Session, *, today: date | None = None) -> None:
        self.db = db
        self.rng = random.Random(SEED)
        self.today = today or date.today()
        self.now = datetime.now(timezone.utc)
        self.tax_year = self.today.year

        self.users: dict[str, User] = {}
        self.securities: dict[str, Security] = {}
        self.custodians: dict[str, Custodian] = {}
        self.benchmarks: dict[str, Benchmark] = {}
        self.charities: list[Charity] = []
        self.households: dict[str, Household] = {}
        self.accounts: dict[tuple[str, str], Account] = {}
        self.portfolios: dict[str, Portfolio] = {}
        self.stats: dict[str, int] = {}

    # ------------------------------------------------------------------
    def run(self, *, reset: bool = True) -> dict[str, Any]:
        if reset:
            self.clear()
        self.seed_roles()
        self.seed_reference()
        self.seed_users()
        self.seed_households()
        self.seed_portfolios()
        self.seed_goals()
        self.seed_tax()
        self.seed_estate_and_giving()
        self.seed_documents()
        self.seed_collaboration()
        self.seed_institutional()
        self.seed_workflow()
        self.seed_notifications_and_audit()
        self.db.commit()
        return self.summary()

    def clear(self) -> None:
        Base.metadata.create_all(bind=engine)
        for model in TABLES_IN_DELETE_ORDER:
            self.db.execute(delete(model))
        self.db.commit()

    # ------------------------------------------------------------------
    def seed_roles(self) -> None:
        permissions: dict[str, PermissionRecord] = {}
        for permission in Permission:
            record = PermissionRecord(key=str(permission), description=str(permission).replace(":", " — ").replace("_", " "))
            self.db.add(record)
            permissions[str(permission)] = record

        for role, label in ROLE_LABELS.items():
            record = RoleRecord(
                key=str(role),
                label=label,
                description=f"{label} workspace and permissions.",
                home_route=ROLE_HOME.get(role, "/dashboard"),
            )
            self.db.add(record)
            self.db.flush()
            for permission in sorted(ROLE_PERMISSIONS.get(role, set()), key=str):
                self.db.add(RolePermission(role_id=record.id, permission_id=permissions[str(permission)].id))
        self.db.flush()

    def seed_reference(self) -> None:
        for name, short, connection, feed in CUSTODIANS:
            custodian = Custodian(
                name=name, short_name=short, connection_type=connection, feed_status=feed, logo_hint=short[:2].upper()
            )
            self.db.add(custodian)
            self.custodians[name] = custodian

        for code, name, description, composition in BENCHMARKS:
            benchmark = Benchmark(code=code, name=name, description=description, composition=composition)
            self.db.add(benchmark)
            self.benchmarks[code] = benchmark

        price_as_of = self.now - timedelta(hours=2)
        for (
            symbol, name, sec_type, asset_class, sector, region, price, prev, div_yield,
            expense, beta, vol, esg, municipal, identical,
        ) in SECURITIES:
            security = Security(
                symbol=symbol,
                name=name,
                security_type=sec_type,
                asset_class=asset_class,
                sector=sector,
                region=region,
                last_price=price,
                previous_close=prev,
                dividend_yield=div_yield,
                expense_ratio=expense,
                beta=beta,
                annualised_volatility=vol,
                esg_score=esg,
                is_municipal=municipal,
                substantially_identical_to=identical,
                price_as_of=price_as_of,
                price_status="fresh",
            )
            self.db.add(security)
            self.securities[symbol] = security

        for name, ein, mission, location, rating in CHARITIES:
            charity = Charity(name=name, ein_masked=ein, mission_area=mission, location=location, rating=rating)
            self.db.add(charity)
            self.charities.append(charity)

        for title, ctype, path, level, minutes, summary, body in EDUCATION_CONTENT:
            self.db.add(
                EducationContent(
                    title=title,
                    content_type=ctype,
                    learning_path=path,
                    level=level,
                    duration_minutes=minutes,
                    summary=summary,
                    body=body,
                    tags=[path.lower().replace(" ", "-"), level],
                    published_on=self.today - timedelta(days=self.rng.randint(30, 500)),
                )
            )
        self.db.flush()

    def seed_users(self) -> None:
        password = hash_password(settings.demo_password)
        for email, full_name, role, title, demo_label, is_demo in STAFF:
            user = User(
                email=email,
                full_name=full_name,
                role=str(role),
                title=title,
                phone=f"+1-503-555-{self.rng.randint(1000, 9999)}",
                avatar_initials="".join(p[0] for p in full_name.split()[:2]).upper(),
                password_hash=password,
                is_active=True,
                is_demo=is_demo,
                demo_label=demo_label,
                timezone="America/Los_Angeles",
            )
            self.db.add(user)
            self.users[email] = user

        team = AdvisorTeam(name="Pacific Northwest Private Wealth", region="West")
        self.db.add(team)
        self.db.flush()
        team.lead_advisor_id = self.users["marcus.webb@nexgile.example"].id
        self.team = team

    # ------------------------------------------------------------------
    def seed_households(self) -> None:
        password = hash_password(settings.demo_password)
        advisors = [self.users["marcus.webb@nexgile.example"], self.users["elena.vargas@nexgile.example"]]

        for index, blueprint in enumerate(HOUSEHOLDS):
            advisor = advisors[0]
            second_chair = advisors[1]
            household = Household(
                name=blueprint["name"],
                segment=blueprint["segment"],
                primary_advisor_id=advisor.id,
                risk_profile=blueprint["risk_profile"],
                since=date.fromisoformat(blueprint["since"]),
                city=blueprint["city"],
                state=blueprint["state"],
                notes=blueprint["notes"],
            )
            self.db.add(household)
            self.db.flush()
            self.households[blueprint["key"]] = household

            self.db.add(
                AdvisorAssignment(
                    advisor_id=advisor.id,
                    household_id=household.id,
                    team_id=self.team.id,
                    role_on_account="lead_advisor",
                    is_primary=True,
                )
            )
            self.db.add(
                AdvisorAssignment(
                    advisor_id=self.users["noor.haddad@nexgile.example"].id,
                    household_id=household.id,
                    team_id=self.team.id,
                    role_on_account="client_service",
                    is_primary=False,
                )
            )
            if index % 2 == 1:
                self.db.add(
                    AdvisorAssignment(
                        advisor_id=second_chair.id,
                        household_id=household.id,
                        team_id=self.team.id,
                        role_on_account="associate_advisor",
                        is_primary=False,
                    )
                )

            for principal in blueprint["principals"]:
                user = None
                if principal.get("is_demo_user"):
                    email = f"{principal['full_name'].split()[0].lower()}.{principal['full_name'].split()[-1].lower()}@example.com"
                    user = User(
                        email=email,
                        full_name=principal["full_name"],
                        role=str(Role.CLIENT),
                        title="Private Client",
                        avatar_initials="".join(p[0] for p in principal["full_name"].split()[:2]).upper(),
                        password_hash=password,
                        is_demo=True,
                        demo_label="Client Demo",
                        timezone="America/Los_Angeles",
                    )
                    self.db.add(user)
                    self.db.flush()
                    self.users[email] = user

                client = Client(
                    user_id=user.id if user else None,
                    household_id=household.id,
                    full_name=principal["full_name"],
                    birth_date=date.fromisoformat(principal["birth_date"]),
                    retirement_age=principal["retirement_age"],
                    filing_status=principal["filing_status"],
                    marginal_tax_rate=principal["marginal_tax_rate"],
                    ltcg_tax_rate=principal["ltcg_tax_rate"],
                    state_tax_rate=principal["state_tax_rate"],
                    annual_income=principal["annual_income"],
                    annual_savings=principal["annual_savings"],
                    risk_tolerance=principal["risk_tolerance"],
                    segment=blueprint["segment"],
                    onboarded_on=date.fromisoformat(blueprint["since"]),
                )
                self.db.add(client)

            for member in blueprint["members"]:
                self.db.add(
                    HouseholdMember(
                        household_id=household.id,
                        full_name=member["full_name"],
                        relationship_type=member["relationship_type"],
                        birth_date=date.fromisoformat(member["birth_date"]),
                        is_dependent=member["is_dependent"],
                    )
                )
            self.db.flush()

    # ------------------------------------------------------------------
    def seed_portfolios(self) -> None:
        for blueprint in HOUSEHOLDS:
            household = self.households[blueprint["key"]]
            benchmark = self.benchmarks[blueprint["benchmark"]]
            portfolio = Portfolio(
                household_id=household.id,
                name=f"{household.name} Managed Portfolio",
                strategy=blueprint["strategy"],
                benchmark_id=benchmark.id,
                inception_date=date.fromisoformat(blueprint["since"]),
                management_fee_bps=75,
                as_of=self.now,
            )
            self.db.add(portfolio)
            self.db.flush()
            self.portfolios[blueprint["key"]] = portfolio

            for asset_class, weight in blueprint["targets"].items():
                self.db.add(
                    AllocationTarget(
                        portfolio_id=portfolio.id,
                        asset_class=asset_class,
                        kind="strategic",
                        target_weight=weight,
                        min_weight=max(weight - 0.10, 0.0),
                        max_weight=min(weight + 0.10, 1.0),
                        tolerance_band=0.05 if weight >= 0.10 else 0.03,
                    )
                )
                self.db.add(
                    AllocationTarget(
                        portfolio_id=portfolio.id,
                        asset_class=asset_class,
                        kind="tactical",
                        target_weight=round(min(max(weight + self.rng.uniform(-0.02, 0.02), 0.0), 1.0), 4),
                        tolerance_band=0.03,
                    )
                )

            invested_total = 0.0
            for spec in blueprint["accounts"]:
                account = self._create_account(household, spec)
                if spec.get("holdings"):
                    invested_total += self._create_holdings(account, portfolio, spec)
                self.db.flush()

            self._create_performance_series(portfolio, invested_total, blueprint)
            self._create_positions_snapshot(portfolio, household)

    def _create_account(self, household: Household, spec: dict) -> Account:
        custodian = self.custodians[spec["custodian"]]
        is_liability = "liability" in spec
        sync_offset = {
            "direct_feed": timedelta(hours=self.rng.randint(1, 6)),
            "aggregated": timedelta(hours=self.rng.randint(6, 20)),
            "manual": timedelta(days=self.rng.randint(5, 12)),
        }[custodian.connection_type]

        account = Account(
            household_id=household.id,
            custodian_id=custodian.id,
            name=spec["name"],
            account_number_masked=f"****{self.rng.randint(1000, 9999)}",
            account_type=spec["account_type"],
            account_subtype=spec.get("subtype"),
            tax_treatment=spec.get("tax_treatment", "taxable"),
            registration=spec.get("registration", "individual"),
            currency="USD",
            balance=spec.get("liability") or spec.get("cash_only") or 0.0,
            cash_balance=spec.get("cash", 0.0) if not is_liability else 0.0,
            is_liability=is_liability,
            interest_rate=spec.get("interest_rate"),
            minimum_payment=spec.get("minimum_payment"),
            status="active",
            is_external=spec.get("external", False),
            opened_on=date.fromisoformat(spec["opened_on"]),
            last_synced_at=self.now - sync_offset,
            data_source=f"{custodian.short_name} {custodian.connection_type}",
        )
        self.db.add(account)
        self.db.flush()
        self.accounts[(household.id, spec["name"])] = account
        return account

    def _create_holdings(self, account: Account, portfolio: Portfolio, spec: dict) -> float:
        """Create holdings, lots and buy transactions; derive the account balance."""
        target = float(spec["target_value"])
        market_value = 0.0

        for entry in spec["holdings"]:
            security = self.securities[entry["symbol"]]
            allocated = target * entry["weight"]
            quantity = round(allocated / security.last_price, 4)
            gain = entry["gain"]
            average_cost = round(security.last_price / (1 + gain), 4)
            actual_value = quantity * security.last_price
            market_value += actual_value

            # Older positions for larger gains keeps holding periods plausible.
            years_held = min(max(abs(gain) * 3.2 + 0.8, 0.6), 11.0)
            acquired = self.today - timedelta(days=int(years_held * 365))
            acquired = max(acquired, account.opened_on)

            holding = Holding(
                account_id=account.id,
                security_id=security.id,
                portfolio_id=portfolio.id,
                quantity=quantity,
                average_cost=average_cost,
                acquired_on=acquired,
                as_of=self.now,
            )
            self.db.add(holding)
            self.db.flush()

            # Split into two or three lots so tax-lot views have real depth.
            lot_count = 3 if quantity > 200 else 2
            remaining = quantity
            for lot_index in range(lot_count):
                lot_quantity = round(remaining / (lot_count - lot_index), 4)
                remaining = round(remaining - lot_quantity, 4)
                lot_days = int(years_held * 365 * (1 - lot_index * 0.28))
                lot_date = max(self.today - timedelta(days=max(lot_days, 45)), account.opened_on)
                # Cost drifts around the average so each lot has its own gain.
                drift = 1 + (lot_index - (lot_count - 1) / 2) * 0.11
                lot_cost = round(average_cost * drift, 4)
                self.db.add(
                    TaxLot(
                        holding_id=holding.id,
                        quantity=lot_quantity,
                        cost_per_share=lot_cost,
                        acquired_on=lot_date,
                        lot_method="FIFO",
                        is_open=True,
                    )
                )
                self.db.add(
                    Transaction(
                        account_id=account.id,
                        security_id=security.id,
                        transaction_type="buy",
                        quantity=lot_quantity,
                        price=lot_cost,
                        amount=round(-lot_quantity * lot_cost, 2),
                        trade_date=lot_date,
                        settle_date=lot_date + timedelta(days=2),
                        description=f"Purchase {security.symbol}",
                    )
                )

        self._create_income_and_sales(account)
        account.balance = round(market_value + (account.cash_balance or 0.0), 2)
        return market_value

    def _create_income_and_sales(self, account: Account) -> None:
        """Dividends and a handful of realised sales so the tax view has data."""
        holdings = self.db.execute(select(Holding).where(Holding.account_id == account.id)).scalars().all()
        for holding in holdings[:4]:
            security = self.db.get(Security, holding.security_id)
            if not security.dividend_yield:
                continue
            for quarter in range(1, 4):
                pay_date = self.today - timedelta(days=90 * quarter)
                if pay_date < account.opened_on:
                    continue
                amount = holding.quantity * security.last_price * security.dividend_yield / 4
                self.db.add(
                    Transaction(
                        account_id=account.id,
                        security_id=security.id,
                        transaction_type="dividend",
                        amount=round(amount, 2),
                        trade_date=pay_date,
                        settle_date=pay_date,
                        description=f"{security.symbol} dividend",
                    )
                )

        if account.tax_treatment != "taxable" or not holdings:
            return

        for holding in holdings[:2]:
            security = self.db.get(Security, holding.security_id)
            sale_date = self.today - timedelta(days=self.rng.randint(40, 220))
            if sale_date.year != self.tax_year or sale_date < account.opened_on:
                sale_date = date(self.tax_year, max(self.today.month - 3, 1), 12)
            quantity = round(holding.quantity * 0.06, 4)
            proceeds = quantity * security.last_price * 0.97
            cost = quantity * holding.average_cost
            gain = proceeds - cost
            long_term = (sale_date - (holding.acquired_on or sale_date)).days >= 366
            self.db.add(
                Transaction(
                    account_id=account.id,
                    security_id=security.id,
                    transaction_type="sell",
                    quantity=quantity,
                    price=round(security.last_price * 0.97, 4),
                    amount=round(proceeds, 2),
                    fees=round(proceeds * 0.0002, 2),
                    trade_date=sale_date,
                    settle_date=sale_date + timedelta(days=2),
                    description=f"Sale {security.symbol}",
                    realized_gain=round(gain, 2),
                    is_long_term=long_term,
                )
            )

    def _create_performance_series(self, portfolio: Portfolio, ending_value: float, blueprint: dict) -> None:
        """Daily series ending exactly on the portfolio's current market value."""
        if ending_value <= 0:
            return

        rng = random.Random(SEED + hash(blueprint["key"]) % 10_000)
        equity_weight = blueprint["targets"]["us_equity"] + blueprint["targets"]["intl_equity"]
        daily_vol = (0.16 * equity_weight + 0.05 * (1 - equity_weight)) / math.sqrt(TRADING_DAYS_PER_YEAR)
        daily_drift = (0.072 * equity_weight + 0.042 * (1 - equity_weight)) / TRADING_DAYS_PER_YEAR
        bench_vol = daily_vol * 0.94
        bench_drift = daily_drift * 0.97

        days: list[date] = []
        cursor = self.today - timedelta(days=int(365.25 * PERFORMANCE_YEARS))
        while cursor <= self.today:
            if cursor.weekday() < 5:
                days.append(cursor)
            cursor += timedelta(days=1)

        # The benchmark shares most of its variance with the portfolio; only the
        # active return is independent. An uncorrelated series would produce
        # implausible multi-point gaps over a single year.
        returns = [rng.gauss(daily_drift, daily_vol) for _ in days]
        tracking_vol = daily_vol * 0.22
        bench_returns = [
            bench_drift + (r - daily_drift) * (bench_vol / daily_vol) + rng.gauss(0.0, tracking_vol)
            for r in returns
        ]
        returns[0] = 0.0
        bench_returns[0] = 0.0

        # Work backwards from today's real market value so the series lands on it.
        values = [0.0] * len(days)
        values[-1] = ending_value
        for i in range(len(days) - 2, -1, -1):
            values[i] = values[i + 1] / (1 + returns[i + 1])

        index = 100.0
        bench_index = 100.0
        for i, day in enumerate(days):
            index *= 1 + returns[i]
            bench_index *= 1 + bench_returns[i]
            self.db.add(
                PerformancePoint(
                    portfolio_id=portfolio.id,
                    as_of=day,
                    market_value=round(values[i], 2),
                    net_flow=0.0,
                    daily_return=round(returns[i], 6),
                    benchmark_return=round(bench_returns[i], 6),
                    cumulative_index=round(index, 4),
                    benchmark_index=round(bench_index, 4),
                )
            )

    def _create_positions_snapshot(self, portfolio: Portfolio, household: Household) -> None:
        rows = self.db.execute(
            select(Holding, Security)
            .join(Security, Holding.security_id == Security.id)
            .join(Account, Holding.account_id == Account.id)
            .where(Account.household_id == household.id)
        ).all()
        total = sum(h.quantity * s.last_price for h, s in rows) or 1.0
        for holding, security in rows:
            value = holding.quantity * security.last_price
            self.db.add(
                PortfolioPosition(
                    portfolio_id=portfolio.id,
                    security_id=security.id,
                    quantity=holding.quantity,
                    market_value=round(value, 2),
                    cost_basis=round(holding.quantity * holding.average_cost, 2),
                    weight=round(value / total, 6),
                    as_of=self.today,
                )
            )

    # ------------------------------------------------------------------
    def seed_goals(self) -> None:
        for blueprint in HOUSEHOLDS:
            household = self.households[blueprint["key"]]
            client = self.db.execute(
                select(Client).where(Client.household_id == household.id).order_by(Client.created_at)
            ).scalars().first()

            for spec in blueprint["goals"]:
                linked = [self.accounts[(household.id, n)] for n in spec.get("current_from_accounts", [])]
                if linked:
                    current = sum(a.balance for a in linked) * spec.get("current_ratio", 1.0)
                else:
                    current = spec.get("current_amount", 0.0)

                goal = Goal(
                    household_id=household.id,
                    client_id=client.id if client else None,
                    name=spec["name"],
                    goal_type=spec["goal_type"],
                    description=spec.get("description"),
                    target_amount=spec["target_amount"],
                    current_amount=round(current, 2),
                    target_date=date.fromisoformat(spec["target_date"]),
                    monthly_contribution=spec["monthly_contribution"],
                    expected_return=spec["expected_return"],
                    inflation_rate=spec["inflation_rate"],
                    priority=spec["priority"],
                    owner_label=spec.get("owner_label"),
                    status="on_track",
                )
                self.db.add(goal)
                self.db.flush()

                for account in linked:
                    self.db.add(
                        GoalAccount(
                            goal_id=goal.id,
                            account_id=account.id,
                            allocation_percent=spec.get("current_ratio", 1.0),
                        )
                    )

                self.db.add(
                    Scenario(
                        goal_id=goal.id,
                        household_id=household.id,
                        name="Base Case",
                        scenario_key="base_case",
                        inputs={
                            "monthly_contribution": spec["monthly_contribution"],
                            "expected_return": spec["expected_return"],
                            "target_date": spec["target_date"],
                        },
                        assumptions={"list": ["Contributions continue uninterrupted", "Constant expected return"]},
                        result={},
                        is_baseline=True,
                        run_at=self.now - timedelta(days=self.rng.randint(2, 30)),
                    )
                )

    # ------------------------------------------------------------------
    def seed_tax(self) -> None:
        for blueprint in HOUSEHOLDS:
            household = self.households[blueprint["key"]]
            client = self.db.execute(
                select(Client).where(Client.household_id == household.id).order_by(Client.created_at)
            ).scalars().first()

            loss_lots = self.db.execute(
                select(TaxLot, Holding, Security, Account)
                .join(Holding, TaxLot.holding_id == Holding.id)
                .join(Security, Holding.security_id == Security.id)
                .join(Account, Holding.account_id == Account.id)
                .where(Account.household_id == household.id, Account.tax_treatment == "taxable")
            ).all()

            candidates = [
                (lot, holding, security, account)
                for lot, holding, security, account in loss_lots
                if lot.quantity * (security.last_price - lot.cost_per_share) < -2_500
            ]
            candidates.sort(key=lambda row: row[0].quantity * (row[2].last_price - row[0].cost_per_share))

            total_benefit = 0.0
            for lot, holding, security, account in candidates[:3]:
                loss = lot.quantity * (security.last_price - lot.cost_per_share)
                long_term = (self.today - lot.acquired_on).days >= 366
                rate = (client.ltcg_tax_rate if long_term else client.marginal_tax_rate) + client.state_tax_rate
                benefit = abs(loss) * rate
                total_benefit += benefit
                replacement = next(
                    (
                        s
                        for s in self.securities.values()
                        if s.asset_class == security.asset_class
                        and s.id != security.id
                        and s.symbol != (security.substantially_identical_to or "")
                    ),
                    None,
                )
                self.db.add(
                    Harvest(
                        household_id=household.id,
                        account_id=account.id,
                        security_id=security.id,
                        tax_lot_id=lot.id,
                        replacement_security_id=replacement.id if replacement else None,
                        quantity=lot.quantity,
                        cost_basis=round(lot.quantity * lot.cost_per_share, 2),
                        market_value=round(lot.quantity * security.last_price, 2),
                        unrealized_loss=round(loss, 2),
                        holding_period="long_term" if long_term else "short_term",
                        estimated_tax_benefit=round(benefit, 2),
                        wash_sale_risk="clear",
                        wash_sale_window_ends=self.today + timedelta(days=30),
                        status="identified",
                        tax_year=self.tax_year,
                        notes=f"Replacement candidate: {replacement.symbol if replacement else 'none identified'}",
                    )
                )

            if total_benefit > 0:
                self.db.add(
                    TaxOpportunity(
                        household_id=household.id,
                        opportunity_type="tax_loss_harvest",
                        title="Harvest available losses before year end",
                        description=(
                            f"{len(candidates[:3])} lots hold unrealised losses that can offset realised gains "
                            "of the same character this year."
                        ),
                        estimated_benefit=round(total_benefit, 2),
                        tax_year=self.tax_year,
                        severity="medium",
                        status="identified",
                        deadline=date(self.tax_year, 12, 31),
                        assumptions=["Losses are usable against gains of the same character this year."],
                        supporting_data={"candidate_count": len(candidates[:3])},
                        as_of=self.now,
                    )
                )

            taxable_accounts = [
                a for a in self.db.execute(
                    select(Account).where(Account.household_id == household.id, Account.tax_treatment == "taxable")
                ).scalars().all()
            ]
            if taxable_accounts:
                self.db.add(
                    TaxOpportunity(
                        household_id=household.id,
                        account_id=taxable_accounts[0].id,
                        opportunity_type="asset_location",
                        title="Relocate taxable bond income to a tax-deferred account",
                        description="Corporate bond income held in a taxable account is taxed at ordinary rates.",
                        estimated_benefit=round(taxable_accounts[0].balance * 0.0012, 2),
                        tax_year=self.tax_year,
                        severity="low",
                        status="identified",
                        deadline=date(self.tax_year, 12, 31),
                        assumptions=["Income taxed at a 35% ordinary rate.", "Repositioning uses new contributions only."],
                        as_of=self.now,
                    )
                )
                self.db.add(
                    TaxOpportunity(
                        household_id=household.id,
                        opportunity_type="charitable_securities",
                        title="Fund charitable giving with appreciated securities",
                        description="Gifting long-term appreciated shares avoids the capital gain and preserves the deduction.",
                        estimated_benefit=round(taxable_accounts[0].balance * 0.0035, 2),
                        tax_year=self.tax_year,
                        severity="medium",
                        status="identified",
                        deadline=date(self.tax_year, 12, 15),
                        assumptions=["Shares held longer than one year.", "Household itemises deductions."],
                        as_of=self.now,
                    )
                )

            # A live wash-sale window on one household so the guard rail is visible.
            if blueprint["key"] == "johnson" and taxable_accounts:
                security = self.securities["VWO"]
                self.db.add(
                    WashSaleWindow(
                        account_id=taxable_accounts[0].id,
                        security_id=security.id,
                        window_start=self.today - timedelta(days=12),
                        window_end=self.today + timedelta(days=18),
                        reason="Shares purchased 12 days ago; a loss sale now would be disallowed",
                        is_active=True,
                    )
                )

            # RMDs where an account owner has reached the required age.
            if client and client.birth_date:
                age = self.today.year - client.birth_date.year
                if age >= 73:
                    ira = self.db.execute(
                        select(Account).where(
                            Account.household_id == household.id, Account.tax_treatment == "tax_deferred"
                        )
                    ).scalars().first()
                    if ira:
                        factor = 26.5 if age == 73 else max(27.4 - (age - 72), 8.9)
                        prior_balance = ira.balance * 0.94
                        required = prior_balance / factor
                        self.db.add(
                            RMD(
                                client_id=client.id,
                                account_id=ira.id,
                                tax_year=self.tax_year,
                                prior_year_end_balance=round(prior_balance, 2),
                                life_expectancy_factor=factor,
                                required_amount=round(required, 2),
                                distributed_amount=round(required * 0.36, 2),
                                deadline=date(self.tax_year, 12, 31),
                                status="pending",
                                satisfied_by_qcd=0.0,
                            )
                        )
                        self.db.add(
                            TaxOpportunity(
                                household_id=household.id,
                                account_id=ira.id,
                                opportunity_type="qcd",
                                title="Satisfy the remaining RMD with a qualified charitable distribution",
                                description="A QCD counts toward the RMD and is excluded from taxable income.",
                                estimated_benefit=round(required * 0.64 * client.marginal_tax_rate, 2),
                                tax_year=self.tax_year,
                                severity="high",
                                status="identified",
                                deadline=date(self.tax_year, 12, 31),
                                assumptions=["Account owner is over 70½.", "Recipient is a qualified public charity."],
                                as_of=self.now,
                            )
                        )

    # ------------------------------------------------------------------
    def seed_estate_and_giving(self) -> None:
        for blueprint in HOUSEHOLDS:
            household = self.households[blueprint["key"]]
            clients = self.db.execute(
                select(Client).where(Client.household_id == household.id).order_by(Client.created_at)
            ).scalars().all()
            primary = clients[0]
            members = self.db.execute(
                select(HouseholdMember).where(HouseholdMember.household_id == household.id)
            ).scalars().all()
            accounts = self.db.execute(
                select(Account).where(Account.household_id == household.id, Account.is_liability.is_(False))
            ).scalars().all()

            reviewed_years_ago = {"johnson": 4.2, "okonkwo": 1.1, "lindqvist": 2.4, "delacroix": 0.6}[blueprint["key"]]
            last_reviewed = self.today - timedelta(days=int(reviewed_years_ago * 365))

            plan = EstatePlan(
                household_id=household.id,
                plan_name=f"{household.name} Estate Plan",
                document_type="will",
                status="current" if reviewed_years_ago < 3 else "review_due",
                executed_on=last_reviewed - timedelta(days=365),
                last_reviewed_on=last_reviewed,
                next_review_due=last_reviewed + timedelta(days=int(3 * 365)),
                attorney="Whitlock & Reyes LLP",
                jurisdiction=f"{household.state}, USA",
                executor=clients[-1].full_name if len(clients) > 1 else primary.full_name,
                notes="Pour-over will directing residuary assets into the revocable trust.",
                estimated_estate_value=round(sum(a.balance for a in accounts), 2),
            )
            self.db.add(plan)
            self.db.flush()

            trust_accounts = [a for a in accounts if a.account_type == "trust"]
            for trust_account in trust_accounts:
                self.db.add(
                    Trust(
                        household_id=household.id,
                        estate_plan_id=plan.id,
                        account_id=trust_account.id,
                        name=trust_account.name,
                        trust_type="irrevocable",
                        grantor=primary.full_name,
                        trustee=clients[-1].full_name if len(clients) > 1 else "Northmoor Trust Company",
                        successor_trustee="Northmoor Trust Company",
                        funded_amount=round(trust_account.balance, 2),
                        is_funded=True,
                        established_on=trust_account.opened_on,
                        situs=household.state,
                        distribution_standard="Health, education, maintenance and support",
                        status="active",
                    )
                )

            self.db.add(
                PowerOfAttorney(
                    household_id=household.id,
                    poa_type="financial",
                    principal=primary.full_name,
                    agent=clients[-1].full_name if len(clients) > 1 else "Northmoor Trust Company",
                    successor_agent="Whitlock & Reyes LLP",
                    executed_on=last_reviewed - timedelta(days=365),
                    status="current" if reviewed_years_ago < 5 else "review_due",
                )
            )
            self.db.add(
                PowerOfAttorney(
                    household_id=household.id,
                    poa_type="healthcare",
                    principal=primary.full_name,
                    agent=clients[-1].full_name if len(clients) > 1 else members[0].full_name if members else "—",
                    executed_on=last_reviewed - timedelta(days=365),
                    status="current",
                )
            )

            # Beneficiaries; one account is deliberately left without one so the
            # gap-detection rule has something real to find.
            designation_accounts = [a for a in accounts if a.account_type in {"retirement", "trust", "education"}]
            spouse = clients[-1].full_name if len(clients) > 1 else None
            children = [m for m in members if m.relationship_type in {"child", "grandchild"}]

            for index, account in enumerate(designation_accounts):
                if blueprint["key"] == "johnson" and account.account_subtype == "roth_ira":
                    continue  # intentional gap
                if spouse and account.account_type == "retirement":
                    self.db.add(
                        Beneficiary(
                            household_id=household.id,
                            account_id=account.id,
                            full_name=spouse,
                            relationship_type="spouse",
                            designation="primary",
                            percentage=100.0,
                            status="completed",
                            last_confirmed_on=last_reviewed,
                        )
                    )
                    for child in children:
                        self.db.add(
                            Beneficiary(
                                household_id=household.id,
                                account_id=account.id,
                                full_name=child.full_name,
                                relationship_type=child.relationship_type,
                                designation="contingent",
                                percentage=round(100.0 / max(len(children), 1), 2),
                                birth_date=child.birth_date,
                                status="completed",
                                last_confirmed_on=last_reviewed,
                            )
                        )
                elif children:
                    share = round(100.0 / len(children), 2)
                    # Deliberately short of 100% on one account per household.
                    adjust = -15.0 if index == len(designation_accounts) - 1 else 0.0
                    for position, child in enumerate(children):
                        self.db.add(
                            Beneficiary(
                                household_id=household.id,
                                account_id=account.id,
                                full_name=child.full_name,
                                relationship_type=child.relationship_type,
                                designation="primary",
                                percentage=round(share + (adjust if position == 0 else 0.0), 2),
                                birth_date=child.birth_date,
                                status="completed",
                                last_confirmed_on=last_reviewed,
                            )
                        )

            if trust_accounts:
                self.db.add(
                    DistributionRequest(
                        household_id=household.id,
                        account_id=trust_accounts[0].id,
                        requested_by=primary.full_name,
                        beneficiary_name=children[0].full_name if children else primary.full_name,
                        amount=round(trust_accounts[0].balance * 0.018, 2),
                        purpose="Annual education distribution under the HEMS standard",
                        distribution_type="discretionary",
                        requested_on=self.today - timedelta(days=9),
                        status=str(ApprovalStatus.SUBMITTED),
                        tax_withholding=0.0,
                    )
                )

            # Gifting
            for index, child in enumerate(children[:2]):
                self.db.add(
                    Gift(
                        household_id=household.id,
                        recipient=child.full_name,
                        gift_type="cash",
                        amount=19_000.0 if index == 0 else 12_000.0,
                        gifted_on=date(self.tax_year, 3, 14),
                        tax_year=self.tax_year,
                        uses_annual_exclusion=True,
                        notes="Annual exclusion gift",
                    )
                )

            # Philanthropy
            charity_pool = self.charities
            vehicle_type, sponsor_org = (
                ("private_foundation", None) if blueprint["key"] == "okonkwo" else ("daf", "Rivermark Charitable Trust")
            )
            daf_balance = round(sum(a.balance for a in accounts) * 0.038, 2)
            grant_target = round(daf_balance * 0.28, 2)
            granted = round(grant_target * (0.42 if blueprint["key"] == "johnson" else 0.78), 2)

            daf = DAF(
                household_id=household.id,
                name=f"{household.name.split()[0]} Charitable Fund",
                vehicle_type=vehicle_type,
                sponsor_organisation=sponsor_org,
                balance=daf_balance,
                contributed_ytd=round(daf_balance * 0.18, 2),
                granted_ytd=granted,
                annual_grant_target=grant_target,
                payout_requirement=0.05 if vehicle_type == "private_foundation" else None,
                established_on=date.fromisoformat(blueprint["since"]) + timedelta(days=400),
                status="active",
            )
            self.db.add(daf)
            self.db.flush()

            remaining = granted
            for index, charity in enumerate(charity_pool[: 4 if blueprint["key"] != "delacroix" else 2]):
                amount = round(remaining * (0.4 if index == 0 else 0.25), 2)
                if amount <= 0:
                    break
                remaining -= amount
                self.db.add(
                    Grant(
                        daf_id=daf.id,
                        charity_id=charity.id,
                        amount=amount,
                        granted_on=date(self.tax_year, min(2 + index * 2, 12), 18),
                        purpose="Unrestricted operating support",
                        is_recurring=index < 2,
                        status="completed",
                        impact_note=f"Supports {charity.mission_area.lower()} programmes in {charity.location}.",
                    )
                )

            self.db.add(
                GivingPlan(
                    household_id=household.id,
                    name=f"{self.tax_year} Giving Plan",
                    tax_year=self.tax_year,
                    target_amount=grant_target,
                    committed_amount=granted,
                    mission_focus=charity_pool[0].mission_area,
                    strategy="Fund the DAF with appreciated securities, grant quarterly",
                    status="active",
                    review_date=date(self.tax_year, 11, 15),
                    last_updated_at=self.now - timedelta(days=21),
                )
            )

            appreciated = round(grant_target * 0.55, 2)
            self.db.add(
                Gift(
                    household_id=household.id,
                    charity_id=charity_pool[0].id,
                    recipient=charity_pool[0].name,
                    gift_type="securities",
                    amount=appreciated,
                    cost_basis=round(appreciated * 0.42, 2),
                    gifted_on=date(self.tax_year, 6, 3),
                    tax_year=self.tax_year,
                    uses_annual_exclusion=False,
                    deduction_amount=appreciated,
                    capital_gain_avoided=round(appreciated * 0.58, 2),
                    notes="Long-term appreciated shares contributed to the charitable fund",
                )
            )

            if blueprint["key"] == "lindqvist":
                self.db.add(
                    Gift(
                        household_id=household.id,
                        charity_id=charity_pool[1].id,
                        recipient=charity_pool[1].name,
                        gift_type="cash",
                        amount=48_000.0,
                        gifted_on=date(self.tax_year, 8, 22),
                        tax_year=self.tax_year,
                        uses_annual_exclusion=False,
                        is_qcd=True,
                        deduction_amount=0.0,
                        notes="Qualified charitable distribution counting toward the RMD",
                    )
                )

    # ------------------------------------------------------------------
    DOCUMENT_SPECS = [
        ("2025_Tax_Return.pdf", "tax", "Tax Return", 2025, None, "reviewed"),
        ("2025_Form_1099_Consolidated.pdf", "tax", "Form 1099", 2025, None, "reviewed"),
        ("2024_Schedule_K-1.pdf", "tax", "Schedule K-1", 2024, None, "reviewed"),
        ("Revocable_Trust_Agreement.pdf", "estate", "Trust Agreement", None, None, "reviewed"),
        ("Last_Will_and_Testament.pdf", "estate", "Will", None, None, "reviewed"),
        ("Durable_Power_of_Attorney.pdf", "estate", "Power of Attorney", None, None, "reviewed"),
        ("Q2_Brokerage_Statement.pdf", "investment", "Account Statement", None, None, "pending_review"),
        ("Investment_Policy_Statement.pdf", "investment", "Account Statement", None, None, "reviewed"),
        ("Umbrella_Liability_Policy.pdf", "insurance", "Insurance Policy", None, 62, "reviewed"),
        ("Term_Life_Insurance_Policy.pdf", "insurance", "Insurance Policy", None, 340, "reviewed"),
        ("Cascade_Bank_Statement_August.pdf", "banking", "Bank Statement", None, None, "pending_review"),
        ("401k_Annual_Statement.pdf", "retirement", "Retirement Statement", None, None, "reviewed"),
        ("Property_Deed_Coastal.pdf", "legal", "Legal Agreement", None, None, "reviewed"),
        ("Charitable_Fund_Agreement.pdf", "legal", "Legal Agreement", None, None, "pending_review"),
    ]

    def seed_documents(self) -> None:
        from app.ai.mock_ai import MockAIService

        classifier = MockAIService()
        advisor = self.users["marcus.webb@nexgile.example"]

        for blueprint in HOUSEHOLDS:
            household = self.households[blueprint["key"]]
            client_user = next(
                (u for u in self.users.values() if u.role == Role.CLIENT), advisor
            )
            count = len(self.DOCUMENT_SPECS) if blueprint["key"] == "johnson" else 8

            for filename, category, doc_type, year, expires_in, review_status in self.DOCUMENT_SPECS[:count]:
                classification = classifier.classify_document(filename)
                uploaded_at = self.now - timedelta(days=self.rng.randint(5, 400))
                document = Document(
                    household_id=household.id,
                    uploaded_by_id=(client_user if category in {"tax", "banking"} else advisor).id,
                    name=filename,
                    original_filename=filename,
                    category=category,
                    document_type=doc_type,
                    tax_year=year,
                    tags=classification.suggested_tags,
                    description=f"{doc_type} filed for {household.name}.",
                    storage_key=None,
                    storage_backend="local",
                    mime_type="application/pdf",
                    size_bytes=self.rng.randint(180_000, 2_400_000),
                    current_version=1,
                    review_status=review_status,
                    suggested_category=classification.suggested_category,
                    suggested_document_type=classification.suggested_document_type,
                    classification_confidence=classification.confidence,
                    classification_source=classification.source,
                    classification_reasons=classification.reasons,
                    classification_accepted=True if review_status == "reviewed" else None,
                    expires_on=self.today + timedelta(days=expires_in) if expires_in else None,
                    retention_until=self.today + timedelta(days=365 * 7),
                    uploaded_at=uploaded_at,
                )
                self.db.add(document)
                self.db.flush()
                self.db.add(
                    DocumentVersion(
                        document_id=document.id,
                        version=1,
                        size_bytes=document.size_bytes,
                        checksum=f"{self.rng.getrandbits(128):032x}",
                        uploaded_by_id=document.uploaded_by_id,
                        change_note="Initial upload",
                    )
                )

            self.db.add(
                DocumentRequest(
                    household_id=household.id,
                    requested_by_id=advisor.id,
                    title=f"{self.tax_year} property tax assessment",
                    category="tax",
                    reason="Needed to complete the year-end tax projection.",
                    due_date=self.today + timedelta(days=21),
                    status="open",
                )
            )

    # ------------------------------------------------------------------
    def seed_collaboration(self) -> None:
        advisor = self.users["marcus.webb@nexgile.example"]
        tax_lead = self.users["hana.mori@nexgile.example"]

        thread_specs = [
            ("Q3 portfolio review preparation", "review", [
                ("advisor", "Ahead of our review I have refreshed the allocation analysis and the goal projections. Two items are worth your time: the concentrated position and the education funding gap."),
                ("client", "Thanks — the concentration is the one that worries me. What are the options if we trim it?"),
                ("advisor", "We can stage the reduction across two tax years and pair it with harvested losses to keep the tax cost down. I have modelled it and will bring the numbers to the meeting."),
            ]),
            ("Year-end tax planning", "tax", [
                ("tax_specialist", "I have identified harvesting candidates across the taxable accounts. Estimated benefit is meaningful and every candidate clears the wash-sale check."),
                ("client", "Please go ahead and prepare the recommendation for review."),
            ]),
            ("Beneficiary designations", "estate", [
                ("advisor", "One retirement account still has no primary beneficiary on file. We should complete that before year end."),
            ]),
        ]

        for blueprint in HOUSEHOLDS:
            household = self.households[blueprint["key"]]
            client = self.db.execute(
                select(Client).where(Client.household_id == household.id).order_by(Client.created_at)
            ).scalars().first()
            specs = thread_specs if blueprint["key"] == "johnson" else thread_specs[:2]

            for offset, (subject, topic, messages) in enumerate(specs):
                thread = MessageThread(household_id=household.id, subject=subject, topic=topic, status="open")
                self.db.add(thread)
                self.db.flush()

                sent_at = self.now - timedelta(days=14 - offset * 4)
                for index, (role, body) in enumerate(messages):
                    sender = {
                        "advisor": advisor,
                        "tax_specialist": tax_lead,
                        "client": None,
                    }[role]
                    sent_at = sent_at + timedelta(hours=6 * index + 2)
                    self.db.add(
                        Message(
                            thread_id=thread.id,
                            sender_id=sender.id if sender else (client.user_id if client else None),
                            sender_name=sender.full_name if sender else (client.full_name if client else "Client"),
                            sender_role=role if role != "client" else "client",
                            body=body,
                            sent_at=sent_at,
                            read_at=sent_at + timedelta(hours=3) if index < len(messages) - 1 else None,
                        )
                    )
                thread.last_message_at = sent_at

            # Meetings
            upcoming = Meeting(
                household_id=household.id,
                advisor_id=household.primary_advisor_id,
                title=f"Q{((self.today.month - 1) // 3) + 1} Portfolio Review",
                meeting_type="review",
                starts_at=self.now + timedelta(days=self.rng.randint(6, 26), hours=3),
                duration_minutes=60,
                location="Video conference",
                status="scheduled",
                agenda=[
                    "Portfolio performance and allocation",
                    "Goal funding update",
                    "Tax planning for the remainder of the year",
                    "Estate document review",
                ],
                attendees=[household.name, "Marcus Webb", "Hana Mori"],
            )
            self.db.add(upcoming)
            self.db.flush()
            self.db.add(
                ActionItem(
                    meeting_id=upcoming.id,
                    household_id=household.id,
                    title="Confirm education funding contribution increase",
                    owner=household.name,
                    due_date=self.today + timedelta(days=34),
                    status="open",
                )
            )

            past = Meeting(
                household_id=household.id,
                advisor_id=household.primary_advisor_id,
                title="Annual Planning Meeting",
                meeting_type="planning",
                starts_at=self.now - timedelta(days=self.rng.randint(70, 140)),
                duration_minutes=90,
                location="Portland office",
                status="completed",
                agenda=["Net worth review", "Goal reprioritisation", "Estate plan status"],
                notes="Reviewed the full balance sheet and reset goal priorities for the year.",
                summary="Agreed to increase education funding and to revisit the concentrated position in Q3.",
                attendees=[household.name, "Marcus Webb"],
            )
            self.db.add(past)
            self.db.flush()
            for title, status in (
                ("Update estate documents with attorney", "open"),
                ("Increase 529 contributions", "complete"),
            ):
                self.db.add(
                    ActionItem(
                        meeting_id=past.id,
                        household_id=household.id,
                        title=title,
                        owner="Marcus Webb" if "estate" in title.lower() else household.name,
                        due_date=self.today + timedelta(days=self.rng.randint(-20, 45)),
                        status=status,
                    )
                )

            # Tasks
            for title, category, priority, due_offset, status in (
                ("Prepare quarterly review pack", "review", "high", 5, "in_progress"),
                ("Collect signed beneficiary form", "service", "high", -3, "open"),
                ("Confirm 529 contribution increase", "planning", "medium", 12, "open"),
                ("Reconcile external account feed", "operations", "low", 21, "open"),
            ):
                self.db.add(
                    Task(
                        title=f"{title} — {household.name}",
                        description=f"{title} for {household.name}.",
                        assignee_id=household.primary_advisor_id,
                        household_id=household.id,
                        category=category,
                        priority=priority,
                        status=status,
                        due_date=self.today + timedelta(days=due_offset),
                        sla_days=5,
                    )
                )

    # ------------------------------------------------------------------
    def seed_institutional(self) -> None:
        sponsor_user = self.users["diane.ellis@brightpath.example"]
        participant_user = self.users["andre.fitzgerald@brightpath.example"]
        advisor = self.users["marcus.webb@nexgile.example"]

        sponsor = Sponsor(
            name="Brightpath Robotics, Inc.",
            industry="Advanced Manufacturing",
            employee_count=1_284,
            ein_masked="**-***5512",
            location="Beaverton, OR",
            relationship_since=date(2017, 4, 1),
            primary_contact_id=sponsor_user.id,
        )
        self.db.add(sponsor)
        self.db.flush()

        plan = Plan(
            sponsor_id=sponsor.id,
            name="Brightpath Robotics 401(k) Plan",
            plan_number="001",
            plan_type="401k",
            plan_year_end=date(self.tax_year, 12, 31),
            eligible_employees=1_240,
            participating_employees=1_058,
            average_deferral_rate=0.071,
            employer_match_formula="100% of the first 4% of pay",
            vesting_schedule="3-year cliff",
            auto_enrollment=True,
            auto_enrollment_rate=0.06,
            auto_escalation=True,
            auto_escalation_cap=0.15,
            loans_allowed=True,
            hardship_allowed=True,
            recordkeeper="Ironbridge Retirement Services",
            advisor_id=advisor.id,
            status="active",
        )
        self.db.add(plan)
        self.db.flush()

        # Second plan so the sponsor workspace has a plan selector with real data.
        sponsor_two = Sponsor(
            name="Kestrel Health Systems",
            industry="Healthcare",
            employee_count=642,
            ein_masked="**-***8890",
            location="Boise, ID",
            relationship_since=date(2020, 9, 15),
        )
        self.db.add(sponsor_two)
        self.db.flush()
        plan_two = Plan(
            sponsor_id=sponsor_two.id,
            name="Kestrel Health Systems 403(b) Plan",
            plan_number="002",
            plan_type="403b",
            plan_year_end=date(self.tax_year, 12, 31),
            eligible_employees=598,
            participating_employees=441,
            average_deferral_rate=0.058,
            employer_match_formula="50% of the first 6% of pay",
            vesting_schedule="6-year graded",
            auto_enrollment=True,
            auto_enrollment_rate=0.04,
            auto_escalation=False,
            loans_allowed=True,
            hardship_allowed=True,
            recordkeeper="Ironbridge Retirement Services",
            advisor_id=advisor.id,
            status="active",
        )
        self.db.add(plan_two)
        self.db.flush()

        for target_plan, participant_count, linked_user in (
            (plan, 60, participant_user),
            (plan_two, 28, None),
        ):
            self._seed_participants(target_plan, participant_count, linked_user)
            self._seed_plan_investments(target_plan)
            self._seed_plan_fees(target_plan)
            self._seed_plan_compliance(target_plan)

    def _seed_participants(self, plan: Plan, count: int, linked_user: User | None) -> None:
        rng = random.Random(SEED + len(plan.name))
        total_assets = 0.0
        hce_threshold = 160_000.0

        for index in range(count):
            if index == 0 and linked_user:
                full_name = linked_user.full_name
                birth_date = date(1982, 4, 17)
                hire_date = date(2016, 2, 8)
                salary = 214_000.0
                deferral = 0.09
                roth_deferral = 0.03
                balance = 486_400.0
            else:
                full_name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
                birth_date = date(rng.randint(1962, 2000), rng.randint(1, 12), rng.randint(1, 28))
                hire_date = date(rng.randint(2009, 2024), rng.randint(1, 12), rng.randint(1, 28))
                salary = round(rng.uniform(62_000, 285_000), -2)
                deferral = round(rng.choice([0.0, 0.03, 0.04, 0.06, 0.06, 0.08, 0.10, 0.12, 0.15]), 4)
                roth_deferral = round(rng.choice([0.0, 0.0, 0.0, 0.02, 0.03]), 4)
                years = max((self.today - hire_date).days / 365.25, 0.5)
                balance = round(salary * (deferral + roth_deferral + 0.04) * years * rng.uniform(1.05, 1.9), 2)

            years_of_service = (self.today - hire_date).days / 365.25
            if "cliff" in plan.vesting_schedule:
                vested = 1.0 if years_of_service >= 3 else 0.0
            else:
                vested = min(max((int(years_of_service) - 1) * 0.20, 0.0), 1.0)

            employer_balance = round(balance * 0.32, 2)
            participant = Participant(
                plan_id=plan.id,
                user_id=linked_user.id if (index == 0 and linked_user) else None,
                full_name=full_name,
                employee_id_masked=f"EMP-***{rng.randint(100, 999)}",
                birth_date=birth_date,
                hire_date=hire_date,
                annual_salary=salary,
                deferral_rate=deferral,
                roth_deferral_rate=roth_deferral,
                account_balance=balance,
                roth_balance=round(balance * roth_deferral * 4, 2),
                employer_balance=employer_balance,
                vested_percentage=vested,
                is_hce=salary >= hce_threshold,
                is_auto_enrolled=hire_date >= date(2018, 1, 1),
                has_beneficiary=rng.random() > 0.16,
                retirement_age=rng.choice([62, 65, 65, 67, 67, 70]),
                status="active" if rng.random() > 0.06 else "terminated",
                engagement_score=round(rng.uniform(0.2, 0.98), 3),
            )
            self.db.add(participant)
            self.db.flush()
            total_assets += balance

            # Two years of quarterly contribution history.
            for year in (self.tax_year - 1, self.tax_year):
                quarters = 4 if year < self.tax_year else max((self.today.month - 1) // 3 + 1, 1)
                for quarter in range(1, quarters + 1):
                    period_start = date(year, 3 * (quarter - 1) + 1, 1)
                    period_end = date(year, min(3 * quarter, 12), 28)
                    quarterly_pay = salary / 4
                    catchup = (
                        quarterly_pay * 0.02
                        if (self.today.year - birth_date.year) >= 50 and deferral > 0
                        else 0.0
                    )
                    self.db.add(
                        Contribution(
                            participant_id=participant.id,
                            plan_id=plan.id,
                            period_start=period_start,
                            period_end=period_end,
                            employee_pretax=round(quarterly_pay * deferral, 2),
                            employee_roth=round(quarterly_pay * roth_deferral, 2),
                            employee_catchup=round(catchup, 2),
                            employer_match=round(quarterly_pay * min(deferral + roth_deferral, 0.04), 2),
                            employer_profit_sharing=round(quarterly_pay * 0.01, 2),
                            tax_year=year,
                        )
                    )

            if rng.random() < 0.13 and plan.loans_allowed:
                original = round(min(balance * 0.35, 50_000), -2)
                if original >= 2_000:
                    issued = self.today - timedelta(days=rng.randint(120, 900))
                    self.db.add(
                        ParticipantLoan(
                            participant_id=participant.id,
                            original_amount=original,
                            outstanding_balance=round(original * rng.uniform(0.25, 0.85), 2),
                            interest_rate=0.0825,
                            term_months=60,
                            payment_amount=round(original / 60 * 1.12, 2),
                            issued_on=issued,
                            matures_on=issued + timedelta(days=5 * 365),
                            loan_type="hardship" if rng.random() < 0.2 else "general",
                            status="current",
                        )
                    )

        # The participant grid is a representative sample of the full population;
        # plan totals scale from it so both views describe the same plan.
        roster = self.db.execute(select(Participant).where(Participant.plan_id == plan.id)).scalars().all()
        average_balance = total_assets / max(len(roster), 1)
        plan.total_assets = round(average_balance * plan.participating_employees, 2)
        plan.average_deferral_rate = round(
            sum(p.deferral_rate + p.roth_deferral_rate for p in roster) / max(len(roster), 1), 4
        )
        plan.plan_health_score = 0.0

        if linked_user:
            participant = self.db.execute(
                select(Participant).where(Participant.user_id == linked_user.id)
            ).scalars().first()
            content = self.db.execute(select(EducationContent)).scalars().all()
            for index, item in enumerate(content):
                status = "complete" if index < 4 else ("in_progress" if index < 6 else "not_started")
                self.db.add(
                    EducationProgress(
                        participant_id=participant.id,
                        content_id=item.id,
                        status=status,
                        progress_percent=1.0 if status == "complete" else (0.45 if status == "in_progress" else 0.0),
                        score=round(self.rng.uniform(0.72, 1.0), 2) if status == "complete" else None,
                        completed_at=self.now - timedelta(days=self.rng.randint(10, 200))
                        if status == "complete"
                        else None,
                    )
                )

    def _seed_plan_investments(self, plan: Plan) -> None:
        lineup = [
            ("Meridian Target 2045 Fund", "MTFDX", "Target Date 2045", 0.0038, 0.0052, 0.0812, 0.0774, 32, True, 0),
            ("Meridian Target 2035 Fund", "MTHDX", "Target Date 2035", 0.0038, 0.0052, 0.0691, 0.0668, 38, False, 0),
            ("Harborline S&P 500 Index", "HSPIX", "Large Cap Blend", 0.0004, 0.0048, 0.1124, 0.1131, 12, False, 0),
            ("Northmoor Large Growth", "NLGRX", "Large Cap Growth", 0.0074, 0.0061, 0.0918, 0.1246, 78, False, 15),
            ("Cascade Small Cap Value", "CSCVX", "Small Cap Value", 0.0091, 0.0079, 0.0642, 0.0731, 68, False, 25),
            ("Ironbridge International Equity", "IIEQX", "Foreign Large Blend", 0.0058, 0.0064, 0.0587, 0.0602, 54, False, 10),
            ("Harborline Core Bond Index", "HCBIX", "Intermediate Core Bond", 0.0005, 0.0041, 0.0148, 0.0152, 22, False, 0),
            ("Meridian Stable Value", "MSVFX", "Stable Value", 0.0031, 0.0037, 0.0284, 0.0271, 28, False, 5),
        ]
        assets = plan.total_assets or 1.0
        weights = [0.22, 0.16, 0.18, 0.09, 0.05, 0.08, 0.13, 0.09]
        participant_total = plan.participating_employees or 1

        for (name, ticker, category, expense, median, three_year, benchmark, percentile, qdia, revenue), weight in zip(
            lineup, weights
        ):
            self.db.add(
                InvestmentOption(
                    plan_id=plan.id,
                    name=name,
                    ticker=ticker,
                    asset_category=category,
                    expense_ratio=expense,
                    category_median_expense=median,
                    plan_assets=round(assets * weight, 2),
                    participants_invested=int(participant_total * weight * 1.6),
                    three_year_return=three_year,
                    five_year_return=round(three_year * 0.94, 4),
                    benchmark_three_year=benchmark,
                    peer_rank_percentile=percentile,
                    ips_status="pass",
                    is_qdia=qdia,
                    revenue_share_bps=revenue,
                )
            )

        self.db.add(
            FiduciaryReview(
                plan_id=plan.id,
                title=f"Q{max((self.today.month - 1) // 3, 1)} Investment Committee Review",
                review_period=f"Q{max((self.today.month - 1) // 3, 1)} {self.tax_year}",
                held_on=self.today - timedelta(days=38),
                attendees=["Diane Ellis", "Marcus Webb", "Tobias Frank", "Priya Raman"],
                agenda=[
                    "Review of the investment policy statement",
                    "Fund performance against benchmarks and peers",
                    "Watch-list discussion",
                    "Fee benchmarking update",
                    "Participant engagement metrics",
                ],
                minutes=(
                    "The committee reviewed all lineup options against the IPS criteria. Two funds were placed on "
                    "watch for trailing three-year performance below benchmark and above-median expenses. The "
                    "committee agreed to review both again next quarter before considering replacement."
                ),
                decisions=[
                    "Retain the current QDIA.",
                    "Place Northmoor Large Growth and Cascade Small Cap Value on watch.",
                    "Request a recordkeeping fee benchmarking study.",
                ],
                funds_on_watch=2,
                ips_compliant=True,
                status="complete",
            )
        )

    def _seed_plan_fees(self, plan: Plan) -> None:
        assets = plan.total_assets or 1.0
        participants = plan.participating_employees or 1
        specs = [
            ("Ironbridge Retirement Services", "recordkeeping", "participant", 0.0022, 0.0018, 0.0004, 4.2),
            ("Nexgile Advisory", "advisory", "sponsor", 0.0018, 0.0020, 0.0, 4.7),
            ("Whitlock & Reyes LLP", "audit", "sponsor", 0.0004, 0.0004, 0.0, 4.5),
            ("Meridian Trust & Custody", "custody", "participant", 0.0006, 0.0005, 0.0001, 4.4),
        ]
        for vendor, fee_type, payer, bps, benchmark_bps, revenue_share, sla in specs:
            annual = assets * bps
            self.db.add(
                Fee(
                    plan_id=plan.id,
                    vendor=vendor,
                    fee_type=fee_type,
                    payer=payer,
                    annual_amount=round(annual, 2),
                    per_participant_amount=round(annual / participants, 2),
                    basis_points=round(bps * 10_000, 2),
                    benchmark_basis_points=round(benchmark_bps * 10_000, 2),
                    revenue_sharing=round(assets * revenue_share, 2),
                    contract_end=date(self.tax_year + 1, 6, 30),
                    sla_score=sla,
                    notes="Contract renewal window opens six months before the end date.",
                )
            )

    def _seed_plan_compliance(self, plan: Plan) -> None:
        participants = self.db.execute(select(Participant).where(Participant.plan_id == plan.id)).scalars().all()
        hce = [p for p in participants if p.is_hce]
        nhce = [p for p in participants if not p.is_hce]
        hce_avg = round(sum(p.deferral_rate + p.roth_deferral_rate for p in hce) / max(len(hce), 1), 4)
        nhce_avg = round(sum(p.deferral_rate + p.roth_deferral_rate for p in nhce) / max(len(nhce), 1), 4)
        key_balances = sum(p.account_balance for p in hce)
        total_balances = sum(p.account_balance for p in participants) or 1.0

        tests = [
            ("ADP", hce_avg, nhce_avg, round(max(nhce_avg * 1.25, min(nhce_avg * 2, nhce_avg + 0.02)), 4), date(self.tax_year, 3, 15), date(self.tax_year, 2, 27)),
            ("ACP", round(hce_avg * 0.82, 4), round(nhce_avg * 0.86, 4), round(nhce_avg * 1.25, 4), date(self.tax_year, 3, 15), date(self.tax_year, 2, 27)),
            ("Top Heavy", round(key_balances, 2), round(total_balances, 2), 0.60, date(self.tax_year, 12, 31), None),
            ("402(g) Limit", None, None, 24_500.0, date(self.tax_year, 4, 15), date(self.tax_year, 3, 30)),
            ("415(c) Annual Additions", None, None, 71_000.0, date(self.tax_year, 12, 31), None),
            ("Coverage 410(b)", round(len(participants) / max(plan.eligible_employees, 1), 4), 0.70, 0.70, date(self.tax_year, 12, 31), None),
        ]

        for test_type, hce_value, nhce_value, threshold, due, completed in tests:
            passed = True
            if test_type == "ADP":
                passed = hce_avg <= max(nhce_avg * 1.25, min(nhce_avg * 2, nhce_avg + 0.02)) + 1e-9
            elif test_type == "Top Heavy":
                passed = (key_balances / total_balances) <= 0.60
            self.db.add(
                ComplianceTest(
                    plan_id=plan.id,
                    test_type=test_type,
                    tax_year=self.tax_year - 1 if completed else self.tax_year,
                    hce_value=hce_value,
                    nhce_value=nhce_value,
                    threshold=threshold,
                    result="pass" if passed else "fail",
                    status=str(ComplianceStatus.COMPLETE if completed else ComplianceStatus.PENDING),
                    due_date=due,
                    completed_on=completed,
                    corrective_action=None
                    if passed
                    else "Refund excess contributions to HCEs within 2.5 months of plan year end.",
                    method="current_year_testing",
                )
            )

        for filing_type, year, due, filed, preparer in (
            ("form_5500", self.tax_year - 1, date(self.tax_year, 7, 31), date(self.tax_year, 7, 12), "Whitlock & Reyes LLP"),
            ("form_5500", self.tax_year, date(self.tax_year + 1, 7, 31), None, "Whitlock & Reyes LLP"),
            ("form_8955_ssa", self.tax_year - 1, date(self.tax_year, 7, 31), date(self.tax_year, 7, 12), "Ironbridge"),
            ("summary_annual_report", self.tax_year - 1, date(self.tax_year, 9, 30), None, "Ironbridge"),
        ):
            self.db.add(
                Filing(
                    plan_id=plan.id,
                    filing_type=filing_type,
                    tax_year=year,
                    due_date=due,
                    extended_due_date=due + timedelta(days=75) if filing_type == "form_5500" else None,
                    filed_on=filed,
                    status=str(ComplianceStatus.COMPLETE if filed else ComplianceStatus.PENDING),
                    preparer=preparer,
                    auditor="Whitlock & Reyes LLP" if filing_type == "form_5500" else None,
                    notes="Independent audit required: plan has more than 100 eligible participants."
                    if filing_type == "form_5500"
                    else None,
                )
            )

    # ------------------------------------------------------------------
    def seed_workflow(self) -> None:
        """Recommendations, approvals and a rebalance in each workflow state."""
        advisor = self.users["marcus.webb@nexgile.example"]
        tax_lead = self.users["hana.mori@nexgile.example"]
        # Investment recommendations are decided by the investment team; the
        # approval engine enforces the same separation of duties.
        reviewer = self.users["tobias.frank@nexgile.example"]

        for blueprint in HOUSEHOLDS:
            household = self.households[blueprint["key"]]
            portfolio = self.portfolios[blueprint["key"]]
            client = self.db.execute(
                select(Client).where(Client.household_id == household.id).order_by(Client.created_at)
            ).scalars().first()
            accounts = self.db.execute(
                select(Account).where(Account.household_id == household.id, Account.is_liability.is_(False))
            ).scalars().all()
            invested = sum(a.balance for a in accounts)

            specs = [
                {
                    "title": "Reduce the concentrated equity position toward policy",
                    "category": "portfolio",
                    "severity": "high",
                    "summary": "Trim the largest single holding back to the 10% policy guideline over two tax years.",
                    "rationale": "The position is the largest single source of portfolio risk and exceeds the investment policy limit.",
                    "action": "Stage the reduction, pairing sales with harvested losses to limit the tax cost.",
                    "impact": round(invested * 0.021, 2),
                    "impact_label": "Estimated proceeds to reallocate",
                    "status": ApprovalStatus.SUBMITTED,
                    "requested_by": advisor,
                },
                {
                    "title": "Harvest available losses before year end",
                    "category": "tax",
                    "severity": "medium",
                    "summary": "Realise losses across the taxable accounts to offset gains of the same character.",
                    "rationale": "Harvested losses offset realised gains and up to $3,000 of ordinary income, with the excess carried forward.",
                    "action": "Approve the harvest set and hold replacements through the 31-day window.",
                    "impact": round(invested * 0.0042, 2),
                    "impact_label": "Estimated tax reduction",
                    "status": ApprovalStatus.APPROVED,
                    "requested_by": tax_lead,
                },
                {
                    "title": "Increase education funding contributions",
                    "category": "goal",
                    "severity": "medium",
                    "summary": "Raise the monthly contribution to close the projected education funding shortfall.",
                    "rationale": "The goal is projected to fall short of its inflation-adjusted target on current assumptions.",
                    "action": "Compare the higher-savings scenario and adjust the funding plan.",
                    "impact": 1_450.0,
                    "impact_label": "Additional monthly contribution",
                    "status": ApprovalStatus.DRAFT,
                    "requested_by": advisor,
                },
                {
                    "title": "Complete outstanding beneficiary designations",
                    "category": "estate",
                    "severity": "high",
                    "summary": "One retirement account has no valid primary beneficiary on file.",
                    "rationale": "Without a designation the account passes through probate rather than to the intended person.",
                    "action": "Collect and file the designation form; route the change through review.",
                    "impact": None,
                    "impact_label": None,
                    "status": ApprovalStatus.COMPLETED,
                    "requested_by": advisor,
                },
            ]
            if blueprint["key"] != "johnson":
                specs = specs[:2]

            for spec in specs:
                recommendation = Recommendation(
                    household_id=household.id,
                    client_id=client.id if client else None,
                    title=spec["title"],
                    category=spec["category"],
                    severity=spec["severity"],
                    summary=spec["summary"],
                    rationale=spec["rationale"],
                    suggested_action=spec["action"],
                    impact_amount=spec["impact"],
                    impact_label=spec["impact_label"],
                    confidence=0.88,
                    status=str(spec["status"]),
                    source="wealthagent_rules",
                    generator="mock",
                    supporting_data={"household": household.name},
                    assumptions=["Figures derive from the platform's calculation engine as of the stated date."],
                    limitations=["Requires human review; this platform never executes trades."],
                    entity_type=spec["category"],
                    as_of=self.now,
                    created_by_id=spec["requested_by"].id,
                )
                self.db.add(recommendation)
                self.db.flush()

                approval = Approval(
                    household_id=household.id,
                    entity_type="recommendation",
                    entity_id=recommendation.id,
                    title=spec["title"],
                    summary=spec["summary"],
                    status=str(spec["status"]),
                    priority="high" if spec["severity"] == "high" else "medium",
                    requested_by_id=spec["requested_by"].id,
                    assigned_to_id=advisor.id,
                    required_role=str(Role.ADVISOR),
                    estimated_impact=spec["impact"],
                    payload={"recommendation_id": recommendation.id, "category": spec["category"]},
                    due_date=self.today + timedelta(days=14),
                )
                if spec["status"] != ApprovalStatus.DRAFT:
                    approval.submitted_at = self.now - timedelta(days=6)
                if spec["status"] in {ApprovalStatus.APPROVED, ApprovalStatus.COMPLETED}:
                    approval.decided_at = self.now - timedelta(days=3)
                    approval.decided_by_id = reviewer.id
                    approval.decision_note = "Reviewed against the investment policy and client objectives."
                if spec["status"] == ApprovalStatus.COMPLETED:
                    approval.completed_at = self.now - timedelta(days=1)
                self.db.add(approval)
                self.db.flush()
                recommendation.approval_id = approval.id

                history = {
                    ApprovalStatus.DRAFT: [(None, "draft")],
                    ApprovalStatus.SUBMITTED: [(None, "draft"), ("draft", "submitted")],
                    ApprovalStatus.APPROVED: [(None, "draft"), ("draft", "submitted"), ("submitted", "under_review"), ("under_review", "approved")],
                    ApprovalStatus.COMPLETED: [
                        (None, "draft"), ("draft", "submitted"), ("submitted", "under_review"),
                        ("under_review", "approved"), ("approved", "completed"),
                    ],
                }[spec["status"]]
                for offset, (from_status, to_status) in enumerate(history):
                    actor = spec["requested_by"] if to_status in {"draft", "submitted"} else reviewer
                    self.db.add(
                        ApprovalEvent(
                            approval_id=approval.id,
                            from_status=from_status,
                            to_status=to_status,
                            actor_id=actor.id,
                            actor_name=actor.full_name,
                            note={
                                "draft": "Request created",
                                "submitted": "Submitted for review",
                                "under_review": "Review started",
                                "approved": "Approved after policy review",
                                "completed": "Action carried out and recorded",
                            }[to_status],
                        )
                    )

            # A rebalance proposal awaiting review on the first two households.
            if blueprint["key"] in {"johnson", "okonkwo"}:
                rebalance = Rebalance(
                    household_id=household.id,
                    portfolio_id=portfolio.id,
                    name=f"Rebalance to policy — {self.today.isoformat()}",
                    strategy_note="Return each asset class to its strategic target within tolerance.",
                    status=str(RebalanceStatus.PENDING_REVIEW),
                    max_drift=0.0,
                    turnover_amount=0.0,
                    estimated_tax_cost=0.0,
                    estimated_trading_cost=0.0,
                    cash_impact=0.0,
                    created_by_id=advisor.id,
                    as_of=self.now,
                    is_simulated=True,
                )
                self.db.add(rebalance)
                self.db.flush()
                self._populate_rebalance(rebalance, household, client)

                approval = Approval(
                    household_id=household.id,
                    entity_type="rebalance",
                    entity_id=rebalance.id,
                    title=rebalance.name,
                    summary=f"{len(rebalance.trades)} proposed trades to return the portfolio to policy.",
                    status=str(ApprovalStatus.SUBMITTED),
                    priority="medium",
                    requested_by_id=advisor.id,
                    assigned_to_id=self.users["tobias.frank@nexgile.example"].id,
                    required_role=str(Role.INVESTMENT_TEAM),
                    estimated_impact=rebalance.estimated_tax_cost,
                    payload={"rebalance_id": rebalance.id},
                    submitted_at=self.now - timedelta(days=2),
                    due_date=self.today + timedelta(days=7),
                )
                self.db.add(approval)
                self.db.flush()
                rebalance.approval_id = approval.id
                for from_status, to_status in ((None, "draft"), ("draft", "submitted")):
                    self.db.add(
                        ApprovalEvent(
                            approval_id=approval.id,
                            from_status=from_status,
                            to_status=to_status,
                            actor_id=advisor.id,
                            actor_name=advisor.full_name,
                            note="Proposal generated from current drift" if to_status == "draft" else "Submitted to the investment team",
                        )
                    )

            # Reports
            for report_type, title in (("quarterly_review", "Quarterly Review"), ("performance", "Performance Report")):
                self.db.add(
                    Report(
                        household_id=household.id,
                        report_type=report_type,
                        title=f"{title} — {household.name}",
                        period_start=date(self.today.year, max(self.today.month - 3, 1), 1),
                        period_end=self.today,
                        benchmark_code=blueprint["benchmark"],
                        status="ready",
                        generated_by_id=advisor.id,
                        generated_at=self.now - timedelta(days=self.rng.randint(3, 40)),
                        sections=["Summary", "Performance", "Allocation", "Goals", "Assumptions"],
                        payload={"note": "Regenerate from the Reports page for the latest figures."},
                        assumptions=["Performance is time-weighted and net of investment-management fees."],
                    )
                )

    def _populate_rebalance(self, rebalance: Rebalance, household: Household, client: Client | None) -> None:
        from app.calculations.advisory import build_rebalance_plan
        from app.services.portfolio_service import PortfolioService

        service = PortfolioService(self.db)
        positions = service.positions(household.id)
        targets = service.allocation_targets(household.id)
        plan = build_rebalance_plan(
            positions,
            targets,
            self.today,
            cash=service.cash_balance(household.id),
            marginal_rate=client.marginal_tax_rate if client else 0.35,
            ltcg_rate=client.ltcg_tax_rate if client else 0.20,
        )
        rebalance.max_drift = plan.result["max_drift"]
        rebalance.turnover_amount = plan.result["turnover_amount"]
        rebalance.estimated_tax_cost = plan.result["estimated_tax_cost"]
        rebalance.estimated_trading_cost = plan.result["estimated_trading_cost"]
        rebalance.cash_impact = plan.result["cash_impact"]

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
                    status="proposed",
                )
            )
        self.db.flush()

    # ------------------------------------------------------------------
    def seed_notifications_and_audit(self) -> None:
        advisor = self.users["marcus.webb@nexgile.example"]
        compliance = self.users["priya.raman@nexgile.example"]
        client_users = [u for u in self.users.values() if u.role == Role.CLIENT]
        client_user = client_users[0] if client_users else None

        alert_specs = [
            ("portfolio", "high", "Concentration above policy limit", "A single holding exceeds the 10% single-position guideline.", "/portfolio"),
            ("tax", "medium", "Harvesting candidates identified", "Loss positions are available to offset this year's realised gains.", "/tax"),
            ("goal", "medium", "Education goal is off track", "The projected balance falls short of the inflation-adjusted target.", "/goals"),
            ("estate", "high", "Beneficiary designation missing", "One retirement account has no primary beneficiary on file.", "/estate"),
            ("document", "low", "Document expiring in 62 days", "The umbrella liability policy is approaching its expiration date.", "/documents"),
            ("meeting", "info", "Quarterly review scheduled", "Your next portfolio review is on the calendar.", "/meetings"),
            ("approval", "medium", "Approval awaiting your review", "A recommendation has been submitted for review.", "/approvals"),
        ]

        for blueprint in HOUSEHOLDS:
            household = self.households[blueprint["key"]]
            recipients = [advisor] + ([client_user] if blueprint["key"] == "johnson" and client_user else [])
            for index, (category, severity, title, body, url) in enumerate(alert_specs):
                if blueprint["key"] != "johnson" and index > 3:
                    continue
                for recipient in recipients:
                    self.db.add(
                        Alert(
                            user_id=recipient.id,
                            household_id=household.id,
                            category=category,
                            severity=severity,
                            title=title,
                            body=body,
                            action_url=url,
                            due_date=self.today + timedelta(days=self.rng.randint(3, 60)) if category in {"tax", "document"} else None,
                            read_at=self.now - timedelta(hours=5) if index > 4 else None,
                        )
                    )

        # Plan-level notifications for the sponsor and compliance workspaces.
        sponsor_user = self.users["diane.ellis@brightpath.example"]
        plan = self.db.execute(select(Plan).order_by(Plan.name)).scalars().first()
        for category, severity, title, body, url in (
            ("compliance", "high", "Form 5500 filing due", "The current plan-year filing has not yet been submitted.", "/compliance"),
            ("plan", "medium", "Two funds on the watch list", "The investment committee placed two options on watch.", "/institutional/investments"),
            ("plan", "info", "Participation rate improved", "Participation increased following the auto-enrolment sweep.", "/institutional"),
        ):
            for recipient in (sponsor_user, compliance):
                self.db.add(
                    Alert(
                        user_id=recipient.id,
                        plan_id=plan.id if plan else None,
                        category=category,
                        severity=severity,
                        title=title,
                        body=body,
                        action_url=url,
                    )
                )

        # Audit history so the trail is populated from the first page load.
        audit_specs = [
            ("login", "session", "Signed in", advisor, "success"),
            ("document_upload", "document", "2025_Tax_Return.pdf", advisor, "success"),
            ("recommendation_created", "recommendation", "Reduce the concentrated equity position toward policy", advisor, "success"),
            ("approval_submitted", "approval", "Reduce the concentrated equity position toward policy", advisor, "success"),
            ("approval_reviewed", "approval", "Harvest available losses before year end", compliance, "success"),
            ("approval_decided", "approval", "Harvest available losses before year end", compliance, "success"),
            ("rebalance_created", "rebalance", "Rebalance to policy", advisor, "success"),
            ("beneficiary_change", "beneficiary", "Beneficiary designation updated", advisor, "success"),
            ("scenario_run", "goal", "Retirement at 65", advisor, "success"),
            ("report_generated", "report", "Quarterly Review", advisor, "success"),
            ("compliance_action", "compliance_test", "ADP test 2025", compliance, "success"),
            ("login_failed", "session", "unknown@example.com", None, "failed"),
        ]
        for house_index, blueprint in enumerate(HOUSEHOLDS):
            household = self.households[blueprint["key"]]
            for index, (action, entity_type, label, actor, status) in enumerate(audit_specs):
                self.db.add(
                    AuditEvent(
                        actor_id=actor.id if actor else None,
                        actor_name=actor.full_name if actor else "Unknown",
                        actor_role=actor.role if actor else None,
                        household_id=household.id if entity_type != "compliance_test" else None,
                        action=action,
                        entity_type=entity_type,
                        entity_label=label,
                        status=status,
                        summary=f"{action.replace('_', ' ').capitalize()} — {label}",
                        ip_address="198.51.100." + str(20 + index),
                        created_at=self.now - timedelta(days=index + house_index, hours=index * 2),
                    )
                )

        if client_user:
            self.db.add(SavedView(user_id=client_user.id, name="Tax documents", query="tax", categories=["documents"], is_pinned=True))
        self.db.add(SavedView(user_id=advisor.id, name="Pending approvals", query="approval", categories=["approvals"], is_pinned=True))
        self.db.add(SavedView(user_id=advisor.id, name="Off-track goals", query="education", categories=["goals"]))

    # ------------------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        counts = {}
        for model in (
            User, Household, Client, Account, Security, Holding, TaxLot, Transaction, Portfolio,
            PerformancePoint, Goal, Scenario, TaxOpportunity, Harvest, EstatePlan, Trust, Beneficiary,
            DAF, Grant, Gift, Document, MessageThread, Message, Meeting, Task, Plan, Participant,
            Contribution, InvestmentOption, ComplianceTest, Filing, Fee, Recommendation, Approval,
            Rebalance, RebalanceTrade, Report, Alert, AuditEvent,
        ):
            counts[model.__tablename__] = len(self.db.execute(select(model)).scalars().all())

        demo_users = self.db.execute(select(User).where(User.is_demo.is_(True))).scalars().all()
        return {
            "counts": counts,
            "total_rows": sum(counts.values()),
            "demo_accounts": [
                {"label": u.demo_label, "email": u.email, "role": u.role} for u in demo_users
            ],
            "password": settings.demo_password,
        }
