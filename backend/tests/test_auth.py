"""Authentication and role-based authorisation (§5, §46)."""

from __future__ import annotations

import pytest

from tests.conftest import ACCOUNTS, DEMO_PASSWORD, auth_headers


class TestAuthentication:
    def test_valid_credentials_return_a_token_and_profile(self, client):
        response = client.post(
            "/api/auth/login", json={"email": ACCOUNTS["client"], "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["user"]["role"] == "client"
        assert body["user"]["home_route"] == "/dashboard"

    def test_wrong_password_is_rejected(self, client):
        response = client.post(
            "/api/auth/login", json={"email": ACCOUNTS["client"], "password": "wrong-password"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"

    def test_unknown_email_is_rejected_without_leaking_existence(self, client):
        response = client.post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": DEMO_PASSWORD}
        )
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Incorrect email or password."

    def test_email_is_case_insensitive(self, client):
        response = client.post(
            "/api/auth/login", json={"email": ACCOUNTS["client"].upper(), "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200

    def test_malformed_payload_is_a_validation_error(self, client):
        response = client.post("/api/auth/login", json={"email": ""})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_protected_route_requires_a_token(self, client):
        assert client.get("/api/dashboard").status_code == 401

    def test_a_garbage_token_is_rejected(self, client):
        response = client.get("/api/dashboard", headers={"Authorization": "Bearer not-a-token"})
        assert response.status_code == 401

    def test_me_returns_the_signed_in_profile(self, client, client_headers):
        body = client.get("/api/auth/me", headers=client_headers).json()
        assert body["email"] == ACCOUNTS["client"]
        assert "wealth:view_own" in body["permissions"]

    def test_a_failed_sign_in_is_written_to_the_audit_trail(self, client, compliance_headers):
        client.post("/api/auth/login", json={"email": "intruder@example.com", "password": "guessing"})
        events = client.get("/api/audit?action=login_failed", headers=compliance_headers).json()["events"]
        assert any(e["status"] == "failed" for e in events)


class TestDemoAccounts:
    def test_demo_accounts_are_listed_without_credentials(self, client):
        accounts = client.get("/api/auth/demo-accounts").json()
        assert len(accounts) >= 6
        labels = {a["label"] for a in accounts}
        assert {"Client Demo", "Advisor Demo", "Sponsor Demo", "Participant Demo",
                "Compliance Demo", "Admin Demo"} <= labels
        for account in accounts:
            assert "password" not in account
            assert "password_hash" not in account

    def test_every_demo_account_can_actually_sign_in(self, client):
        for account in client.get("/api/auth/demo-accounts").json():
            response = client.post(
                "/api/auth/login", json={"email": account["email"], "password": DEMO_PASSWORD}
            )
            assert response.status_code == 200, f"{account['label']} could not sign in"


class TestAuthorisation:
    @pytest.mark.parametrize(
        "role,expected_home",
        [
            ("client", "/dashboard"),
            ("advisor", "/advisor"),
            ("sponsor", "/institutional"),
            ("participant", "/participant"),
            ("compliance", "/compliance"),
            ("admin", "/admin"),
        ],
    )
    def test_each_role_lands_in_its_own_workspace(self, client, role, expected_home):
        response = client.post(
            "/api/auth/login", json={"email": ACCOUNTS[role], "password": DEMO_PASSWORD}
        )
        assert response.json()["user"]["home_route"] == expected_home

    def test_a_client_cannot_open_the_advisor_workstation(self, client, client_headers):
        assert client.get("/api/advisor", headers=client_headers).status_code == 403

    def test_a_client_cannot_read_the_audit_trail(self, client, client_headers):
        assert client.get("/api/audit", headers=client_headers).status_code == 403

    def test_a_participant_cannot_read_client_portfolios(self, client, participant_headers):
        assert client.get("/api/portfolio", headers=participant_headers).status_code == 403

    def test_a_client_cannot_read_another_households_data(self, client, client_headers, advisor_headers):
        book = client.get("/api/advisor/clients", headers=advisor_headers).json()["clients"]
        own = client.get("/api/dashboard", headers=client_headers).json()["household"]["id"]
        other = next(row["household_id"] for row in book if row["household_id"] != own)
        response = client.get(f"/api/dashboard?household_id={other}", headers=client_headers)
        assert response.status_code == 403

    def test_a_client_cannot_open_another_households_account(self, client, client_headers, advisor_headers):
        own = client.get("/api/dashboard", headers=client_headers).json()["household"]["id"]
        book = client.get("/api/advisor/clients", headers=advisor_headers).json()["clients"]
        other = next(row["household_id"] for row in book if row["household_id"] != own)
        accounts = client.get(f"/api/accounts?household_id={other}", headers=advisor_headers).json()["accounts"]
        response = client.get(f"/api/accounts/{accounts[0]['id']}", headers=client_headers)
        assert response.status_code == 403

    def test_an_advisor_can_read_a_household_in_their_book(self, client, advisor_headers):
        book = client.get("/api/advisor/clients", headers=advisor_headers).json()["clients"]
        response = client.get(f"/api/dashboard?household_id={book[0]['household_id']}", headers=advisor_headers)
        assert response.status_code == 200

    def test_compliance_can_read_the_audit_trail(self, client, compliance_headers):
        assert client.get("/api/audit", headers=compliance_headers).status_code == 200

    def test_admin_holds_every_permission(self, client):
        headers = auth_headers(client, "admin")
        profile = client.get("/api/auth/me", headers=headers).json()
        assert "admin:all" in profile["permissions"]
        assert client.get("/api/advisor", headers=headers).status_code == 200
        assert client.get("/api/compliance", headers=headers).status_code == 200
