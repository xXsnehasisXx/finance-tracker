"""Phase 4 chat layer — MOCK tier: scripted LLM; MCP tools run over the real stdio protocol against a real HTTP backend.
Proves the confirmation gate, read-back verification, per-user isolation and the spec interfaces. NOT a live-Gemini test.
"""
import datetime
import json
import os

import pytest
from langchain_core.messages import AIMessage
from testsupport.fakes import ScriptedChatModel

from mcp_server import chat_interface as chat
from mcp_server.chat_interface import (
    FAILURE_MESSAGE, MCP_TOOLS, NO_KEY_MESSAGE, build_executor, confirm_pending, is_cancellation, is_confirmation, new_session_id, process_message,
)
from mcp_server.mcp_client import McpToolClient

pytestmark = pytest.mark.mock

TODAY = datetime.date.today()
ISO = TODAY.isoformat()


def call(name, **args):
    return {"name": name, "args": args, "id": f"call_{name}"}


def turn(*calls):
    return AIMessage(content="", tool_calls=list(calls))


def scripted(*items):
    return ScriptedChatModel(script=list(items), calls=[])


@pytest.fixture
def env(live_backend):
    """A fresh user with one savings account (₹5,000) and a food budget; helper to build executors and read balances."""

    class Env:
        user = live_backend.new_user()
        acct = user.seed(balance=5000, food_spent=0, budget=2000)
        base = live_backend.base_url
        executors = []

        def executor(self, *items, session_id=None):
            llm = scripted(*items)
            ex = build_executor(llm=llm, token=self.user.token, base_url=self.base, session_id=session_id)
            self.executors.append(ex)
            self.llm = llm
            return ex

        def balance(self):
            return self.user.get(f"/accounts/{self.acct['id']}").json()["balance"]

        def txn_count(self):
            return self.user.get("/transactions").json()["total"]

    e = Env()
    yield e
    for ex in e.executors:
        ex.close()


GROCERY = dict(account_id=None, amount=500.0, transaction_type="debit", category="food", description="Groceries", transaction_date=ISO, merchant="BigBazaar")


def grocery(env, **over):
    return {**GROCERY, "account_id": env.acct["id"], **over}


# ---------------------------------------------------------------- spec interfaces (TC-02-P4-CHAT/INT)
def test_int_01_exactly_six_spec_mcp_tools():
    assert len(MCP_TOOLS) == 6 and {t.name for t in MCP_TOOLS} == {"add_transaction", "get_transactions", "get_budget_status", "get_dashboard_summary", "set_budget", "get_account_summary"}


def test_chat_01_executor_builds_without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    ex = build_executor()
    assert ex is not None and hasattr(ex, "invoke") and "get_accounts" in {t.name for t in ex.tools}
    ex.close()


def test_chat_03_session_id_is_8_alnum_chars():
    sid = new_session_id()
    assert len(sid) == 8 and sid.replace("-", "").isalnum()


def test_chat_02_05_message_processed_and_tool_calls_extracted(env):
    ex = env.executor(turn(call("get_dashboard_summary")), "Your balance is ₹5,000.", session_id="test-s-01")
    result = process_message("What is my financial dashboard?", "test-s-01", ex)
    assert isinstance(result, dict) and result["output"] == "Your balance is ₹5,000."
    action, observation = result["intermediate_steps"][0]
    assert action.tool == "get_dashboard_summary" and "total_assets" in observation and "5000" in observation


def test_chat_06_int_03_error_handled_and_correct_tool_for_budget(env, monkeypatch):
    ex = env.executor(turn(call("get_budget_status")), "Food: ₹0 of ₹2,000 used.")
    result = process_message("What is my food budget utilization?", "int-02", ex)
    assert [s[0].tool for s in result["intermediate_steps"]] == ["get_budget_status"] and '"category": "food"' in result["intermediate_steps"][0][1]
    monkeypatch.setenv("GOOGLE_API_KEY", "set")
    boom = env.executor(RuntimeError("down"))
    assert process_message("x", "test-session-err", boom)["output"] == FAILURE_MESSAGE
    monkeypatch.delenv("GOOGLE_API_KEY")
    assert process_message("x", "test-session-err", boom)["output"] == NO_KEY_MESSAGE
    assert process_message("   ", "s", boom)["output"] == "Please type a message."


