"""API contract tests: shapes, validation, status codes and data consistency."""

from __future__ import annotations

from datetime import date, timedelta

import pytest


class TestDashboard:
    def test_dashboard_returns_every_panel_the_client_screen_needs(self, client, client_headers):
        body = client.get("/api/dashboard", headers=client_headers).json()
        for key in (
            "household", "as_of", "net_worth", "net_worth_trend", "portfolio", "allocation",
            "concentration", "risk", "performance", "top_holdings", "goals", "needs_attention",
            "wealthagent", "notifications", "data_freshness",
        ):
            assert key in body, f"dashboard is missing {key}"

    def test_net_worth_reconciles_with_the_account_list(self, client, client_headers):
        dashboard = client.get("/api/dashboard", headers=client_headers).json()
        accounts = client.get("/api/accounts", headers=client_headers).json()
        assert dashboard["net_worth"]["result"]["net_worth"] == pytest.approx(
            accounts["summary"]["net_worth"], abs=1.0
        )

    def test_assets_less_liabilities_equals_net_worth(self, client, client_headers):
        result = client.get("/api/dashboard", headers=client_headers).json()["net_worth"]["result"]
        assert result["total_assets"] - result["total_liabilities"] == pytest.approx(result["net_worth"], abs=1.0)

    def test_data_freshness_is_declared_for_every_source(self, client, client_headers):
        freshness = client.get("/api/dashboard", headers=client_headers).json()["data_freshness"]
        assert set(freshness) == {"custodian_feed", "market_data", "performance"}
        assert set(freshness.values()) <= {"fresh", "delayed", "stale", "unavailable"}


class TestPortfolioAndHoldings:
    def test_portfolio_exposes_every_breakdown(self, client, client_headers):
        body = client.get("/api/portfolio", headers=client_headers).json()
        for key in ("valuation", "allocation", "sector_allocation", "geography_allocation",
                    "drift", "concentration", "risk", "income", "performance", "targets"):
            assert key in body

    def test_allocation_weights_sum_to_one(self, client, client_headers):
        rows = client.get("/api/portfolio", headers=client_headers).json()["allocation"]["result"]["rows"]
        assert sum(r["weight"] for r in rows) == pytest.approx(1.0, abs=1e-3)

    def test_holdings_market_value_matches_the_portfolio_valuation(self, client, client_headers):
        portfolio = client.get("/api/portfolio", headers=client_headers).json()
        holdings = client.get("/api/holdings?page_size=200", headers=client_headers).json()
        invested = portfolio["valuation"]["result"]["market_value"] - portfolio["valuation"]["result"]["cash"]
        assert holdings["totals"]["market_value"] == pytest.approx(invested, rel=1e-6)

    @pytest.mark.parametrize("period", ["1D", "1W", "1M", "3M", "YTD", "1Y", "3Y", "5Y"])
    def test_every_period_button_returns_a_return(self, client, client_headers, period):
        body = client.get(f"/api/portfolio/performance?period={period}", headers=client_headers).json()
        assert body["result"]["period"] == period
        assert isinstance(body["result"]["return"], float)

    def test_an_unknown_period_is_rejected(self, client, client_headers):
        assert client.get("/api/portfolio/performance?period=42Y", headers=client_headers).status_code == 422

    def test_holdings_can_be_searched(self, client, client_headers):
        symbol = client.get("/api/holdings?page_size=5", headers=client_headers).json()["rows"][0]["symbol"]
        rows = client.get(f"/api/holdings?search={symbol}", headers=client_headers).json()["rows"]
        assert rows and all(symbol.lower() in r["symbol"].lower() or symbol.lower() in r["name"].lower() for r in rows)

    def test_holdings_can_be_sorted_and_paginated(self, client, client_headers):
        body = client.get("/api/holdings?sort_by=gain_loss&sort_dir=desc&page_size=5", headers=client_headers).json()
        values = [r["gain_loss"] for r in body["rows"]]
        assert values == sorted(values, reverse=True)
        assert body["page_size"] == 5 and len(body["rows"]) <= 5

    def test_an_unknown_sort_column_falls_back_safely(self, client, client_headers):
        response = client.get("/api/holdings?sort_by=DROP+TABLE", headers=client_headers)
        assert response.status_code == 200

    def test_holding_detail_includes_tax_lots(self, client, client_headers):
        holding_id = client.get("/api/holdings?page_size=5", headers=client_headers).json()["rows"][0]["holding_id"]
        body = client.get(f"/api/holdings/{holding_id}", headers=client_headers).json()
        assert body["tax_lots"]
        assert {"acquired_on", "holding_period", "gain_loss"} <= set(body["tax_lots"][0])

    def test_a_missing_holding_returns_404(self, client, client_headers):
        assert client.get("/api/holdings/does-not-exist", headers=client_headers).status_code == 404


