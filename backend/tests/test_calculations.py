"""The calculation engine is the financial source of truth, so it is tested
directly and independently of the API."""

from __future__ import annotations

from datetime import date

import pytest

from app.calculations import advisory, goals, institutional, portfolio, retirement, tax

AS_OF = date(2026, 9, 4)

POSITIONS = [
    {
        "symbol": "VTI", "name": "US Total Market", "security_type": "etf", "quantity": 1000,
        "price": 300.0, "previous_close": 297.0, "average_cost": 200.0, "asset_class": "us_equity",
        "sector": "Diversified", "region": "United States", "beta": 1.0, "volatility": 0.16,
        "dividend_yield": 0.013, "esg_score": 62,
    },
    {
        "symbol": "ACME", "name": "Acme Corp", "security_type": "stock", "quantity": 500,
        "price": 200.0, "previous_close": 196.0, "average_cost": 50.0, "asset_class": "us_equity",
        "sector": "Technology", "region": "United States", "beta": 1.8, "volatility": 0.40,
        "dividend_yield": 0.0, "esg_score": 44,
    },
    {
        "symbol": "BND", "name": "Total Bond", "security_type": "etf", "quantity": 2000,
        "price": 75.0, "previous_close": 75.2, "average_cost": 80.0, "asset_class": "fixed_income",
        "sector": "Aggregate", "region": "United States", "beta": 0.14, "volatility": 0.058,
        "dividend_yield": 0.043, "esg_score": 60,
    },
]


class TestPortfolioValuation:
    def test_market_value_is_quantity_times_price_plus_cash(self):
        result = portfolio.value_portfolio(POSITIONS, AS_OF, cash=50_000).result
        assert result["market_value"] == pytest.approx(300_000 + 100_000 + 150_000 + 50_000)

    def test_unrealised_gain_is_market_value_less_cost(self):
        result = portfolio.value_portfolio(POSITIONS, AS_OF, cash=50_000).result
        # Cost: 200k + 25k + 160k, plus cash at par.
        assert result["cost_basis"] == pytest.approx(200_000 + 25_000 + 160_000 + 50_000)
        assert result["unrealized_gain"] == pytest.approx(165_000)

    def test_day_change_uses_previous_close(self):
        result = portfolio.value_portfolio(POSITIONS, AS_OF).result
        assert result["day_change"] == pytest.approx(1000 * 3 + 500 * 4 + 2000 * -0.2)

    def test_empty_portfolio_does_not_divide_by_zero(self):
        result = portfolio.value_portfolio([], AS_OF).result
        assert result["market_value"] == 0
        assert result["unrealized_gain_percent"] == 0

    def test_every_calculation_publishes_its_disclosure(self):
        calculation = portfolio.value_portfolio(POSITIONS, AS_OF).to_dict()
        for field in ("method", "result", "as_of", "inputs", "assumptions", "limitations", "source"):
            assert field in calculation, f"missing disclosure field: {field}"
        assert calculation["assumptions"] and calculation["limitations"]


class TestAllocationAndDrift:
    def test_weights_sum_to_one(self):
        rows = portfolio.allocation_breakdown(POSITIONS, "asset_class", AS_OF, cash=50_000).result["rows"]
        assert sum(r["weight"] for r in rows) == pytest.approx(1.0, abs=1e-4)

    def test_drift_flags_only_breaches_outside_the_band(self):
        current = [
            {"key": "us_equity", "weight": 0.72, "market_value": 400_000},
            {"key": "fixed_income", "weight": 0.28, "market_value": 150_000},
        ]
        targets = [
            {"asset_class": "us_equity", "target_weight": 0.60, "tolerance_band": 0.05},
            {"asset_class": "fixed_income", "target_weight": 0.30, "tolerance_band": 0.05},
        ]
        result = portfolio.drift_vs_target(current, targets, AS_OF).result
        breached = {r["asset_class"]: r["breached"] for r in result["rows"]}
        assert breached["us_equity"] is True
        assert breached["fixed_income"] is False
        assert result["breach_count"] == 1