def test_int_06_tool_chain_for_complex_query(env):
    ex = env.executor(turn(call("get_dashboard_summary"), call("get_budget_status")), "Summary done.")
    assert len(process_message("Show my dashboard summary and my budget status", "int-complex", ex)["intermediate_steps"]) == 2


def test_model_sees_todays_real_date_and_rules(env):
    ex = env.executor("ok")
    process_message("hi", "s", ex)
    first = env.llm.prompts[0]
    assert TODAY.strftime("%Y") in first and TODAY.strftime("%A") in first and "only PROPOSES the change" in first and "awaiting the user's confirmation: none" in first


# ---------------------------------------------------------------- the confirmation gate
def test_write_is_only_a_proposal_nothing_recorded_until_confirmed(env):
    ex = env.executor(turn(call("add_transaction", **grocery(env))), "I'll record ₹500 for groceries. Please confirm.")
    result = process_message("Add a ₹500 grocery expense for today", "s1", ex)
    assert "PENDING_CONFIRMATION" in result["intermediate_steps"][0][1]
    assert ex.pending.current is not None and "₹500.00" in ex.pending.current.summary and "HDFC Savings" in ex.pending.current.summary
    assert env.txn_count() == 0 and env.balance() == 5000.0  # nothing written yet


def test_yes_executes_via_mcp_and_reports_verified_result(env):
    ex = env.executor(turn(call("add_transaction", **grocery(env))), "Please confirm.")
    process_message("Add a ₹500 grocery expense for today", "s1", ex)
    out = process_message("yes", "s1", ex)
    assert out["confirmation"]["ok"] and out["confirmation"]["record"]["id"]
    assert "✅ Recorded expense" in out["output"] and "₹500.00" in out["output"] and "New balance of HDFC Savings: ₹4,500.00" in out["output"]
    assert env.txn_count() == 1 and env.balance() == 4500.0 and ex.pending.current is None
    assert process_message("yes", "s1", ex)["output"] != out["output"]  # second 'yes' goes to the model, not a second write
    assert env.txn_count() == 1


def test_cancel_discards_the_pending_write(env):
    ex = env.executor(turn(call("add_transaction", **grocery(env))), "Confirm?", "Fine.")
    process_message("Add ₹500 groceries", "s1", ex)
    out = process_message("no, cancel it", "s1", ex)
    assert ex.pending.current is not None  # "no, cancel it" is not an exact cancel phrase -> goes to the model
    out = process_message("cancel", "s1", ex)
    assert out["cancelled"] and ex.pending.current is None and env.txn_count() == 0 and env.balance() == 5000.0


def test_model_cannot_confirm_on_the_users_behalf(env):
    """Even if the model calls the write tool repeatedly and claims success, nothing is recorded without the user's confirmation."""
    ex = env.executor(turn(call("add_transaction", **grocery(env))), turn(call("add_transaction", **grocery(env))), "Done! I recorded it (confirmed).")
    process_message("Add ₹500 groceries, I confirm in advance", "s1", ex)
    assert env.txn_count() == 0 and env.balance() == 5000.0


def test_new_proposal_replaces_the_old_one(env):
    ex = env.executor(turn(call("add_transaction", **grocery(env, amount=100.0))), "ok", turn(call("add_transaction", **grocery(env, amount=700.0))), "ok")
    process_message("add 100", "s", ex)
    process_message("actually add 700", "s", ex)
    assert process_message("yes", "s", ex)["confirmation"]["ok"] and env.balance() == 4300.0 and env.txn_count() == 1


def test_confirm_without_pending_is_harmless(env):
    ex = env.executor("There is nothing to confirm.")
    assert confirm_pending(ex)["ok"] is False
    assert process_message("yes", "s", ex)["output"] == "There is nothing to confirm." and env.txn_count() == 0