class TestAccounts:
    def test_accounts_cover_the_supported_types(self, client, client_headers):
        accounts = client.get("/api/accounts", headers=client_headers).json()["accounts"]
        types = {a["account_type"] for a in accounts}
        assert {"brokerage", "retirement", "banking", "mortgage"} <= types

    def test_each_account_declares_its_freshness_and_source(self, client, client_headers):
        for account in client.get("/api/accounts", headers=client_headers).json()["accounts"]:
            assert account["data_freshness"] in {"fresh", "delayed", "stale", "unavailable"}
            assert account["institution"]

    def test_account_detail_returns_holdings_and_transactions(self, client, client_headers):
        accounts = client.get("/api/accounts", headers=client_headers).json()["accounts"]
        brokerage = next(a for a in accounts if a["account_type"] == "brokerage")
        body = client.get(f"/api/accounts/{brokerage['id']}", headers=client_headers).json()
        assert body["holdings"] and body["transactions"]


class TestGoals:
    def test_goal_list_includes_projections(self, client, client_headers):
        body = client.get("/api/goals", headers=client_headers).json()
        assert body["result"]["goals"]
        first = body["result"]["goals"][0]
        assert {"funded_ratio", "projected_value", "status", "gap"} <= set(first)

    def test_creating_a_goal_returns_201_and_a_projection(self, client, client_headers):
        payload = {
            "name": "Sabbatical Fund",
            "goal_type": "life_event",
            "target_amount": 250_000,
            "current_amount": 40_000,
            "target_date": (date.today() + timedelta(days=1500)).isoformat(),
            "monthly_contribution": 2_000,
            "priority": "medium",
        }
        response = client.post("/api/goals", json=payload, headers=client_headers)
        assert response.status_code == 201
        body = response.json()
        assert body["goal"]["name"] == "Sabbatical Fund"
        assert body["projection"]["result"]["projected_value"] > 40_000

    def test_a_past_target_date_is_rejected(self, client, client_headers):
        response = client.post(
            "/api/goals",
            json={
                "name": "Backwards", "goal_type": "custom", "target_amount": 1000,
                "target_date": "2020-01-01",
            },
            headers=client_headers,
        )
        assert response.status_code == 422

    def test_a_negative_target_is_rejected(self, client, client_headers):
        response = client.post(
            "/api/goals",
            json={
                "name": "Negative", "goal_type": "custom", "target_amount": -5,
                "target_date": (date.today() + timedelta(days=400)).isoformat(),
            },
            headers=client_headers,
        )
        assert response.status_code == 422

    def test_scenarios_do_not_change_the_goal_itself(self, client, client_headers):
        goal_id = client.get("/api/goals", headers=client_headers).json()["result"]["goals"][0]["id"]
        before = client.get(f"/api/goals/{goal_id}", headers=client_headers).json()["goal"]
        client.post(f"/api/goals/{goal_id}/scenarios", json={"persist": True}, headers=client_headers)
        after = client.get(f"/api/goals/{goal_id}/", headers=client_headers)
        after = client.get(f"/api/goals/{goal_id}", headers=client_headers).json()["goal"]
        assert before == after

    def test_scenarios_return_the_full_comparison_set(self, client, client_headers):
        goal_id = client.get("/api/goals", headers=client_headers).json()["result"]["goals"][0]["id"]
        body = client.post(f"/api/goals/{goal_id}/scenarios", json={}, headers=client_headers).json()
        keys = {row["key"] for row in body["result"]["scenarios"]}
        assert {"base_case", "higher_savings", "lower_return", "earlier_retirement"} <= keys
        assert body["assumptions"] and body["limitations"]


