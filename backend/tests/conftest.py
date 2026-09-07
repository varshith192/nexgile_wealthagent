"""Test fixtures.

The suite runs against a throwaway SQLite database seeded once per session with
the same generator the demo uses, so tests exercise realistic data rather than
hand-built stubs.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Point the application at a temporary database before anything imports settings.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="nexgile-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["LOCAL_STORAGE_DIR"] = str(_TMP_DIR / "documents")
os.environ["AI_PROVIDER"] = "mock"
os.environ.pop("AI_API_KEY", None)
os.environ["JWT_SECRET"] = "test-secret-long-enough-for-hmac-sha256-keys"
os.environ["ENVIRONMENT"] = "local"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal, create_all  # noqa: E402
from app.main import app  # noqa: E402
from app.seeds.seeder import DemoSeeder  # noqa: E402

DEMO_PASSWORD = settings.demo_password

ACCOUNTS = {
    "client": "sarah.johnson@example.com",
    "advisor": "marcus.webb@nexgile.example",
    "compliance": "priya.raman@nexgile.example",
    "admin": "ellen.sorensen@nexgile.example",
    "sponsor": "diane.ellis@brightpath.example",
    "participant": "andre.fitzgerald@brightpath.example",
    "tax_specialist": "hana.mori@nexgile.example",
    "investment_team": "tobias.frank@nexgile.example",
}


@pytest.fixture(scope="session", autouse=True)
def seeded_database():
    create_all()
    with SessionLocal() as db:
        DemoSeeder(db).run(reset=True)
    yield


@pytest.fixture(scope="session")
def client(seeded_database) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def db_session(seeded_database):
    with SessionLocal() as session:
        yield session


def auth_headers(client: TestClient, role: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login", json={"email": ACCOUNTS[role], "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def client_headers(client) -> dict[str, str]:
    return auth_headers(client, "client")


@pytest.fixture
def advisor_headers(client) -> dict[str, str]:
    return auth_headers(client, "advisor")


@pytest.fixture
def compliance_headers(client) -> dict[str, str]:
    return auth_headers(client, "compliance")


@pytest.fixture
def sponsor_headers(client) -> dict[str, str]:
    return auth_headers(client, "sponsor")


@pytest.fixture
def participant_headers(client) -> dict[str, str]:
    return auth_headers(client, "participant")


@pytest.fixture
def client_reviewer(client) -> dict[str, str]:
    """Investment-team headers: the role that decides on investment recommendations."""
    return auth_headers(client, "investment_team")


@pytest.fixture
def household_id(client, client_headers) -> str:
    return client.get("/api/dashboard", headers=client_headers).json()["household"]["id"]