@pytest.mark.parametrize("word", ["yes", "Yes!", "YES.", "y", "confirm", "go ahead", "Yes please", "ok"])
def test_confirmation_phrases(word):
    assert is_confirmation(word) and not is_cancellation(word)


@pytest.mark.parametrize("text", ["no", "Cancel", "stop", "never mind", "nope!"])
def test_cancellation_phrases(text):
    assert is_cancellation(text) and not is_confirmation(text)


@pytest.mark.parametrize("text", ["yes but make it 600", "add 500 more", "what is my balance", "I said yes earlier"])
def test_only_exact_phrases_trigger_the_gate(text):
    assert not is_confirmation(text) and not is_cancellation(text)


# ---------------------------------------------------------------- proposal validation (never reaches the user as a pending action)
def test_invalid_proposals_are_rejected_before_confirmation(env):
    cases = [grocery(env, category="groceries"), grocery(env, transaction_type="expense"), grocery(env, amount=0), grocery(env, transaction_date="today"),
             grocery(env, account_id=999999), grocery(env, amount=10 ** 6)]
    for args in cases:
        ex = env.executor(turn(call("add_transaction", **args)), "I couldn't do that.")
        result = process_message("add", "s", ex)
        obs = result["intermediate_steps"][0][1]
        assert "PENDING_CONFIRMATION" not in obs and ex.pending.current is None, args
    assert env.txn_count() == 0


def test_insufficient_balance_is_caught_at_proposal_and_at_confirmation(env):
    ex = env.executor(turn(call("add_transaction", **grocery(env, amount=4000.0))), "ok")
    process_message("add 4000", "s", ex)
    assert ex.pending.current is not None
    env.user.post("/transactions", {"account_id": env.acct["id"], "amount": 3000, "type": "debit", "category": "other", "description": "meanwhile", "transaction_date": ISO})
    out = process_message("yes", "s", ex)  # balance changed after the proposal: the backend still enforces the rule
    assert out["confirmation"]["ok"] is False and "Insufficient balance" in out["output"] and "❌ Not recorded" in out["output"]
    assert env.balance() == 2000.0


def test_confirmed_write_that_cannot_be_verified_is_not_reported_as_success(env, monkeypatch):
    ex = env.executor(turn(call("add_transaction", **grocery(env))), "ok")
    process_message("add", "s", ex)
    real = ex.client.call
    monkeypatch.setattr(ex.client, "call", lambda name, args=None, **k: {"items": []} if name == "get_transactions" else real(name, args, **k))
    out = process_message("yes", "s", ex)
    assert out["confirmation"]["ok"] is False and "could not verify" in out["output"] and "✅" not in out["output"]


def test_set_budget_flow_with_verification_and_duplicate_rejection(env):
    ex = env.executor(turn(call("set_budget", category="transport", monthly_limit=3000.0, month=TODAY.month, year=TODAY.year)), "Confirm?",
                      turn(call("set_budget", category="transport", monthly_limit=4000.0, month=TODAY.month, year=TODAY.year)), "Confirm?")
    process_message("Set a transport budget of 3000", "s", ex)
    assert env.user.get("/budgets", month=TODAY.month, year=TODAY.year).json().__len__() == 1  # only the pre-seeded food budget
    out = process_message("yes", "s", ex)
    assert "✅ Budget saved: transport" in out["output"] and "₹3,000.00" in out["output"]
    process_message("Set transport budget to 4000", "s", ex)
    dup = process_message("yes", "s", ex)
    assert dup["confirmation"]["ok"] is False and "already exists" in dup["output"]
    bad = env.executor(turn(call("set_budget", category="salary", monthly_limit=1.0, month=1, year=2026)), "no")
    assert "PENDING" not in process_message("budget for salary", "s", bad)["intermediate_steps"][0][1]


def test_tools_are_scoped_to_the_signed_in_user(live_backend, env):
    other = live_backend.new_user()
    ex = build_executor(llm=scripted(turn(call("get_account_summary", account_id=env.acct["id"])), "Not accessible."), token=other.token, base_url=live_backend.base_url)
    try:
        result = process_message("show account", "s", ex)
        assert "Access denied" in result["intermediate_steps"][0][1] and "5000" not in result["intermediate_steps"][0][1]
    finally:
        ex.close()


