import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite://"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
# NOTE: foreign keys stay OFF on this engine on purpose: the POC unit tests insert rows with user_id=1 without a user.
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def ls_trace():
    """Live LangSmith check: tracing is forced on for this test only, with an explicit client built from the real key."""
    from langsmith import tracing_context

    from testsupport.langsmith_check import TraceCheck

    check = TraceCheck()
    with tracing_context(enabled=True, client=check.client):
        yield check


@pytest.fixture(scope="function")
def db_session():
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register_and_login(client, email, name="Test User", income=80000):
    client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": "testpass123", "monthly_income": income})
    response = client.post("/api/v1/auth/login", data={"username": email, "password": "testpass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_token(client):
    client.post("/api/v1/auth/register", json={
        "name": "Test User", "email": "test@finance.com", "password": "testpass123", "monthly_income": 80000,
    })
    response = client.post("/api/v1/auth/login", data={"username": "test@finance.com", "password": "testpass123"})
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def other_headers(client, auth_headers):
    """A second, independent user (for cross-user access tests). Depends on auth_headers so user 1 exists first."""
    return _register_and_login(client, "other@finance.com", name="Other User")


@pytest.fixture
def test_account(client, auth_headers):
    resp = client.post("/api/v1/accounts", json={
        "account_name": "HDFC Savings", "account_type": "savings", "balance": 50000.0,
    }, headers=auth_headers)
    return resp.json()


# ---------------------------------------------------------------- AI-layer fixtures (phases 3-5)
TESTSERVER_BASE = "http://testserver/api/v1"


class FinanceApi:
    """A registered user + helpers. The AI layer's HTTP calls are routed into the real FastAPI app (real routes/auth/DB)."""

    def __init__(self, client, email="ai.user@finance.com", name="AI User"):
        self.client = client
        self.email = email
        client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": "testpass123", "monthly_income": 80000})
        self.token = client.post("/api/v1/auth/login", data={"username": email, "password": "testpass123"}).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def post(self, path, body):
        r = self.client.post(f"/api/v1{path}", json=body, headers=self.headers)
        assert r.status_code < 300, (path, r.status_code, r.text)
        return r.json()

    def get(self, path, **params):
        return self.client.get(f"/api/v1{path}", params=params, headers=self.headers)

    def seed_basic(self, spent_food=8500, budget_limit=10000):
        """Savings account, salary today, a food expense and a food budget for the current month."""
        import datetime

        today = datetime.date.today().isoformat()
        acct = self.post("/accounts", {"account_name": "HDFC Savings", "account_type": "savings", "balance": 50000})
        self.post("/budgets", {"category": "food", "monthly_limit": budget_limit, "month": datetime.date.today().month, "year": datetime.date.today().year})
        self.post("/transactions", {"account_id": acct["id"], "amount": 80000, "type": "credit", "category": "salary", "description": "Salary", "transaction_date": today})
        self.post("/transactions", {"account_id": acct["id"], "amount": spent_food, "type": "debit", "category": "food", "description": "Groceries", "merchant": "BigBazaar", "transaction_date": today})
        return acct


@pytest.fixture
def route_http(client, monkeypatch):
    """Routes httpx.request (used by common.api_client) to the in-process FastAPI app. Records (method, path) calls."""
    import httpx

    calls = []

    def fake_request(method, url, params=None, json=None, data=None, headers=None, timeout=None, **kw):
        assert url.startswith(TESTSERVER_BASE), url
        path = url[len(TESTSERVER_BASE):]
        calls.append((method.upper(), path))
        return client.request(method, f"/api/v1{path}", params=params, json=json, data=data, headers=headers)

    monkeypatch.setattr(httpx, "request", fake_request)
    monkeypatch.setenv("API_BASE_URL", TESTSERVER_BASE)
    return calls


@pytest.fixture
def finance_api(client, route_http, monkeypatch):
    api = FinanceApi(client)
    monkeypatch.setenv("API_JWT_TOKEN", api.token)
    api.calls = route_http
    return api


@pytest.fixture
def second_api(client, finance_api):
    return FinanceApi(client, email="second.user@finance.com", name="Second User")


# ---------------------------------------------------------------- real HTTP backend (for MCP stdio subprocess tests)
class LiveBackend:
    """The real API served over HTTP by a subprocess (temp SQLite file). Users are created over HTTP."""

    def __init__(self, base_url):
        self.base_url = base_url
        self._n = 0

    def new_user(self, email=None):
        import httpx

        self._n += 1
        email = email or f"live{self._n}.{__import__('uuid').uuid4().hex[:6]}@finance.com"
        r = httpx.post(f"{self.base_url}/auth/register", json={"name": "Live User", "email": email, "password": "testpass123", "monthly_income": 80000}, timeout=15)
        assert r.status_code == 201, r.text
        token = httpx.post(f"{self.base_url}/auth/login", data={"username": email, "password": "testpass123"}, timeout=15).json()["access_token"]
        return LiveUser(self.base_url, email, token)


class LiveUser:
    def __init__(self, base_url, email, token):
        self.base_url, self.email, self.token = base_url, email, token
        self.headers = {"Authorization": f"Bearer {token}"}

    def post(self, path, body):
        import httpx

        r = httpx.post(f"{self.base_url}{path}", json=body, headers=self.headers, timeout=15)
        assert r.status_code < 300, (path, r.status_code, r.text)
        return r.json()

    def get(self, path, **params):
        import httpx

        return httpx.get(f"{self.base_url}{path}", params=params, headers=self.headers, timeout=15)

    def seed(self, balance=50000, food_spent=0, budget=None):
        import datetime

        today = datetime.date.today()
        acct = self.post("/accounts", {"account_name": "HDFC Savings", "account_type": "savings", "balance": balance})
        if budget:
            self.post("/budgets", {"category": "food", "monthly_limit": budget, "month": today.month, "year": today.year})
        if food_spent:
            self.post("/transactions", {"account_id": acct["id"], "amount": food_spent, "type": "debit", "category": "food", "description": "Groceries", "transaction_date": today.isoformat()})
        return acct


@pytest.fixture(scope="session")
def live_backend(tmp_path_factory):
    import os
    import socket
    import subprocess
    import sys
    import time

    import httpx

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    db = tmp_path_factory.mktemp("livedb") / "live.db"
    env = {**os.environ, "PORT": str(port), "DATABASE_URL": f"sqlite:///{db}", "APP_ENV": "test", "OTEL_CONSOLE": "false",
           "SECRET_KEY": "live-backend-test-secret-0123456789-abcdef"}
    proc = subprocess.Popen([sys.executable, os.path.join(root, "backend", "run.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}/api/v1"
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        else:
            raise RuntimeError("live backend did not start")
        yield LiveBackend(base)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