class TestTaxAndEstate:
    def test_tax_centre_returns_every_section(self, client, client_headers):
        body = client.get("/api/tax", headers=client_headers).json()
        for key in ("realized_gains", "tax_estimate", "harvest", "asset_location",
                    "capital_gains_budget", "opportunities", "rmd", "roth_conversion",
                    "wash_sale_windows", "charitable_securities", "projection"):
            assert key in body

    def test_harvest_candidates_all_hold_a_loss(self, client, client_headers):
        opportunities = client.get("/api/tax", headers=client_headers).json()["harvest"]["result"]["opportunities"]
        assert all(row["unrealized_loss"] < 0 for row in opportunities)

    def test_wash_sale_check_reports_a_window(self, client, client_headers):
        holdings = client.get("/api/holdings?page_size=5", headers=client_headers).json()["rows"]
        security_id = holdings[0]["security_id"]
        body = client.get(f"/api/tax/wash-sale-check?security_id={security_id}", headers=client_headers).json()
        assert body["result"]["risk"] in {"clear", "blocked"}
        assert body["result"]["window_start"] < body["result"]["window_end"]

    def test_estate_reports_projection_and_beneficiary_gaps(self, client, client_headers):
        body = client.get("/api/estate", headers=client_headers).json()
        assert "projection" in body and "beneficiary_gaps" in body
        assert body["projection"]["assumptions"]

    def test_philanthropy_reports_deduction_impact(self, client, client_headers):
        body = client.get("/api/philanthropy", headers=client_headers).json()
        assert body["summary"]["total_balance"] >= 0
        assert "deduction_impact" in body