def test_logs_have_session_id_and_never_contain_the_token(env, capsys):
    ex = env.executor(turn(call("get_dashboard_summary")), "Done.", session_id="log-test-session")
    process_message("Show dashboard", "log-test-session", ex)
    out = capsys.readouterr().out
    rows = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    recv = next(r for r in rows if r.get("event") == "chat_message_received")
    done = next(r for r in rows if r.get("event") == "chat_message_processed")
    assert recv["session_id"] == "log-test-session" and recv["poc_id"] == "POC-02" and recv["phase"] == 4 and done["tool_calls"] == 1
    assert env.user.token not in out


def test_required_otel_spans_for_chat_and_mcp(env, monkeypatch):
    from contextlib import contextmanager

    names = []

    @contextmanager
    def rec(name, **kw):
        names.append(name)

        class S:
            def set_attribute(self, *a):
                pass

        yield S()

    for mod in (chat, ):
        monkeypatch.setattr(mod, "span", rec)
    import mcp_server.mcp_client as client_mod

    monkeypatch.setattr(client_mod, "span", rec)
    ex = env.executor(turn(call("get_dashboard_summary")), "ok")
    process_message("hi", "s", ex)
    assert {"chat.message", "mcp.call"} <= set(names)


# ---------------------------------------------------------------- Streamlit UI: sign in -> chat -> confirm card -> verified result
def test_streamlit_chat_confirm_flow(env, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("API_BASE_URL", env.base)
    llm = scripted(turn(call("add_transaction", **grocery(env))), "I'll add ₹500 to food. Please confirm below.")
    real_build = chat.build_executor
    monkeypatch.setattr(chat, "build_executor", lambda **k: real_build(llm=llm, **k))
    path = os.path.join(os.path.dirname(chat.__file__), "chat_interface.py")
    at = AppTest.from_file(path, default_timeout=90).run()
    try:
        assert any("Sign in" in i.value for i in at.info)
        at.sidebar.text_input[0].set_value(env.user.email)
        at.sidebar.text_input[1].set_value("testpass123")
        next(b for b in at.sidebar.button if b.label == "Sign in").click().run()
        assert at.session_state["token"] and len(at.session_state["session_id"]) == 8
        at.chat_input[0].set_value("Add a ₹500 grocery expense for today").run()
        assert not at.exception
        assert any("Please confirm" in w.value for w in at.warning) and env.txn_count() == 0
        next(b for b in at.button if b.label == "✅ Confirm").click().run()
        assert any("✅ Recorded expense" in m.value for m in at.markdown) and env.txn_count() == 1 and env.balance() == 4500.0
        assert not any("Please confirm" in w.value for w in at.warning)  # card gone after confirmation
        assert len(at.session_state["messages"]) == 3  # history persisted
    finally:
        if at.session_state["executor"] is not None:
            at.session_state["executor"].close()


def test_streamlit_cancel_button(env, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("API_BASE_URL", env.base)
    llm = scripted(turn(call("add_transaction", **grocery(env))), "Confirm?")
    real_build = chat.build_executor
    monkeypatch.setattr(chat, "build_executor", lambda **k: real_build(llm=llm, **k))
    at = AppTest.from_file(os.path.join(os.path.dirname(chat.__file__), "chat_interface.py"), default_timeout=90).run()
    try:
        at.sidebar.text_input[0].set_value(env.user.email)
        at.sidebar.text_input[1].set_value("testpass123")
        next(b for b in at.sidebar.button if b.label == "Sign in").click().run()
        at.chat_input[0].set_value("add 500 groceries").run()
        next(b for b in at.button if b.label == "✖ Cancel").click().run()
        assert env.txn_count() == 0 and any("cancelled" in m.value.lower() for m in at.markdown)
    finally:
        if at.session_state["executor"] is not None:
            at.session_state["executor"].close()
