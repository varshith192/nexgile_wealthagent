"""The AI layer (§1, §19, §51).

Two properties matter most and are asserted directly: the product runs with no
API key, and the intelligence layer never becomes the source of a number.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.ai.base import AIContext, AIProvider
from app.ai.mock_ai import MockAIService
from app.ai.providers import AnthropicProvider, OpenAIProvider
from app.ai.service import AIService, build_provider
from app.core.config import settings


@pytest.fixture
def context() -> AIContext:
    return AIContext(
        household_id="h1",
        household_name="Test Family",
        as_of=date(2026, 9, 4),
        currency="USD",
        net_worth={"net_worth": 18_500_000, "total_assets": 22_000_000, "total_liabilities": 3_500_000},
        portfolio={"market_value": 14_200_000, "unrealized_gain": 4_100_000, "cash": 1_350_000},
        allocation={"rows": [{"key": "us_equity", "weight": 0.52}, {"key": "fixed_income", "weight": 0.22}]},
        drift={
            "breach_count": 1,
            "max_drift": 0.07,
            "rows": [{
                "asset_class": "us_equity", "current_weight": 0.52, "target_weight": 0.45,
                "drift": 0.07, "tolerance_band": 0.05, "breached": True, "dollar_drift": 994_000,
            }],
        },
        concentration={
            "top_position": {"symbol": "VTI", "name": "US Total Market", "weight": 0.18, "market_value": 2_556_000},
            "top_single_name": {"symbol": "NVDA", "name": "Nvidia", "weight": 0.14, "market_value": 1_988_000},
            "top_five_weight": 0.41,
            "hhi": 0.083,
        },
        risk={"beta": 1.08, "cash_exposure": 0.095},
        performance={"YTD": {"return": 0.0612, "benchmark_return": 0.0840, "excess_return": -0.0228}},
        income={"annual_income": 214_000, "portfolio_yield": 0.015, "municipal_income": 62_000},
        goals={
            "goals_off_track": 1,
            "goals": [{
                "id": "g2", "name": "Education Fund", "status": "at_risk", "funded_ratio": 0.78,
                "projected_value": 420_000, "inflation_adjusted_target": 538_000, "gap": -118_000,
                "additional_monthly_needed": 1_450, "years_to_target": 6, "target_date": "2032-08-01",
            }],
        },
        tax={
            "harvest": {
                "opportunity_count": 3, "total_harvestable_loss": -186_000, "total_estimated_benefit": 46_500,
                "opportunities": [{"symbol": "EFA", "unrealized_loss": -92_000, "wash_sale_risk": "clear"}],
            },
            "realized": {"net_gain": 180_000, "short_term_gain": 48_000, "long_term_gain": 132_000},
            "rmd": {"required_amount": 112_000, "distributed_amount": 40_000, "deadline": "2026-12-31"},
            "asset_location": {"total_estimated_drag": 8_400},
        },
        estate={
            "gross_estate": 22_000_000, "estimated_federal_tax": 0, "last_reviewed_on": "2021-04-12",
            "beneficiary_gaps": [{"account_name": "Roth IRA", "reason": "No primary beneficiary"}],
        },
        philanthropy={"daf_balance": 840_000, "granted_ytd": 120_000, "annual_grant_target": 250_000},
        documents={"total": 48, "pending_review": 3, "expiring_soon": [{"name": "Policy.pdf", "expires_on": "2026-11-01"}]},
        meetings=[{"title": "Q3 Review", "starts_at": "2026-09-18T15:00:00Z"}],
        data_freshness={"custodian_feed": "fresh", "market_data": "delayed"},
    )


class TestNoApiKeyRequired:
    def test_the_default_provider_is_the_deterministic_engine(self):
        assert isinstance(build_provider(), MockAIService)

    def test_the_mock_provider_needs_no_key(self):
        info = MockAIService().info()
        assert info.requires_api_key is False
        assert info.is_configured is True
        assert info.mode == "mock"

    def test_a_live_provider_without_a_key_falls_back_rather_than_failing(self, monkeypatch):
        monkeypatch.setattr(settings, "ai_provider", "anthropic")
        monkeypatch.setattr(settings, "ai_api_key", None)
        assert isinstance(build_provider(), MockAIService)

    def test_an_unknown_provider_name_falls_back(self, monkeypatch):
        monkeypatch.setattr(settings, "ai_provider", "not-a-provider")
        assert isinstance(build_provider(), MockAIService)

    @pytest.mark.parametrize("provider_cls", [AnthropicProvider, OpenAIProvider])
    def test_live_providers_implement_the_same_interface(self, provider_cls):
        provider = provider_cls(api_key=None, model="test-model")
        assert isinstance(provider, AIProvider)
        for method in ("generate_insights", "generate_recommendations", "suggest_actions",
                       "classify_document", "explain", "answer", "info"):
            assert callable(getattr(provider, method))

    def test_a_live_provider_still_answers_using_deterministic_rules(self, context):
        provider = AnthropicProvider(api_key=None, model="claude-opus-5")
        insights = provider.generate_insights(context)
        assert insights
        assert all(i.source == "deterministic_rules" for i in insights)


class TestDeterminism:
    def test_the_same_context_always_produces_the_same_insights(self, context):
        service = MockAIService()
        first = [i.model_dump(mode="json") for i in service.generate_insights(context)]
        second = [i.model_dump(mode="json") for i in service.generate_insights(context)]
        assert first == second

    def test_answers_are_reproducible(self, context):
        service = MockAIService()
        question = "How is my portfolio performing?"
        assert service.answer(question, context).answer == service.answer(question, context).answer


class TestInsightQuality:
    def test_insights_are_ordered_by_severity(self, context):
        insights = MockAIService().generate_insights(context)
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        ranks = [order[i.severity] for i in insights]
        assert ranks == sorted(ranks)

    def test_every_insight_carries_its_provenance(self, context):
        for insight in MockAIService().generate_insights(context):
            assert insight.summary and insight.impact and insight.suggested_next_step
            assert insight.supporting_facts, f"{insight.key} has no supporting data"
            assert insight.calculation_method, f"{insight.key} does not state its method"
            assert insight.assumptions and insight.limitations
            assert insight.as_of == context.as_of
            assert 0 < insight.confidence <= 1

    def test_supporting_facts_quote_figures_from_the_context(self, context):
        insights = {i.key: i for i in MockAIService().generate_insights(context)}
        concentration = insights["portfolio_concentration"]
        weights = [f.raw_value for f in concentration.supporting_facts if f.label == "Weight"]
        assert weights == [context.concentration["top_single_name"]["weight"]]

    def test_concentration_reports_the_single_name_not_the_index_fund(self, context):
        insight = {i.key: i for i in MockAIService().generate_insights(context)}["portfolio_concentration"]
        assert "Nvidia" in insight.summary
        assert "US Total Market" not in insight.summary

    def test_a_clean_portfolio_produces_no_false_alarms(self, context):
        clean = context.model_copy(
            update={
                "concentration": {"top_position": {"symbol": "VTI", "weight": 0.06}, "top_single_name": None,
                                  "top_five_weight": 0.22, "hhi": 0.03},
                "drift": {"breach_count": 0, "rows": []},
                "goals": {"goals_off_track": 0, "goals": []},
                "tax": {"harvest": {"opportunity_count": 0, "total_estimated_benefit": 0}},
                "estate": {"beneficiary_gaps": [], "last_reviewed_on": "2025-01-01"},
                "documents": {"total": 10, "expiring_soon": []},
                "risk": {"beta": 1.0, "cash_exposure": 0.03},
                "philanthropy": {},
                "data_freshness": {"custodian_feed": "fresh"},
            }
        )
        keys = {i.key for i in MockAIService().generate_insights(clean)}
        assert "portfolio_concentration" not in keys
        assert "allocation_drift" not in keys
        assert "beneficiary_gap" not in keys

    def test_recommendations_always_require_human_review(self, context):
        for draft in MockAIService().generate_recommendations(context):
            assert draft.requires_approval is True
            assert draft.assumptions and draft.limitations

    def test_no_recommendation_claims_to_execute_a_trade(self, context):
        for draft in MockAIService().generate_recommendations(context):
            text = f"{draft.summary} {draft.suggested_action} {' '.join(draft.limitations)}".lower()
            assert "executed automatically" not in text
            assert "placed the trade" not in text


class TestDocumentClassification:
    @pytest.mark.parametrize(
        "filename,category,doc_type",
        [
            ("2025_Tax_Return.pdf", "tax", "Tax Return"),
            ("Form_1099_Consolidated_2025.pdf", "tax", "Form 1099"),
            ("Revocable_Trust_Agreement.pdf", "estate", "Trust Agreement"),
            ("Durable_Power_of_Attorney.pdf", "estate", "Power of Attorney"),
            ("Umbrella_Liability_Policy.pdf", "insurance", "Insurance Policy"),
            ("401k_Annual_Statement.pdf", "retirement", "Retirement Statement"),
        ],
    )
    def test_known_document_shapes_are_recognised(self, filename, category, doc_type):
        result = MockAIService().classify_document(filename)
        assert result.suggested_category == category
        assert result.suggested_document_type == doc_type
        assert result.confidence >= 0.85

    def test_a_year_in_the_filename_is_detected(self):
        assert MockAIService().classify_document("2025_Tax_Return.pdf").detected_year == 2025

    def test_an_unknown_document_defers_to_a_person(self):
        result = MockAIService().classify_document("IMG_4821.pdf")
        assert result.suggested_category == "other"
        assert result.confidence < 0.5
        assert "person should categorise" in result.reasons[0]

    def test_the_source_is_never_presented_as_an_external_model(self):
        assert MockAIService().classify_document("2025_Tax_Return.pdf").source == "mock_rules"


class TestGroundedAnswers:
    @pytest.mark.parametrize(
        "question,intent",
        [
            ("What is my net worth?", "net_worth"),
            ("How is my portfolio performing this year?", "performance"),
            ("How am I allocated across asset classes?", "allocation"),
            ("Am I too concentrated in one holding?", "concentration"),
            ("Am I on track for retirement?", "goals"),
            ("Are there any tax opportunities?", "tax"),
            ("When did I last review my estate documents?", "estate"),
            ("How much have I given to charity?", "philanthropy"),
            ("How much cash am I holding?", "cash"),
            ("What income does the portfolio generate?", "income"),
        ],
    )
    def test_questions_route_to_the_right_intent(self, context, question, intent):
        assert MockAIService().answer(question, context).intent == intent

    def test_answers_are_grounded_in_supplied_facts(self, context):
        answer = MockAIService().answer("What is my net worth?", context)
        assert answer.grounded_facts
        assert any(f.raw_value == 18_500_000 for f in answer.grounded_facts)

    def test_every_answer_carries_the_advice_disclaimer(self, context):
        answer = MockAIService().answer("anything at all", context)
        assert "not investment, tax or legal advice" in answer.disclaimer

    def test_an_unrelated_question_returns_an_overview_rather_than_inventing(self, context):
        answer = MockAIService().answer("What is the weather in Lisbon?", context)
        assert answer.intent == "overview"
        assert "Lisbon" not in answer.answer


class TestExplanation:
    def test_a_calculation_is_narrated_with_its_method_and_caveats(self):
        calculation = {
            "method": "net_worth = assets - liabilities",
            "result": {"net_worth": 18_500_000},
            "as_of": "2026-09-04",
            "inputs": {"account_count": 11},
            "assumptions": ["Balances reflect the latest sync."],
            "limitations": ["Unlinked assets are excluded."],
            "source": "nexgile_calculation_engine",
        }
        explanation = MockAIService().explain(calculation)
        assert explanation.method == calculation["method"]
        assert explanation.assumptions == calculation["assumptions"]
        assert explanation.limitations == calculation["limitations"]
        assert explanation.source == "nexgile_calculation_engine"
        assert "18500000" in explanation.body.replace(",", "") or "18,500,000" in explanation.body


class TestServiceFacade:
    def test_the_facade_exposes_the_provider_identity(self):
        service = AIService(MockAIService())
        assert service.info.name == "mock"
        assert service.info.capabilities

    def test_the_provider_endpoint_reports_configuration(self, client):
        body = client.get("/api/wealthagent/provider").json()
        assert body["name"] == "mock"
        assert body["requires_api_key"] is False


class TestWealthAgentEndpoints:
    def test_the_workspace_returns_all_three_surfaces(self, client, client_headers):
        body = client.get("/api/wealthagent", headers=client_headers).json()
        assert body["insights"] and body["actions"]
        assert "recommendation_drafts" in body
        assert body["provider"]["mode"] == "mock"
        assert "not investment, tax or legal advice" in body["disclaimer"]

    def test_asking_a_question_returns_a_grounded_answer(self, client, client_headers):
        body = client.post(
            "/api/wealthagent/ask", json={"question": "What is my net worth?"}, headers=client_headers
        ).json()
        assert body["intent"] == "net_worth"
        assert body["grounded_facts"]

    def test_an_empty_question_is_rejected(self, client, client_headers):
        response = client.post("/api/wealthagent/ask", json={"question": ""}, headers=client_headers)
        assert response.status_code == 422

    def test_a_draft_can_be_promoted_into_a_tracked_recommendation(self, client, advisor_headers, household_id):
        drafts = client.get(
            f"/api/recommendations/drafts?household_id={household_id}", headers=advisor_headers
        ).json()
        assert drafts
        response = client.post(
            "/api/recommendations/from-draft",
            json={"draft_key": drafts[0]["key"], "household_id": household_id, "submit": True},
            headers=advisor_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "submitted"
        assert body["approval_id"]
        assert body["generator"] == "mock"

    def test_an_unknown_draft_key_returns_404(self, client, advisor_headers, household_id):
        response = client.post(
            "/api/recommendations/from-draft",
            json={"draft_key": "no-such-draft", "household_id": household_id},
            headers=advisor_headers,
        )
        assert response.status_code == 404