class TestConcentration:
    def test_single_name_is_measured_separately_from_funds(self):
        result = portfolio.concentration(POSITIONS, AS_OF, threshold=0.10).result
        assert result["top_position"]["symbol"] == "VTI"
        assert result["top_single_name"]["symbol"] == "ACME"

    def test_a_diversified_fund_is_never_flagged_as_concentration(self):
        result = portfolio.concentration(POSITIONS, AS_OF, threshold=0.10).result
        assert [r["symbol"] for r in result["flagged"]] == ["ACME"]

    def test_hhi_rises_as_the_portfolio_concentrates(self):
        diversified = portfolio.concentration(POSITIONS, AS_OF).result["hhi"]
        single = portfolio.concentration([POSITIONS[1]], AS_OF).result["hhi"]
        assert single > diversified
        assert single == pytest.approx(1.0)


class TestPerformance:
    def _series(self, days: int, daily: float, bench: float):
        return [
            {
                "as_of": date.fromordinal(date(2025, 9, 4).toordinal() + i),
                "market_value": 1_000_000 * (1 + daily) ** i,
                "daily_return": daily if i else 0.0,
                "benchmark_return": bench if i else 0.0,
            }
            for i in range(days)
        ]

    def test_returns_chain_geometrically(self):
        series = self._series(11, 0.01, 0.005)
        result = portfolio.time_weighted_return(series, date(2025, 9, 14), "1M").result
        # Returns are published rounded to four decimals.
        assert result["return"] == pytest.approx(1.01**10 - 1, abs=1e-4)

    def test_excess_return_is_portfolio_minus_benchmark(self):
        series = self._series(11, 0.01, 0.005)
        result = portfolio.time_weighted_return(series, date(2025, 9, 14), "1M").result
        assert result["excess_return"] == pytest.approx(result["return"] - result["benchmark_return"])

    def test_no_history_is_reported_as_a_limitation_not_a_crash(self):
        result = portfolio.time_weighted_return([], AS_OF, "YTD")
        assert result.result["return"] == 0.0
        assert result.limitations


class TestNetWorth:
    def test_liabilities_are_subtracted(self):
        accounts = [
            {"balance": 1_000_000, "is_liability": False, "account_type": "brokerage"},
            {"balance": 250_000, "is_liability": False, "account_type": "banking"},
            {"balance": 400_000, "is_liability": True, "account_type": "mortgage"},
        ]
        result = portfolio.net_worth(accounts, AS_OF).result
        assert result["total_assets"] == 1_250_000
        assert result["total_liabilities"] == 400_000
        assert result["net_worth"] == 850_000


class TestGoals:
    BASE = {
        "name": "Retirement",
        "current_amount": 1_000_000.0,
        "target_amount": 2_000_000.0,
        "monthly_contribution": 5_000.0,
        "expected_return": 0.06,
        "inflation_rate": 0.0,
        "target_date": date(2036, 9, 4),
    }

    def test_future_value_matches_the_annuity_formula(self):
        # 100k at 6% for 10 years with no contributions.
        assert goals.future_value(100_000, 0, 0.06, 120) == pytest.approx(100_000 * (1.005**120), rel=1e-9)

    def test_zero_rate_is_handled_without_dividing_by_zero(self):
        assert goals.future_value(1_000, 100, 0.0, 12) == pytest.approx(1_000 + 1_200)

    def test_projection_reports_a_funded_ratio_and_status(self):
        result = goals.project_goal(self.BASE, AS_OF).result
        assert result["projected_value"] > self.BASE["current_amount"]
        assert 0 < result["funded_ratio"]
        assert result["status"] in {"on_track", "monitor", "at_risk", "off_track"}

    def test_inflation_raises_the_target(self):
        without = goals.project_goal(self.BASE, AS_OF).result["inflation_adjusted_target"]
        with_inflation = goals.project_goal({**self.BASE, "inflation_rate": 0.03}, AS_OF).result[
            "inflation_adjusted_target"
        ]
        assert with_inflation > without

    def test_required_contribution_closes_the_gap(self):
        underfunded = {**self.BASE, "current_amount": 100_000.0, "monthly_contribution": 0.0}
        result = goals.project_goal(underfunded, AS_OF).result
        required = result["required_monthly_contribution"]
        closed = goals.project_goal({**underfunded, "monthly_contribution": required}, AS_OF).result
        assert closed["funded_ratio"] == pytest.approx(1.0, abs=0.01)

    def test_scenarios_move_the_outcome_in_the_expected_direction(self):
        result = goals.compare_scenarios(self.BASE, AS_OF).result
        by_key = {row["key"]: row for row in result["scenarios"]}
        base = by_key["base_case"]["projected_value"]
        assert by_key["higher_savings"]["projected_value"] > base
        assert by_key["lower_return"]["projected_value"] < base
        assert by_key["earlier_retirement"]["projected_value"] < base

    def test_scenarios_never_mutate_the_input_goal(self):
        original = dict(self.BASE)
        goals.compare_scenarios(self.BASE, AS_OF)
        assert self.BASE == original


