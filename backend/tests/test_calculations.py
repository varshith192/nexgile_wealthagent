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
    def test_short_and_long_term_equity_gains_are_taxed_at_different_rates(self):
        result = tax.estimate_capital_gains_tax(
            equity_stcg=1_00_000, equity_ltcg=2_00_000, other_stcg=0, other_ltcg=0,
            slab_rate=0.30, total_income=20_00_000, as_of=AS_OF,
        ).result
        # Section 111A at 20% on the full short-term gain.
        assert result["tax_equity_stcg"] == pytest.approx(1_00_000 * 0.20)
        # Section 112A at 12.5% only above the Rs 1,25,000 exemption.
        assert result["tax_equity_ltcg"] == pytest.approx((2_00_000 - 1_25_000) * 0.125)
        assert result["exemption_used"] == pytest.approx(1_25_000)

    def test_a_long_term_loss_only_offsets_long_term_gains(self):
        result = tax.estimate_capital_gains_tax(
            equity_stcg=1_00_000, equity_ltcg=-1_00_000, other_stcg=0, other_ltcg=0,
            slab_rate=0.30, total_income=20_00_000, as_of=AS_OF,
        ).result
        # The short-term gain is untouched by a long-term loss.
        assert result["taxable_equity_stcg"] == pytest.approx(1_00_000)
        assert result["taxable_equity_ltcg"] == pytest.approx(0)

    def test_holding_period_boundary_is_366_days(self):
        assert tax.holding_period(date(2025, 9, 4), date(2026, 9, 3)) == "short_term"
        assert tax.holding_period(date(2025, 9, 4), date(2026, 9, 5)) == "long_term"

    def test_india_has_no_wash_sale_rule_so_harvesting_surfaces_losses_and_gains(self):
        lots = [
            {"id": "1", "symbol": "NIFTYBEES", "name": "Nifty ETF", "account_id": "a1", "account_name": "Demat",
             "asset_class": "indian_equity", "quantity": 1000, "cost_per_share": 100.0, "price": 84.0,
             "acquired_on": date(2023, 1, 10)},
            {"id": "2", "symbol": "TCS", "name": "TCS", "account_id": "a1", "account_name": "Demat",
             "asset_class": "indian_equity", "quantity": 100, "cost_per_share": 300.0, "price": 400.0,
             "acquired_on": date(2023, 1, 10)},
        ]
        result = tax.harvest_opportunities(
            lots, slab_rate=0.30, ltcg_exemption_remaining=1_25_000.0, as_of=AS_OF, minimum_loss=1_000, minimum_gain=1_000
        ).result
        assert [row["symbol"] for row in result["loss_opportunities"]] == ["NIFTYBEES"]
        assert [row["symbol"] for row in result["gain_opportunities"]] == ["TCS"]
        # The loss lot is long-term (acquired 2023, sold 2026): 16,000 loss x 12.5% x 1.04 cess.
        assert result["loss_benefit"] == pytest.approx(16_000 * 0.125 * 1.04)

    def test_the_section_112a_exemption_caps_the_gain_harvest(self):
        lots = [
            {"id": "1", "symbol": "TCS", "name": "TCS", "account_id": "a1", "account_name": "Demat",
             "asset_class": "indian_equity", "quantity": 1000, "cost_per_share": 100.0, "price": 300.0,
             "acquired_on": date(2020, 1, 1)},
        ]
        result = tax.harvest_opportunities(
            lots, slab_rate=0.30, ltcg_exemption_remaining=50_000.0, as_of=AS_OF, minimum_loss=1_000, minimum_gain=1_000
        ).result
        assert result["gain_opportunities"][0]["harvestable_gain"] == pytest.approx(50_000.0)
        assert result["exemption_remaining_after"] == pytest.approx(0.0)

    def test_new_regime_is_cheaper_above_the_87a_rebate_limit(self):
        result = tax.compare_regimes(gross_income=24_00_000, deductions=0, age=40, as_of=AS_OF).result
        assert result["recommended_regime"] == "new"
        assert result["new_regime_tax"] < result["old_regime_tax"]

    def test_the_87a_rebate_zeroes_tax_at_the_new_regime_threshold(self):
        result = tax.slab_tax(gross_income=12_00_000, regime="new", deductions=0, age=40, as_of=AS_OF).result
        assert result["total_tax"] == 0.0


