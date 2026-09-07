"""The complete evaluation journey (§48, §52).

    Login -> Dashboard -> Portfolio -> Goal -> WealthAgent -> Recommendation
          -> Advisor Client 360 -> Approval -> Audit trail

One test walks the whole path and asserts that each step is grounded in the
previous one, so a break anywhere in the chain fails here.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.conftest import ACCOUNTS, DEMO_PASSWORD


def test_end_to_end_client_and_advisor_journey(client):
    # ---------------------------------------------------------- 1. Login
    login = client.post("/api/auth/login", json={"email": ACCOUNTS["client"], "password": DEMO_PASSWORD})
    assert login.status_code == 200
    client_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert login.json()["user"]["home_route"] == "/dashboard"

    # ------------------------------------------------------ 2. Dashboard
    dashboard = client.get("/api/dashboard", headers=client_headers).json()
    household_id = dashboard["household"]["id"]
    net_worth = dashboard["net_worth"]["result"]["net_worth"]
    as_of = dashboard["as_of"]
    assert net_worth > 0
    assert dashboard["needs_attention"], "the dashboard must surface what needs attention"
    assert dashboard["wealthagent"]["insights"]

    # ------------------------------------------------------ 3. Portfolio
    portfolio = client.get("/api/portfolio", headers=client_headers).json()
    market_value = portfolio["valuation"]["result"]["market_value"]
    assert market_value > 0
    assert portfolio["as_of"] == as_of, "every panel must agree on the as-of date"
    # The dashboard and the portfolio page must show the same number.
    assert dashboard["portfolio"]["result"]["market_value"] == pytest.approx(market_value)

    holdings = client.get("/api/holdings?page_size=200", headers=client_headers).json()
    assert holdings["totals"]["market_value"] == pytest.approx(
        market_value - portfolio["valuation"]["result"]["cash"], rel=1e-6
    )

    # ----------------------------------------------------------- 4. Goal
    goals = client.get("/api/goals", headers=client_headers).json()["result"]["goals"]
    assert goals
    goal = next((g for g in goals if g["status"] in {"at_risk", "off_track"}), goals[0])
    detail = client.get(f"/api/goals/{goal['id']}", headers=client_headers).json()
    assert detail["projection"]["assumptions"], "a projection must publish its assumptions"
    assert detail["projection"]["limitations"], "a projection must publish its limitations"

    scenarios = client.post(f"/api/goals/{goal['id']}/scenarios", json={}, headers=client_headers).json()
    keys = {row["key"] for row in scenarios["result"]["scenarios"]}
    assert {"base_case", "higher_savings", "lower_return", "earlier_retirement"} <= keys

    # A scenario must not alter the books of record.
    after_scenarios = client.get(f"/api/goals/{goal['id']}", headers=client_headers).json()
    assert after_scenarios["goal"]["target_amount"] == detail["goal"]["target_amount"]
    assert after_scenarios["goal"]["current_amount"] == detail["goal"]["current_amount"]

    # --------------------------------------------------- 5. WealthAgent
    agent = client.get("/api/wealthagent", headers=client_headers).json()
    assert agent["provider"]["mode"] == "mock", "the product runs without an AI API key"
    assert agent["insights"] and agent["actions"]

    insight = agent["insights"][0]
    assert insight["supporting_facts"], "an insight must show its supporting data"
    assert insight["calculation_method"], "an insight must name the calculation behind it"
    assert insight["as_of"] == as_of

    answer = client.post(
        "/api/wealthagent/ask", json={"question": "What is my net worth?"}, headers=client_headers
    ).json()
    quoted = [f["raw_value"] for f in answer["grounded_facts"] if f["label"] == "Net worth"]
    assert quoted == [net_worth], "the agent must quote the verified figure, not its own"

    # ------------------------------------------------- 6. Recommendation
    advisor_login = client.post(
        "/api/auth/login", json={"email": ACCOUNTS["advisor"], "password": DEMO_PASSWORD}
    )
    advisor_headers = {"Authorization": f"Bearer {advisor_login.json()['access_token']}"}

    drafts = client.get(
        f"/api/recommendations/drafts?household_id={household_id}", headers=advisor_headers
    ).json()
    assert drafts, "the agent must propose something to act on"

    created = client.post(
        "/api/recommendations/from-draft",
        json={"draft_key": drafts[0]["key"], "household_id": household_id, "submit": True},
        headers=advisor_headers,
    )
    assert created.status_code == 201
    recommendation = created.json()
    approval_id = recommendation["approval_id"]
    assert recommendation["status"] == "submitted"

    # ------------------------------------------------ 7. Advisor Client 360
    client_360 = client.get(f"/api/advisor/clients/{household_id}", headers=advisor_headers).json()
    for section in ("profile", "household_members", "team", "accounts", "portfolio", "goals",
                    "tax", "estate", "documents", "messages", "meetings", "tasks",
                    "recommendations", "activity"):
        assert section in client_360, f"Client 360 is missing {section}"

    # The advisor must see the same net worth the client sees.
    assert client_360["net_worth"]["result"]["net_worth"] == pytest.approx(net_worth)
    assert any(r["id"] == recommendation["id"] for r in client_360["recommendations"])

    # ------------------------------------------------------- 8. Approval
    reviewer_login = client.post(
        "/api/auth/login", json={"email": ACCOUNTS["investment_team"], "password": DEMO_PASSWORD}
    )
    reviewer_headers = {"Authorization": f"Bearer {reviewer_login.json()['access_token']}"}

    queue = client.get("/api/approvals?status_filter=submitted", headers=reviewer_headers).json()
    assert any(a["id"] == approval_id for a in queue["approvals"])

    reviewed = client.post(
        f"/api/approvals/{approval_id}/review", json={"note": "Reviewing against policy."},
        headers=reviewer_headers,
    )
    assert reviewed.json()["status"] == "under_review"

    approved = client.post(
        f"/api/approvals/{approval_id}/approve",
        json={"note": "Approved. Proceed with the staged reduction."},
        headers=reviewer_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    completed = client.post(f"/api/approvals/{approval_id}/complete", json={}, headers=reviewer_headers)
    assert completed.json()["status"] == "completed"

    final = client.get(f"/api/recommendations/{recommendation['id']}", headers=advisor_headers).json()
    assert final["status"] == "completed"

    # ---------------------------------------------------- 9. Audit trail
    compliance_login = client.post(
        "/api/auth/login", json={"email": ACCOUNTS["compliance"], "password": DEMO_PASSWORD}
    )
    compliance_headers = {"Authorization": f"Bearer {compliance_login.json()['access_token']}"}

    trail = client.get(
        f"/api/audit?entity_type=approval&entity_id={approval_id}", headers=compliance_headers
    ).json()["events"]
    actions = [e["action"] for e in trail]
    assert "approval_decided" in actions
    assert "approval_completed" in actions

    decision = next(e for e in trail if e["action"] == "approval_decided")
    assert decision["before_state"]["status"] == "under_review"
    assert decision["after_state"]["status"] == "approved"
    assert decision["actor_name"], "every audit event names its actor"

    history = client.get(f"/api/approvals/{approval_id}", headers=compliance_headers).json()["events"]
    assert [e["to_status"] for e in history] == [
        "draft", "submitted", "under_review", "approved", "completed"
    ]


def test_institutional_journey(client):
    """Sponsor -> plan health -> fiduciary lineup -> compliance -> participant."""
    sponsor = client.post("/api/auth/login", json={"email": ACCOUNTS["sponsor"], "password": DEMO_PASSWORD})
    sponsor_headers = {"Authorization": f"Bearer {sponsor.json()['access_token']}"}
    assert sponsor.json()["user"]["home_route"] == "/institutional"

    dashboard = client.get("/api/institutional", headers=sponsor_headers).json()
    plan_id = dashboard["plan"]["id"]
    assert dashboard["health"]["result"]["score"] > 0
    assert dashboard["metrics"]["participant_count"] > 0

    participants = client.get(f"/api/participants?plan_id={plan_id}", headers=sponsor_headers).json()
    assert participants["total"] > 0
    assert participants["participants"][0]["vested_percentage"] <= 1.0

    lineup = client.get(f"/api/institutional/investments?plan_id={plan_id}", headers=sponsor_headers).json()
    assert lineup["monitor"]["result"]["options"]
    assert lineup["reviews"], "fiduciary evidence must exist for the committee"

    fees = client.get(f"/api/institutional/fees?plan_id={plan_id}", headers=sponsor_headers).json()
    assert fees["benchmark"]["result"]["all_in_basis_points"] > 0

    compliance = client.post(
        "/api/auth/login", json={"email": ACCOUNTS["compliance"], "password": DEMO_PASSWORD}
    )
    compliance_headers = {"Authorization": f"Bearer {compliance.json()['access_token']}"}
    centre = client.get(f"/api/compliance?plan_id={plan_id}", headers=compliance_headers).json()
    assert centre["tests"] and centre["filings"]

    adp = next(t for t in centre["tests"] if t["test_type"] == "ADP")
    run = client.post(f"/api/compliance/tests/{adp['id']}/run", headers=compliance_headers)
    assert run.status_code == 200
    calculation = run.json()["calculation"]
    assert calculation["result"]["result"] in {"pass", "fail"}
    assert calculation["assumptions"] and calculation["limitations"]

    participant = client.post(
        "/api/auth/login", json={"email": ACCOUNTS["participant"], "password": DEMO_PASSWORD}
    )
    participant_headers = {"Authorization": f"Bearer {participant.json()['access_token']}"}
    portal = client.get("/api/participant", headers=participant_headers).json()
    assert portal["participant"]["account_balance"] > 0
    assert portal["readiness"]["projection"]["result"]["status"] in {"on_track", "monitor", "at_risk"}
    assert portal["readiness"]["monte_carlo"]["result"]["success_basis"]
    assert portal["education"]["items"]


def test_no_screen_is_blank_for_any_role(client):
    """Every workspace a role can reach returns usable content, not an empty shell."""
    journeys = {
        "client": ["/api/dashboard", "/api/portfolio", "/api/accounts", "/api/holdings", "/api/goals",
                   "/api/tax", "/api/estate", "/api/philanthropy", "/api/documents", "/api/messages",
                   "/api/meetings", "/api/reports", "/api/wealthagent", "/api/notifications"],
        "advisor": ["/api/advisor", "/api/advisor/clients", "/api/advisor/rebalancing", "/api/advisor/tasks",
                    "/api/approvals", "/api/audit", "/api/search?q=johnson"],
        "sponsor": ["/api/institutional", "/api/plans", "/api/participants",
                    "/api/institutional/investments", "/api/institutional/fees", "/api/compliance"],
        "participant": ["/api/participant", "/api/participant/readiness", "/api/participant/education",
                        "/api/education", "/api/notifications"],
        "compliance": ["/api/compliance", "/api/audit", "/api/approvals", "/api/notifications"],
    }

    for role, routes in journeys.items():
        login = client.post("/api/auth/login", json={"email": ACCOUNTS[role], "password": DEMO_PASSWORD})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        for route in routes:
            response = client.get(route, headers=headers)
            assert response.status_code == 200, f"{role} could not open {route}: {response.text[:200]}"
            body = response.json()
            assert body not in ({}, [], None), f"{role} received an empty payload from {route}"