class TestTax:
    def test_short_and_long_term_gains_are_taxed_at_different_rates(self):
        result = tax.estimate_tax_on_gains(100_000, 100_000, 0.35, 0.20, 0.05, AS_OF).result
        assert result["federal_tax"] == pytest.approx(100_000 * 0.35 + 100_000 * 0.20)
        assert result["state_tax"] == pytest.approx(200_000 * 0.05)

    def test_net_loss_offsets_ordinary_income_and_carries_forward(self):
        result = tax.estimate_tax_on_gains(-10_000, 0, 0.35, 0.20, 0.05, AS_OF).result
        assert result["ordinary_income_offset"] == 3_000
        assert result["loss_carryforward"] == 7_000
        assert result["federal_tax"] < 0  # a benefit, not a liability

    def test_holding_period_boundary_is_366_days(self):
        assert tax.holding_period(date(2025, 9, 4), date(2026, 9, 3)) == "short_term"
        assert tax.holding_period(date(2025, 9, 4), date(2026, 9, 5)) == "long_term"

    def test_wash_sale_blocks_a_repurchase_inside_the_window(self):
        blocked = tax.wash_sale_check(
            "EFA", date(2026, 6, 1), [{"symbol": "EFA", "trade_date": date(2026, 5, 20), "quantity": 100}]
        ).result
        assert blocked["is_blocked"] is True
        assert blocked["risk"] == "blocked"

    def test_wash_sale_clears_outside_the_window(self):
        clear = tax.wash_sale_check(
            "EFA", date(2026, 6, 1), [{"symbol": "EFA", "trade_date": date(2026, 4, 1), "quantity": 100}]
        ).result
        assert clear["is_blocked"] is False

    def test_wash_sale_catches_a_substantially_identical_security(self):
        result = tax.wash_sale_check(
            "VTI",
            date(2026, 6, 1),
            [{"symbol": "ITOT", "trade_date": date(2026, 6, 10), "quantity": 100}],
            substantially_identical=["ITOT"],
        ).result
        assert result["is_blocked"] is True

    def test_harvesting_only_surfaces_losses_above_the_threshold(self):
        lots = [
            {"id": "1", "symbol": "EFA", "quantity": 1000, "cost_per_share": 100.0, "price": 84.0,
             "acquired_on": date(2023, 1, 10)},
            {"id": "2", "symbol": "VTI", "quantity": 10, "cost_per_share": 300.0, "price": 299.0,
             "acquired_on": date(2023, 1, 10)},
        ]
        result = tax.harvest_opportunities(lots, 0.35, 0.20, 0.05, AS_OF, minimum_loss=1_000).result
        assert [row["symbol"] for row in result["opportunities"]] == ["EFA"]
        assert result["total_estimated_benefit"] == pytest.approx(16_000 * 0.25)

    def test_rmd_uses_the_uniform_lifetime_table(self):
        result = tax.rmd_amount(75, 1_000_000, 2026, AS_OF).result
        assert result["required_amount"] == pytest.approx(1_000_000 / 24.6, rel=1e-6)
        assert result["is_required"] is True

    def test_no_rmd_before_the_start_age(self):
        assert tax.rmd_amount(68, 1_000_000, 2026, AS_OF).result["is_required"] is False


