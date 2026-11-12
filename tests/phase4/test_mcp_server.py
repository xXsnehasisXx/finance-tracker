"""Phase 4 — MCP server over the REAL MCP protocol (stdio subprocess) against a REAL HTTP backend. MOCK tier = no LLM involved.

Covers: tool discovery, JSON schemas, invocation, error handling, multiple/concurrent calls, per-user isolation.
Plain-function tests (spec TC-02-P4-MCP-*) run in-process against the FastAPI app.
"""
import datetime
import json
import threading

import pytest

from mcp_server import mcp_app
from mcp_server.mcp_client import McpClientError, McpToolClient

pytestmark = pytest.mark.mock

TOOLS7 = {"add_transaction", "get_transactions", "get_budget_status", "get_dashboard_summary", "set_budget", "get_account_summary", "get_accounts"}
TODAY = datetime.date.today()


# ---------------------------------------------------------------- spec tests: tools as plain functions (in-process API)
def test_mcp_01_server_object_and_run():
    assert mcp_app.mcp is not None and hasattr(mcp_app.mcp, "run")


def test_mcp_02_all_spec_tools_are_plain_callables():
    for name in ("add_transaction", "get_transactions", "get_budget_status", "get_dashboard_summary", "set_budget", "get_account_summary"):
        assert callable(getattr(mcp_app, name))


def test_mcp_03_add_transaction_via_function(finance_api):
    acct = finance_api.post("/accounts", {"account_name": "S", "account_type": "savings", "balance": 1000})
    r = mcp_app.add_transaction(account_id=acct["id"], amount=500.0, transaction_type="debit", category="food", description="MCP test", transaction_date=TODAY.isoformat(), merchant="TestMart")
    assert r["amount"] == 500.0 and r["category"] == "food" and r["merchant"] == "TestMart" and "id" in r
    assert finance_api.get(f"/accounts/{acct['id']}").json()["balance"] == 500.0


def test_mcp_04_05_06_07_read_tools_and_set_budget(finance_api):
    acct = finance_api.seed(balance=1000) if hasattr(finance_api, "seed") else finance_api.seed_basic()
    assert "total_balance" in mcp_app.get_dashboard_summary()
    b = mcp_app.set_budget(category="entertainment", monthly_limit=2000.0, month=7, year=2026)
    assert b["category"] == "entertainment" and b["month"] == 7
    status = mcp_app.get_budget_status()
    assert isinstance(status["budgets"], list) and any(x["category"] == "entertainment" for x in status["budgets"])
    assert "balance" in mcp_app.get_account_summary(account_id=acct["id"]) and "items" in mcp_app.get_transactions()


def test_mcp_08_invalid_input_returns_error_dict(finance_api):
    assert "error" in mcp_app.get_account_summary(account_id=99999)
    assert "error" in mcp_app.get_account_summary(account_id=-1)
    for bad in (dict(transaction_type="expense"), dict(category="groceries"), dict(amount=0), dict(amount=-5), dict(transaction_date="15/06/2026"), dict(description="  "), dict(account_id=0)):
        args = dict(account_id=1, amount=10.0, transaction_type="debit", category="food", description="x", transaction_date=TODAY.isoformat()) | bad
        r = mcp_app.add_transaction(**args)
        assert isinstance(r, dict) and "error" in r, bad
    assert "error" in mcp_app.set_budget(category="salary", monthly_limit=100.0, month=6, year=2026)
    assert "error" in mcp_app.set_budget(category="food", monthly_limit=100.0, month=13, year=2026)
    assert "error" in mcp_app.get_transactions(date_from="2026/01/01") and "error" in mcp_app.get_transactions(category="nope")


def test_mcp_backend_rules_still_apply_through_the_tool(finance_api):
    acct = finance_api.post("/accounts", {"account_name": "S", "account_type": "savings", "balance": 100})
    r = mcp_app.add_transaction(account_id=acct["id"], amount=500.0, transaction_type="debit", category="food", description="too much", transaction_date=TODAY.isoformat())
    assert "Insufficient balance" in r["error"]
    assert "error" in mcp_app.add_transaction(account_id=acct["id"] + 999, amount=1.0, transaction_type="debit", category="food", description="x", transaction_date=TODAY.isoformat())


def test_mcp_identity_comes_from_environment_not_arguments(finance_api, second_api, monkeypatch):
    acct = finance_api.seed_basic()
    monkeypatch.setenv("API_JWT_TOKEN", second_api.token)  # the server process acts as user 2
    assert "error" in mcp_app.get_account_summary(account_id=acct["id"]) and "Access denied" in mcp_app.get_account_summary(account_id=acct["id"])["error"]
    assert mcp_app.get_accounts()["accounts"] == []
    monkeypatch.delenv("API_JWT_TOKEN")
    assert "Not authenticated" in mcp_app.get_dashboard_summary()["error"]