class TestRetirement:
    KWARGS = dict(
        current_age=45, retirement_age=60, current_savings=50_00_000, annual_contribution=3_00_000,
        employer_contribution=1_00_000, expected_return=0.08, current_income=20_00_000,
        eps_pension_annual=1_20_000, nps_annuity_annual=0, rental_income_annual=0,
        healthcare_annual=1_00_000, inflation=0.06, as_of=AS_OF,
    )

    def test_projection_reports_a_replacement_ratio_and_status(self):
        result = retirement.retirement_projection(**self.KWARGS).result
        assert result["projected_corpus"] > 50_00_000
        assert result["status"] in {"on_track", "monitor", "at_risk"}
        assert result["years_to_retirement"] == 15

    def test_saving_more_improves_the_outcome(self):
        base = retirement.retirement_projection(**self.KWARGS).result
        more = retirement.retirement_projection(**{**self.KWARGS, "annual_contribution": 6_00_000}).result
        assert more["projected_corpus"] > base["projected_corpus"]
        assert more["income_gap"] > base["income_gap"]

    def test_monte_carlo_is_reproducible_for_the_same_seed(self):
        kwargs = dict(starting_balance=50_00_000, annual_contribution=4_00_000, years=20,
                      expected_return=0.08, volatility=0.14, as_of=AS_OF, trials=200)
        first = retirement.monte_carlo_projection(**kwargs).result
        second = retirement.monte_carlo_projection(**kwargs).result
        assert first["percentiles"] == second["percentiles"]

    def test_monte_carlo_percentiles_are_ordered(self):
        result = retirement.monte_carlo_projection(
            starting_balance=50_00_000, annual_contribution=4_00_000, years=20,
            expected_return=0.08, volatility=0.14, as_of=AS_OF, trials=300,
        ).result
        p = result["percentiles"]
        assert p["p10"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p90"]

    def test_success_is_measured_against_the_required_corpus_when_given(self):
        result = retirement.monte_carlo_projection(
            starting_balance=1_00_000, annual_contribution=10_000, years=10,
            expected_return=0.08, volatility=0.14, as_of=AS_OF, trials=200,
            success_threshold=50_00_00_000,
        ).result
        assert result["success_rate"] == 0.0
        assert "500,000,000" in result["success_basis"]

    def test_epf_and_eps_split_the_employer_contribution(self):
        result = retirement.epf_projection(
            current_balance=0, monthly_basic=50_000, years_to_retirement=10,
            salary_growth=0.06, interest_rate=0.0825, as_of=AS_OF,
        ).result
        assert result["eps_diverted"] > 0
        assert result["projected_corpus"] > result["employee_contribution"]

    def test_eps_pension_requires_ten_years_of_service(self):
        short = retirement.eps_pension(pensionable_salary=15_000, pensionable_service=8, as_of=AS_OF).result
        long = retirement.eps_pension(pensionable_salary=15_000, pensionable_service=20, as_of=AS_OF).result
        assert short["is_eligible"] is False
        assert short["monthly_pension"] == 0.0
        assert long["is_eligible"] is True
        assert long["monthly_pension"] == pytest.approx((15_000 * 20) / 70)

    def test_gratuity_is_capped_at_the_statutory_ceiling(self):
        result = retirement.gratuity_estimate(
            last_drawn_monthly=5_00_000, years_of_service=30, as_of=AS_OF
        ).result
        assert result["capped"] is True
        assert result["gratuity_payable"] == pytest.approx(retirement.GRATUITY_CAP)

    def test_service_linked_eligibility_is_all_or_nothing(self):
        before = retirement.vesting_status(hire_date=date(2024, 6, 1), as_of=AS_OF).result
        after = retirement.vesting_status(hire_date=date(2014, 6, 1), as_of=AS_OF).result
        # The employee's own EPF corpus is always fully theirs from day one.
        assert before["vested_percentage"] == 1.0
        assert before["eps_eligible"] is False
        assert after["eps_eligible"] is True
        assert after["gratuity_eligible"] is True


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
    def test_epf_contribution_check_passes_at_statutory_rates(self):
        wages = 60_00_000.0
        eps = min(wages, institutional.EPF_WAGE_CEILING_MONTHLY * 12 * 10) * institutional.EPS_DIVERSION_RATE
        result = institutional.epf_contribution_check(
            total_wages=wages,
            employee_remitted=wages * institutional.EPF_EMPLOYEE_RATE,
            employer_remitted=wages * institutional.EPF_EMPLOYER_RATE - eps,
            eps_remitted=eps,
            member_count=10,
            as_of=AS_OF,
        ).result
        assert result["result"] == "pass"

    def test_epf_contribution_check_fails_on_a_shortfall(self):
        result = institutional.epf_contribution_check(
            total_wages=60_00_000.0, employee_remitted=5_00_000.0, employer_remitted=5_00_000.0,
            eps_remitted=0.0, member_count=10, as_of=AS_OF,
        ).result
        assert result["result"] == "fail"
        assert result["corrective_action"]

    def test_scheme_monitor_flags_underperformance(self):
        options = [
            {"id": "1", "name": "Good Fund", "three_year_return": 0.13, "benchmark_three_year": 0.12,
             "peer_rank_percentile": 25, "expense_ratio": 0.004, "category_median_expense": 0.006},
            {"id": "2", "name": "Poor Fund", "three_year_return": 0.07, "benchmark_three_year": 0.12,
             "peer_rank_percentile": 82, "expense_ratio": 0.009, "category_median_expense": 0.006},
        ]
        result = institutional.scheme_monitor(options, AS_OF).result
        statuses = {row["name"]: row["ips_status"] for row in result["options"]}
        assert statuses["Good Fund"] == "pass"
        assert statuses["Poor Fund"] == "replace"
        assert result["compliant"] is False

    def test_india_levies_no_estate_tax_regardless_of_estate_size(self):
        small = institutional.succession_review(
            gross_estate=50_00_000, liabilities=0, assets_with_nomination=50_00_000,
            assets_in_trust=0, assets_jointly_held=0, has_valid_will=True, will_registered=True,
            is_huf=False, as_of=AS_OF,
        ).result
        large = institutional.succession_review(
            gross_estate=40_00_00_000, liabilities=0, assets_with_nomination=40_00_00_000,
            assets_in_trust=0, assets_jointly_held=0, has_valid_will=True, will_registered=True,
            is_huf=False, as_of=AS_OF,
        ).result
        assert small["estate_tax_payable"] == 0.0
        assert large["estate_tax_payable"] == 0.0

    def test_succession_flags_assets_without_a_nomination_or_will(self):
        result = institutional.succession_review(
            gross_estate=1_00_00_000, liabilities=0, assets_with_nomination=0,
            assets_in_trust=0, assets_jointly_held=0, has_valid_will=False, will_registered=False,
            is_huf=False, as_of=AS_OF,
        ).result
        assert result["requires_succession_process"] == pytest.approx(1_00_00_000)
        assert any(f["finding"] == "No valid will on file" for f in result["findings"])

    def test_gift_between_relatives_is_exempt_regardless_of_amount(self):
        result = institutional.gift_tax_review(
            [{"recipient": "Son", "amount": 50_00_000.0, "gifted_on": AS_OF, "is_relative": True}], AS_OF
        ).result
        assert result["taxable_amount"] == 0.0

    def test_gift_from_a_non_relative_is_taxable_in_full_above_the_threshold(self):
        result = institutional.gift_tax_review(
            [{"recipient": "Friend", "amount": 60_000.0, "gifted_on": AS_OF, "is_relative": False}], AS_OF
        ).result
        assert result["threshold_breached"] is True
        assert result["taxable_amount"] == pytest.approx(60_000.0)  # all-or-nothing, not just the excess

    def test_section_80g_splits_capped_and_uncapped_categories(self):
        result = institutional.section_80g_deduction(
            donations_100_no_cap=1_00_000, donations_50_no_cap=0,
            donations_100_capped=0, donations_50_capped=2_00_000,
            adjusted_gross_income=10_00_000, marginal_rate=0.30, as_of=AS_OF,
        ).result
        # 100%-no-cap is deducted in full; the 50%-capped donation is limited by
        # the 10%-of-AGI qualifying limit (Rs 1,00,000) at a 50% rate.
        assert result["uncapped_deduction"] == pytest.approx(1_00_000)
        assert result["capped_deduction"] == pytest.approx(1_00_000 * 0.50)

    def test_plan_health_improves_with_participation(self):
        low = institutional.plan_health(
            eligible_employees=1000, enrolled_employees=400, average_contribution_rate=0.04,
            average_balance=4_00_000, members_with_nomination=200, uan_seeded=300,
            nps_corporate_offered=False, voluntary_pf_offered=False, as_of=AS_OF,
        ).result
        high = institutional.plan_health(
            eligible_employees=1000, enrolled_employees=1000, average_contribution_rate=0.18,
            average_balance=15_00_000, members_with_nomination=980, uan_seeded=1000,
            nps_corporate_offered=True, voluntary_pf_offered=True, as_of=AS_OF,
        ).result
        assert high["score"] > low["score"]
        assert high["grade"] == "strong"
