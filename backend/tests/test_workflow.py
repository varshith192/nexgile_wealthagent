"""The approval engine (§37) and the audit trail (§38)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


def _create_recommendation(client, headers, household_id: str, title: str, submit: bool = False) -> dict:
    response = client.post(
        "/api/recommendations",
        json={
            "title": title,
            "summary": "Created by the workflow test suite.",
            "category": "portfolio",
            "severity": "medium",
            "rationale": "Exercises the approval state machine.",
            "suggested_action": "Review and decide.",
            "household_id": household_id,
            "submit": submit,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestApprovalStateMachine:
    def test_a_new_recommendation_starts_as_a_draft_with_an_approval(self, client, advisor_headers, household_id):
        rec = _create_recommendation(client, advisor_headers, household_id, "Draft state test")
        assert rec["status"] == "draft"
        assert rec["approval_id"]

    def test_the_happy_path_runs_draft_to_completed(self, client, advisor_headers, household_id, client_reviewer):
        rec = _create_recommendation(client, advisor_headers, household_id, "Full lifecycle test")
        approval_id = rec["approval_id"]

        submitted = client.post(f"/api/approvals/{approval_id}/submit", json={}, headers=advisor_headers)
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "submitted"

        reviewed = client.post(
            f"/api/approvals/{approval_id}/review", json={"note": "Reviewing"}, headers=client_reviewer
        )
        assert reviewed.json()["status"] == "under_review"

        approved = client.post(
            f"/api/approvals/{approval_id}/approve",
            json={"note": "Consistent with the investment policy."},
            headers=client_reviewer,
        )
        assert approved.json()["status"] == "approved"
        assert approved.json()["decision_note"] == "Consistent with the investment policy."

        completed = client.post(f"/api/approvals/{approval_id}/complete", json={}, headers=client_reviewer)
        assert completed.json()["status"] == "completed"

    def test_the_recommendation_status_follows_its_approval(self, client, advisor_headers, household_id, client_reviewer):
        rec = _create_recommendation(client, advisor_headers, household_id, "Status sync test", submit=True)
        client.post(f"/api/approvals/{rec['approval_id']}/approve", json={}, headers=client_reviewer)
        refreshed = client.get(f"/api/recommendations/{rec['id']}", headers=advisor_headers).json()
        assert refreshed["status"] == "approved"

    def test_an_illegal_transition_is_refused(self, client, advisor_headers, household_id, client_reviewer):
        rec = _create_recommendation(client, advisor_headers, household_id, "Illegal transition test")
        # A draft cannot jump straight to completed.
        response = client.post(
            f"/api/approvals/{rec['approval_id']}/complete", json={}, headers=client_reviewer
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid_workflow_transition"

    def test_a_rejected_request_is_terminal(self, client, advisor_headers, household_id, client_reviewer):
        rec = _create_recommendation(client, advisor_headers, household_id, "Rejection test", submit=True)
        rejected = client.post(
            f"/api/approvals/{rec['approval_id']}/reject",
            json={"note": "Not appropriate at this time."},
            headers=client_reviewer,
        )
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["available_transitions"] == []

        again = client.post(f"/api/approvals/{rec['approval_id']}/approve", json={}, headers=client_reviewer)
        assert again.status_code == 409

    def test_a_requester_cannot_approve_their_own_request(self, client, advisor_headers, household_id):
        rec = _create_recommendation(client, advisor_headers, household_id, "Self-approval test", submit=True)
        response = client.post(f"/api/approvals/{rec['approval_id']}/approve", json={}, headers=advisor_headers)
        assert response.status_code == 403
        assert "yourself" in response.json()["error"]["message"]

    def test_a_client_cannot_approve_anything(self, client, advisor_headers, client_headers, household_id):
        rec = _create_recommendation(client, advisor_headers, household_id, "Client approval test", submit=True)
        response = client.post(f"/api/approvals/{rec['approval_id']}/approve", json={}, headers=client_headers)
        assert response.status_code == 403

    def test_every_transition_is_recorded_in_the_event_history(self, client, advisor_headers, household_id, client_reviewer):
        rec = _create_recommendation(client, advisor_headers, household_id, "Event history test", submit=True)
        client.post(f"/api/approvals/{rec['approval_id']}/approve", json={}, headers=client_reviewer)
        approval = client.get(f"/api/approvals/{rec['approval_id']}", headers=advisor_headers).json()
        statuses = [event["to_status"] for event in approval["events"]]
        assert statuses == ["draft", "submitted", "approved"]
        assert all(event["actor_name"] for event in approval["events"])

    def test_available_transitions_reflect_the_callers_role(self, client, advisor_headers, household_id, client_reviewer):
        rec = _create_recommendation(client, advisor_headers, household_id, "Transitions by role test", submit=True)
        as_requester = client.get(f"/api/approvals/{rec['approval_id']}", headers=advisor_headers).json()
        as_reviewer = client.get(f"/api/approvals/{rec['approval_id']}", headers=client_reviewer).json()
        assert "approved" not in as_requester["available_transitions"]
        assert "approved" in as_reviewer["available_transitions"]

    def test_the_queue_reports_a_pending_count(self, client, advisor_headers):
        body = client.get("/api/approvals?status_filter=submitted", headers=advisor_headers).json()
        assert body["pending_count"] >= 0
        assert all(a["status"] == "submitted" for a in body["approvals"])


class TestRebalanceWorkflow:
    def test_a_proposal_lists_trades_and_costs_without_executing(self, client, advisor_headers, household_id):
        response = client.post(
            "/api/advisor/rebalancing", json={"household_id": household_id}, headers=advisor_headers
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "draft"
        assert body["is_simulated"] is True
        assert "never routes orders" in body["execution_note"]
        for trade in body["trades"]:
            assert trade["status"] == "proposed"
            assert trade["rationale"]

    def test_an_unapproved_rebalance_cannot_be_executed(self, client, advisor_headers, household_id):
        created = client.post(
            "/api/advisor/rebalancing", json={"household_id": household_id}, headers=advisor_headers
        ).json()
        response = client.post(f"/api/advisor/rebalancing/{created['id']}/execute", headers=advisor_headers)
        assert response.status_code == 409

    def test_execution_after_approval_is_marked_simulated(self, client, advisor_headers, household_id):
        investment_team = auth_headers(client, "investment_team")
        created = client.post(
            "/api/advisor/rebalancing", json={"household_id": household_id}, headers=advisor_headers
        ).json()
        client.post(f"/api/approvals/{created['approval_id']}/submit", json={}, headers=advisor_headers)
        client.post(f"/api/approvals/{created['approval_id']}/approve", json={}, headers=investment_team)

        executed = client.post(
            f"/api/advisor/rebalancing/{created['id']}/execute", headers=investment_team
        ).json()
        assert executed["status"] == "completed"
        assert executed["is_simulated"] is True
        assert all(t["status"] == "filled_simulated" for t in executed["trades"])


class TestHarvestWorkflow:
    def test_a_harvest_proposal_carries_a_loss_and_is_simulated(self, client, advisor_headers, household_id):
        tax_headers = auth_headers(client, "tax_specialist")
        loss_opportunities = client.get(
            f"/api/tax?household_id={household_id}", headers=advisor_headers
        ).json()["harvest"]["result"]["loss_opportunities"]
        proposed = {
            h["tax_lot_id"]
            for h in client.get(f"/api/tax/harvests?household_id={household_id}", headers=advisor_headers).json()
        }
        lot_id = next((o["lot_id"] for o in loss_opportunities if o["lot_id"] not in proposed), None)
        if lot_id is None:
            pytest.skip("no unproposed harvest candidates in the seeded dataset")

        response = client.post(
            "/api/tax/harvests",
            json={"tax_lot_id": lot_id, "household_id": household_id},
            headers=tax_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["unrealized_loss"] < 0
        assert body["is_simulated"] is True

    def test_the_same_lot_cannot_be_proposed_twice(self, client, advisor_headers, household_id):
        tax_headers = auth_headers(client, "tax_specialist")
        proposed = {
            h["tax_lot_id"]
            for h in client.get(f"/api/tax/harvests?household_id={household_id}", headers=advisor_headers).json()
        }
        loss_opportunities = client.get(
            f"/api/tax?household_id={household_id}", headers=advisor_headers
        ).json()["harvest"]["result"]["loss_opportunities"]
        fresh = next((o["lot_id"] for o in loss_opportunities if o["lot_id"] not in proposed), None)
        if fresh is None:
            pytest.skip("every harvest candidate already has a proposal")

        first = client.post(
            "/api/tax/harvests", json={"tax_lot_id": fresh, "household_id": household_id}, headers=tax_headers
        )
        assert first.status_code == 201
        second = client.post(
            "/api/tax/harvests", json={"tax_lot_id": fresh, "household_id": household_id}, headers=tax_headers
        )
        assert second.status_code == 409


class TestBeneficiaryWorkflow:
    def test_a_change_is_drafted_and_routed_rather_than_applied(self, client, advisor_headers, household_id):
        estate = client.get(f"/api/estate?household_id={household_id}", headers=advisor_headers).json()
        beneficiary = estate["beneficiaries"][0]
        original = beneficiary["percentage"]

        response = client.post(
            "/api/estate/beneficiaries/change",
            json={"beneficiary_id": beneficiary["id"], "new_percentage": 55.0, "household_id": household_id},
            headers=advisor_headers,
        )
        assert response.status_code == 201
        assert response.json()["status"] == "draft"

        refreshed = client.get(f"/api/estate?household_id={household_id}", headers=advisor_headers).json()
        updated = next(b for b in refreshed["beneficiaries"] if b["id"] == beneficiary["id"])
        assert updated["percentage"] == original, "the live designation must not change before approval"
        assert updated["pending_percentage"] == 55.0

    def test_the_change_only_applies_once_the_approval_completes(self, client, advisor_headers, household_id, compliance_headers):
        # A beneficiary change is decided by estate/trust or compliance, never by
        # the investment team, so this workflow uses a different reviewer.
        estate = client.get(f"/api/estate?household_id={household_id}", headers=advisor_headers).json()
        beneficiary = estate["beneficiaries"][-1]
        created = client.post(
            "/api/estate/beneficiaries/change",
            json={"beneficiary_id": beneficiary["id"], "new_percentage": 42.0, "household_id": household_id},
            headers=advisor_headers,
        ).json()

        approval_id = created["approval_id"]
        client.post(f"/api/approvals/{approval_id}/submit", json={}, headers=advisor_headers)
        client.post(f"/api/approvals/{approval_id}/approve", json={}, headers=compliance_headers)
        client.post(f"/api/approvals/{approval_id}/complete", json={}, headers=compliance_headers)

        refreshed = client.get(f"/api/estate?household_id={household_id}", headers=advisor_headers).json()
        updated = next(b for b in refreshed["beneficiaries"] if b["id"] == beneficiary["id"])
        assert updated["percentage"] == 42.0
        assert updated["status"] == "completed"

    def test_a_percentage_above_one_hundred_is_rejected(self, client, advisor_headers, household_id):
        estate = client.get(f"/api/estate?household_id={household_id}", headers=advisor_headers).json()
        response = client.post(
            "/api/estate/beneficiaries/change",
            json={
                "beneficiary_id": estate["beneficiaries"][0]["id"],
                "new_percentage": 140.0,
                "household_id": household_id,
            },
            headers=advisor_headers,
        )
        assert response.status_code == 422


class TestAuditTrail:
    def test_actions_are_recorded_with_actor_entity_and_time(self, client, advisor_headers, household_id, client_reviewer):
        _create_recommendation(client, advisor_headers, household_id, "Audit capture test")
        events = client.get(
            f"/api/audit?household_id={household_id}&entity_type=recommendation", headers=client_reviewer
        ).json()["events"]
        assert events
        event = events[0]
        assert event["actor_name"] and event["entity_type"] and event["created_at"]

    def test_a_decision_records_the_before_and_after_state(self, client, advisor_headers, household_id, client_reviewer):
        rec = _create_recommendation(client, advisor_headers, household_id, "Before/after test", submit=True)
        client.post(f"/api/approvals/{rec['approval_id']}/approve", json={}, headers=client_reviewer)
        events = client.get(
            f"/api/audit?entity_type=approval&entity_id={rec['approval_id']}", headers=client_reviewer
        ).json()["events"]
        decision = next(e for e in events if e["action"] == "approval_decided")
        assert decision["before_state"]["status"] == "submitted"
        assert decision["after_state"]["status"] == "approved"

    def test_the_trail_can_be_filtered_by_action(self, client, client_reviewer):
        events = client.get("/api/audit?action=login", headers=client_reviewer).json()["events"]
        assert events and all(e["action"] == "login" for e in events)

    def test_scenario_runs_are_recorded_as_leaving_records_unchanged(self, client, client_headers, household_id, client_reviewer):
        goal_id = client.get("/api/goals", headers=client_headers).json()["result"]["goals"][0]["id"]
        client.post(f"/api/goals/{goal_id}/scenarios", json={}, headers=client_headers)
        events = client.get(
            f"/api/audit?action=scenario_run&household_id={household_id}", headers=client_reviewer
        ).json()["events"]
        assert events
        assert "books of record unchanged" in events[0]["summary"]