def test_mcp_api_unavailable_returns_error_dict(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "request", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    monkeypatch.setenv("API_BASE_URL", "http://localhost:9999/api/v1")
    assert "unavailable" in mcp_app.get_dashboard_summary()["error"].lower()


def test_mcp_tools_log_session_and_never_log_token(finance_api, capsys, monkeypatch):
    monkeypatch.setenv("MCP_SESSION_ID", "sess1234")
    mcp_app.get_accounts()
    out = capsys.readouterr().out
    entry = next(json.loads(line) for line in out.splitlines() if '"mcp_tool_invoked"' in line)
    assert entry["session_id"] == "sess1234" and entry["tool"] == "get_accounts" and entry["poc_id"] == "POC-02" and entry["phase"] == 4
    assert finance_api.token not in out


# ---------------------------------------------------------------- REAL protocol: stdio subprocess + HTTP backend
@pytest.fixture(scope="module")
def user(live_backend):
    u = live_backend.new_user()
    u.acct = u.seed(balance=5000, food_spent=800, budget=1000)
    return u


@pytest.fixture(scope="module")
def mcp_client(live_backend, user):
    c = McpToolClient(token=user.token, base_url=live_backend.base_url, session_id="itest001")
    c.start()
    yield c
    c.close()


def test_protocol_tool_discovery_and_schemas(mcp_client):
    tools = {t["name"]: t for t in mcp_client.list_tools()}
    assert set(tools) == TOOLS7
    add = tools["add_transaction"]["input_schema"]
    assert set(add["required"]) == {"account_id", "amount", "transaction_type", "category", "description", "transaction_date"}
    assert add["properties"]["account_id"]["type"] == "integer" and add["properties"]["amount"]["type"] == "number"
    assert "'debit' (expense) or 'credit' (income)" in tools["add_transaction"]["description"]
    assert tools["get_accounts"]["input_schema"].get("properties", {}) == {}
    assert all(t["description"] for t in tools.values())


def test_protocol_invocation_returns_real_backend_data(mcp_client, user):
    dash = mcp_client.call("get_dashboard_summary")
    assert dash["monthly_expenses"] == 800.0 and dash["total_assets"] == 4200.0
    accounts = mcp_client.call("get_accounts")["accounts"]
    assert accounts[0]["id"] == user.acct["id"] and accounts[0]["balance"] == 4200.0
    budgets = mcp_client.call("get_budget_status")["budgets"]
    assert budgets[0]["category"] == "food" and budgets[0]["utilization_percent"] == 80.0 and budgets[0]["has_alert"] is True


def test_protocol_write_then_read_back(mcp_client, user):
    r = mcp_client.call("add_transaction", {"account_id": user.acct["id"], "amount": 100.0, "transaction_type": "debit", "category": "transport",
                                            "description": "Metro", "transaction_date": TODAY.isoformat(), "merchant": "DMRC"})
    assert r["amount"] == 100.0 and r["category"] == "transport"
    items = mcp_client.call("get_transactions", {"category": "transport"})["items"]
    assert any(t["id"] == r["id"] and t["merchant"] == "DMRC" for t in items)
    assert user.get(f"/transactions/{r['id']}").json()["description"] == "Metro"


def test_protocol_error_handling(mcp_client, user):
    assert "Insufficient balance" in mcp_client.call("add_transaction", {"account_id": user.acct["id"], "amount": 10 ** 6, "transaction_type": "debit", "category": "food", "description": "x", "transaction_date": TODAY.isoformat()})["error"]
    assert "error" in mcp_client.call("add_transaction", {"account_id": user.acct["id"], "amount": 5, "transaction_type": "expense", "category": "food", "description": "x", "transaction_date": TODAY.isoformat()})
    assert "error" in mcp_client.call("get_account_summary", {"account_id": 99999})
    assert "error" in mcp_client.call("get_account_summary", {"account_id": "not-an-int"})  # schema validation at the protocol layer
    assert "error" in mcp_client.call("get_account_summary", {})  # missing required argument
    assert "error" in mcp_client.call("no_such_tool", {})
    assert "accounts" in mcp_client.call("get_accounts")  # server still healthy


def test_protocol_multiple_and_concurrent_calls(mcp_client):
    results = []

    def worker():
        results.append(mcp_client.call("get_accounts"))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(results) == 6 and all("accounts" in r for r in results)
    for _ in range(5):
        assert "total_balance" in mcp_client.call("get_dashboard_summary")


def test_protocol_users_are_isolated_by_server_process(live_backend, user):
    other = live_backend.new_user()
    with McpToolClient(token=other.token, base_url=live_backend.base_url) as c:
        assert c.call("get_accounts")["accounts"] == []
        assert "Access denied" in c.call("get_account_summary", {"account_id": user.acct["id"]})["error"]
        assert c.call("get_dashboard_summary")["monthly_expenses"] == 0


def test_protocol_bad_token_and_unreachable_backend_are_reported(live_backend):
    with McpToolClient(token="garbage", base_url=live_backend.base_url) as c:
        assert "Not authenticated" in c.call("get_dashboard_summary")["error"]
    with McpToolClient(token="x", base_url="http://127.0.0.1:9/api/v1") as c:
        assert "unavailable" in c.call("get_accounts")["error"].lower()


def test_protocol_client_lifecycle(live_backend, user):
    c = McpToolClient(token=user.token, base_url=live_backend.base_url)
    assert c.call("get_accounts")["accounts"]  # lazy start on first call
    c.close()
    c.close()  # idempotent
    bad = McpToolClient(server_script="/nonexistent/server.py", startup_timeout=15)
    with pytest.raises(McpClientError):
        bad.start()