class TestRetirement:
    KWARGS = dict(
        current_age=45, retirement_age=65, current_savings=500_000, annual_contribution=30_000,
        employer_match=10_000, expected_return=0.06, current_income=200_000,
        social_security_annual=36_000, other_income_annual=0, healthcare_annual=12_000,
        inflation=0.025, as_of=AS_OF,
    )

    def test_projection_reports_a_replacement_ratio_and_status(self):
        result = retirement.retirement_projection(**self.KWARGS).result
        assert result["projected_balance"] > 500_000
        assert result["status"] in {"on_track", "monitor", "at_risk"}
        assert result["years_to_retirement"] == 20

    def test_saving_more_improves_the_outcome(self):
        base = retirement.retirement_projection(**self.KWARGS).result
        more = retirement.retirement_projection(**{**self.KWARGS, "annual_contribution": 60_000}).result
        assert more["projected_balance"] > base["projected_balance"]
        assert more["income_gap"] > base["income_gap"]

    def test_monte_carlo_is_reproducible_for_the_same_seed(self):
        kwargs = dict(starting_balance=500_000, annual_contribution=40_000, years=20,
                      expected_return=0.06, volatility=0.14, as_of=AS_OF, trials=200)
        first = retirement.monte_carlo_projection(**kwargs).result
        second = retirement.monte_carlo_projection(**kwargs).result
        assert first["percentiles"] == second["percentiles"]

    def test_monte_carlo_percentiles_are_ordered(self):
        result = retirement.monte_carlo_projection(
            starting_balance=500_000, annual_contribution=40_000, years=20,
            expected_return=0.06, volatility=0.14, as_of=AS_OF, trials=300,
        ).result
        p = result["percentiles"]
        assert p["p10"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p90"]

    def test_success_is_measured_against_the_required_balance_when_given(self):
        result = retirement.monte_carlo_projection(
            starting_balance=100_000, annual_contribution=1_000, years=10,
            expected_return=0.06, volatility=0.14, as_of=AS_OF, trials=200,
            success_threshold=50_000_000,
        ).result
        assert result["success_rate"] == 0.0
        assert "50,000,000" in result["success_basis"]

    def test_catch_up_capacity_opens_at_fifty(self):
        under = retirement.contribution_capacity(age=45, salary=200_000, deferral_rate=0.1,
                                                 ytd_deferral=0, as_of=AS_OF).result
        over = retirement.contribution_capacity(age=52, salary=200_000, deferral_rate=0.1,
                                                ytd_deferral=0, as_of=AS_OF).result
        assert under["catchup_eligible"] is False
        assert over["catchup_eligible"] is True
        assert over["annual_limit"] > under["annual_limit"]

    def test_cliff_vesting_is_all_or_nothing(self):
        before = retirement.vesting_status(hire_date=date(2024, 6, 1), schedule="3-year cliff", as_of=AS_OF).result
        after = retirement.vesting_status(hire_date=date(2020, 6, 1), schedule="3-year cliff", as_of=AS_OF).result
        assert before["vested_percentage"] == 0.0
        assert after["vested_percentage"] == 1.0


class TestAdvisory:
    WEIGHTS = {"us_equity": 0.45, "intl_equity": 0.20, "fixed_income": 0.25, "cash": 0.10}

    def test_expected_risk_falls_as_equity_falls(self):
        _, high = advisory.portfolio_expected_risk({"us_equity": 1.0})
        _, low = advisory.portfolio_expected_risk({"fixed_income": 1.0})
        assert high > low

    def test_stress_scenarios_produce_losses_for_an_equity_portfolio(self):
        result = advisory.stress_test(self.WEIGHTS, 10_000_000, AS_OF).result
        assert result["worst_case"]["portfolio_impact_percent"] < 0
        assert result["worst_case"]["resulting_value"] < 10_000_000

    def test_frontier_is_monotonic_in_risk(self):
        frontier = advisory.efficient_frontier(self.WEIGHTS, AS_OF).result["frontier"]
        volatilities = [point["volatility"] for point in frontier]
        assert volatilities == sorted(volatilities)

    def test_liquidity_buckets_sum_to_the_portfolio(self):
        result = advisory.liquidity_profile(POSITIONS, AS_OF, cash=50_000).result
        assert result["liquid_percent"] + result["illiquid_percent"] == pytest.approx(1.0, abs=1e-3)

    def test_rebalance_moves_holdings_toward_target(self):
        positions = [
            {**p, "account_id": "a1", "account_name": "Brokerage", "security_id": p["symbol"],
             "expense_ratio": 0.0003, "is_long_term": True}
            for p in POSITIONS
        ]
        targets = [
            {"asset_class": "us_equity", "target_weight": 0.40},
            {"asset_class": "fixed_income", "target_weight": 0.50},
            {"asset_class": "cash", "target_weight": 0.10},
        ]
        result = advisory.build_rebalance_plan(positions, targets, AS_OF, cash=50_000).result
        assert result["trade_count"] > 0
        assert all(t["side"] in {"buy", "sell"} for t in result["trades"])
        # Over-weight US equity must be sold, not bought.
        equity_sides = {t["side"] for t in result["trades"] if t["asset_class"] == "us_equity"}
        assert equity_sides == {"sell"}

    def test_selling_a_gain_position_estimates_a_tax_cost(self):
        positions = [
            {**POSITIONS[1], "account_id": "a1", "account_name": "Brokerage",
             "security_id": "ACME", "is_long_term": True}
        ]
        targets = [{"asset_class": "us_equity", "target_weight": 0.10}, {"asset_class": "cash", "target_weight": 0.90}]
        result = advisory.build_rebalance_plan(positions, targets, AS_OF, ltcg_rate=0.20).result
        assert result["estimated_tax_cost"] > 0

    def test_rebalance_states_that_nothing_is_executed(self):
        result = advisory.build_rebalance_plan([], [], AS_OF)
        assert any("not an order" in limitation.lower() for limitation in result.limitations)


class TestInstitutional:
    def test_adp_passes_within_the_alternative_limit(self):
        result = institutional.adp_acp_test(
            hce_average=0.078, nhce_average=0.064, test_type="ADP", tax_year=2025, as_of=AS_OF
        ).result
        assert result["result"] == "pass"

    def test_adp_fails_and_returns_a_correction(self):
        result = institutional.adp_acp_test(
            hce_average=0.12, nhce_average=0.04, test_type="ADP", tax_year=2025, as_of=AS_OF
        ).result
        assert result["result"] == "fail"
        assert result["corrective_action"]

    def test_top_heavy_threshold_is_sixty_percent(self):
        under = institutional.top_heavy_test(
            key_employee_balances=59, total_plan_assets=100, tax_year=2025, as_of=AS_OF
        ).result
        over = institutional.top_heavy_test(
            key_employee_balances=61, total_plan_assets=100, tax_year=2025, as_of=AS_OF
        ).result
        assert under["is_top_heavy"] is False
        assert over["is_top_heavy"] is True

    def test_ips_monitor_flags_underperformance(self):
        options = [
            {"id": "1", "name": "Good Fund", "three_year_return": 0.11, "benchmark_three_year": 0.10,
             "peer_rank_percentile": 25, "expense_ratio": 0.004, "category_median_expense": 0.006},
            {"id": "2", "name": "Poor Fund", "three_year_return": 0.05, "benchmark_three_year": 0.10,
             "peer_rank_percentile": 82, "expense_ratio": 0.009, "category_median_expense": 0.006},
        ]
        result = institutional.ips_monitor(options, AS_OF).result
        statuses = {row["name"]: row["ips_status"] for row in result["options"]}
        assert statuses["Good Fund"] == "pass"
        assert statuses["Poor Fund"] == "replace"
        assert result["compliant"] is False

    def test_estate_tax_applies_only_above_the_exemption(self):
        small = institutional.estate_projection(
            gross_estate=5_000_000, liabilities=0, lifetime_gifts_used=0,
            charitable_bequests=0, is_married=False, as_of=AS_OF,
        ).result
        assert small["estimated_federal_tax"] == 0

        large = institutional.estate_projection(
            gross_estate=40_000_000, liabilities=0, lifetime_gifts_used=0,
            charitable_bequests=0, is_married=False, as_of=AS_OF,
        ).result
        assert large["estimated_federal_tax"] == pytest.approx((40_000_000 - 15_000_000) * 0.40)

    def test_charitable_deduction_respects_the_agi_limits(self):
        result = institutional.charitable_deduction(
            cash_gifts=500_000, appreciated_gifts_fmv=500_000, appreciated_cost_basis=100_000,
            adjusted_gross_income=1_000_000, marginal_rate=0.37, ltcg_rate=0.20, as_of=AS_OF,
        ).result
        assert result["deductible_cash"] == 500_000  # under the 60% limit
        assert result["deductible_appreciated"] == 300_000  # capped at 30% of AGI
        assert result["carryforward"] == 200_000
        assert result["capital_gains_avoided"] == 400_000

    def test_plan_health_improves_with_participation(self):
        low = institutional.plan_health(
            eligible_employees=1000, participating_employees=400, average_deferral_rate=0.04,
            average_balance=40_000, participants_with_beneficiary=200, auto_enrollment=False,
            auto_escalation=False, as_of=AS_OF,
        ).result
        high = institutional.plan_health(
            eligible_employees=1000, participating_employees=950, average_deferral_rate=0.10,
            average_balance=150_000, participants_with_beneficiary=900, auto_enrollment=True,
            auto_escalation=True, as_of=AS_OF,
        ).result
        assert high["score"] > low["score"]
        assert high["grade"] == "strong"