class TestDocuments:
    def test_document_list_returns_categories_and_counts(self, client, client_headers):
        body = client.get("/api/documents", headers=client_headers).json()
        assert body["documents"]
        assert {c["key"] for c in body["categories"]} >= {"tax", "estate", "investment"}

    def test_documents_can_be_filtered_by_category(self, client, client_headers):
        rows = client.get("/api/documents?category=tax", headers=client_headers).json()["documents"]
        assert rows and all(d["category"] == "tax" for d in rows)

    def test_classification_is_a_suggestion_with_reasons(self, client, client_headers):
        body = client.post(
            "/api/documents/classify", json={"filename": "2025_Tax_Return.pdf"}, headers=client_headers
        ).json()
        assert body["suggested_category"] == "tax"
        assert body["detected_year"] == 2025
        assert 0 < body["confidence"] <= 1
        assert body["reasons"]
        assert body["source"] == "mock_rules"

    def test_an_unrecognised_filename_is_low_confidence_not_a_guess(self, client, client_headers):
        body = client.post(
            "/api/documents/classify", json={"filename": "scan001.pdf"}, headers=client_headers
        ).json()
        assert body["suggested_category"] == "other"
        assert body["confidence"] < 0.5

    def test_uploading_stores_the_file_and_suggests_a_category(self, client, client_headers):
        response = client.post(
            "/api/documents",
            files={"file": ("2026_Form_1099_Consolidated.pdf", b"%PDF-1.4 test", "application/pdf")},
            headers=client_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["classification"]["suggested_category"] == "tax"
        assert body["review_status"] == "pending_review"

    def test_a_disallowed_file_type_is_refused(self, client, client_headers):
        response = client.post(
            "/api/documents",
            files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
            headers=client_headers,
        )
        assert response.status_code == 422

    def test_a_path_traversal_filename_is_neutralised(self, client, client_headers):
        response = client.post(
            "/api/documents",
            files={"file": ("../../etc/passwd.pdf", b"%PDF-1.4", "application/pdf")},
            headers=client_headers,
        )
        assert response.status_code == 201
        assert "/" not in response.json()["name"] and "\\" not in response.json()["name"]

    def test_a_suggestion_can_be_accepted_or_overridden(self, client, client_headers):
        created = client.post(
            "/api/documents",
            files={"file": ("Homeowners_Insurance_Policy.pdf", b"%PDF-1.4", "application/pdf")},
            headers=client_headers,
        ).json()
        accepted = client.post(
            f"/api/documents/{created['id']}/classification",
            json={"decision": "accept"},
            headers=client_headers,
        ).json()
        assert accepted["review_status"] == "reviewed"
        assert accepted["classification"]["accepted"] is True

        edited = client.post(
            f"/api/documents/{created['id']}/classification",
            json={"decision": "edit", "category": "legal"},
            headers=client_headers,
        ).json()
        assert edited["category"] == "legal"

    def test_editing_without_a_category_is_rejected(self, client, client_headers):
        document_id = client.get("/api/documents", headers=client_headers).json()["documents"][0]["id"]
        response = client.post(
            f"/api/documents/{document_id}/classification", json={"decision": "edit"}, headers=client_headers
        )
        assert response.status_code == 422


class TestSearchAndNotifications:
    def test_search_groups_results_by_category(self, client, advisor_headers):
        body = client.get("/api/search?q=retire", headers=advisor_headers).json()
        assert body["total"] > 0
        assert all({"category", "label", "results"} <= set(g) for g in body["groups"])

    def test_a_one_character_query_asks_for_more(self, client, advisor_headers):
        body = client.get("/api/search?q=a", headers=advisor_headers).json()
        assert body["groups"] == []
        assert "at least two" in body["message"]

    def test_search_is_scoped_to_the_callers_own_household(self, client, client_headers, advisor_headers):
        own = client.get("/api/dashboard", headers=client_headers).json()["household"]["name"]
        body = client.get("/api/search?q=Family", headers=client_headers).json()
        for group in body["groups"]:
            if group["category"] == "households":
                assert all(r["title"] == own for r in group["results"])

    def test_suggestions_include_recent_and_role_defaults(self, client, advisor_headers):
        body = client.get("/api/search/suggestions", headers=advisor_headers).json()
        assert body["suggested"] and body["categories"]

    def test_notifications_report_an_unread_count(self, client, client_headers):
        body = client.get("/api/notifications", headers=client_headers).json()
        assert "unread_count" in body and body["notifications"]

    def test_marking_a_notification_read_reduces_the_count(self, client, client_headers):
        before = client.get("/api/notifications", headers=client_headers).json()
        unread = [n for n in before["notifications"] if not n["is_read"]]
        if not unread:
            pytest.skip("no unread notifications in the seeded dataset")
        client.post(f"/api/notifications/{unread[0]['id']}/read", headers=client_headers)
        after = client.get("/api/notifications", headers=client_headers).json()
        assert after["unread_count"] < before["unread_count"]


class TestReportsAndCollaboration:
    def test_report_catalogue_lists_every_type(self, client, client_headers):
        catalogue = client.get("/api/reports", headers=client_headers).json()["catalogue"]
        assert {c["key"] for c in catalogue} >= {
            "portfolio", "performance", "goal", "tax", "household", "quarterly_review"
        }

    def test_generating_a_report_returns_sections_and_assumptions(self, client, client_headers):
        response = client.post(
            "/api/reports",
            json={
                "report_type": "quarterly_review",
                "period_start": (date.today() - timedelta(days=90)).isoformat(),
                "period_end": date.today().isoformat(),
            },
            headers=client_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["sections"] and body["assumptions"]
        assert body["payload"]["net_worth"]["result"]["net_worth"]

    def test_an_inverted_period_is_rejected(self, client, client_headers):
        response = client.post(
            "/api/reports",
            json={"report_type": "portfolio", "period_start": "2026-06-01", "period_end": "2026-01-01"},
            headers=client_headers,
        )
        assert response.status_code == 422

    def test_messaging_round_trip(self, client, client_headers):
        threads = client.get("/api/messages", headers=client_headers).json()["threads"]
        assert threads
        thread_id = threads[0]["id"]
        before = len(client.get(f"/api/messages/{thread_id}", headers=client_headers).json()["messages"])
        response = client.post(
            f"/api/messages/{thread_id}/reply", json={"body": "Understood, thank you."}, headers=client_headers
        )
        assert response.status_code == 201
        after = len(client.get(f"/api/messages/{thread_id}", headers=client_headers).json()["messages"])
        assert after == before + 1

    def test_an_empty_message_is_rejected(self, client, client_headers):
        thread_id = client.get("/api/messages", headers=client_headers).json()["threads"][0]["id"]
        response = client.post(f"/api/messages/{thread_id}/reply", json={"body": "   "}, headers=client_headers)
        assert response.status_code == 422

    def test_meetings_separate_upcoming_from_past(self, client, client_headers):
        body = client.get("/api/meetings", headers=client_headers).json()
        assert "upcoming" in body and "past" in body
        assert body["next_meeting"] is None or body["next_meeting"]["agenda"]


class TestInstitutional:
    def test_sponsor_dashboard_reports_plan_health(self, client, sponsor_headers):
        body = client.get("/api/institutional", headers=sponsor_headers).json()
        assert body["health"]["result"]["grade"] in {"strong", "healthy", "needs_attention", "at_risk"}
        assert body["metrics"]["participant_count"] > 0

    def test_participation_rate_is_consistent(self, client, sponsor_headers):
        plan = client.get("/api/institutional", headers=sponsor_headers).json()["plan"]
        assert plan["participation_rate"] == pytest.approx(
            plan["participating_employees"] / plan["eligible_employees"], abs=1e-3
        )

    def test_investment_lineup_is_screened_against_the_ips(self, client, sponsor_headers):
        body = client.get("/api/institutional/investments", headers=sponsor_headers).json()
        options = body["monitor"]["result"]["options"]
        assert options
        assert all(o["ips_status"] in {"pass", "watch", "replace"} for o in options)
        for option in options:
            if option["ips_status"] != "pass":
                assert option["reasons"], "a watched fund must say why"

    def test_fee_review_benchmarks_each_vendor(self, client, sponsor_headers):
        body = client.get("/api/institutional/fees", headers=sponsor_headers).json()
        assert body["benchmark"]["result"]["all_in_basis_points"] > 0
        assert body["vendors"]

    def test_participant_portal_returns_the_full_picture(self, client, participant_headers):
        body = client.get("/api/participant", headers=participant_headers).json()
        for key in ("participant", "plan", "contributions", "vesting", "loans", "investments", "readiness", "education"):
            assert key in body

    def test_readiness_responds_to_a_higher_deferral_rate(self, client, participant_headers):
        base = client.get("/api/participant/readiness", headers=participant_headers).json()
        higher = client.post(
            "/api/participant/readiness", json={"deferral_rate": 0.20}, headers=participant_headers
        ).json()
        assert (
            higher["projection"]["result"]["projected_balance"]
            > base["projection"]["result"]["projected_balance"]
        )

    def test_readiness_rejects_an_impossible_age(self, client, participant_headers):
        response = client.post("/api/participant/readiness", json={"current_age": 5}, headers=participant_headers)
        assert response.status_code == 422

    def test_compliance_centre_classifies_every_item(self, client, compliance_headers):
        body = client.get("/api/compliance", headers=compliance_headers).json()
        statuses = {row["status"] for row in body["tests"] + body["filings"]}
        assert statuses <= {"complete", "at_risk", "pending", "overdue"}


class TestErrorHandling:
    def test_a_missing_resource_returns_a_structured_404(self, client, client_headers):
        response = client.get("/api/goals/nope", headers=client_headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_an_unknown_route_returns_404(self, client, client_headers):
        assert client.get("/api/not-a-route", headers=client_headers).status_code == 404

    def test_health_reports_the_configured_adapters(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["ai_provider"] == "mock"
        assert body["ai_key_configured"] is False
        assert body["seeded"] is True
