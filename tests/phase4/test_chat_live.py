"""Phase 4 — LIVE tier: real Gemini + real MCP stdio + real HTTP backend. SKIPPED (not passed) without GOOGLE_API_KEY.

Run once a key exists:  GOOGLE_API_KEY=... pytest tests/phase4/test_chat_live.py -m live_gemini -v
"""
import datetime
import os
import time

import pytest

from mcp_server.chat_interface import build_executor, confirm_pending, process_message

pytestmark = pytest.mark.live_gemini

ISO = datetime.date.today().isoformat()


@pytest.fixture
def live(live_backend):
    user = live_backend.new_user()
    acct = user.seed(balance=5000, food_spent=800, budget=1000)
    ex = build_executor(token=user.token, base_url=live_backend.base_url, session_id="live-0001")
    yield user, acct, ex
    ex.close()


def test_live_natural_language_add_expense_proposes_then_records_after_confirmation(live):
    user, acct, ex = live
    before = user.get("/transactions").json()["total"]
    result = process_message("Add a ₹500 grocery expense for today", "live-0001", ex)
    action = ex.pending.current
    assert action is not None and action.args["amount"] == 500 and action.args["category"] == "food" and action.args["transaction_type"] == "debit"
    assert action.args["transaction_date"] == ISO and "confirm" in result["output"].lower()
    assert user.get("/transactions").json()["total"] == before  # nothing recorded before confirmation
    out = process_message("yes", "live-0001", ex)
    assert out["confirmation"]["ok"] and user.get("/transactions").json()["total"] == before + 1


def test_live_asks_for_missing_information_instead_of_guessing(live):
    user, acct, ex = live
    process_message("Add an expense", "live-0001", ex)
    assert ex.pending.current is None  # no amount given: it must ask, not invent one


def test_live_budget_question_uses_budget_tool(live):
    user, acct, ex = live
    result = process_message("How much have I spent on food this month?", "live-0001", ex)
    assert any(a.tool in ("get_budget_status", "get_dashboard_summary", "get_transactions") for a, _ in result["intermediate_steps"]) and "800" in result["output"]


def test_live_dashboard_summary(live):
    user, acct, ex = live
    result = process_message("Show my financial summary", "live-0001", ex)
    assert any(a.tool == "get_dashboard_summary" for a, _ in result["intermediate_steps"]) and "₹" in result["output"]


def test_live_cancel_flow_records_nothing(live):
    user, acct, ex = live
    before = user.get("/transactions").json()["total"]
    process_message("Add a ₹300 transport expense today", "live-0001", ex)
    assert process_message("cancel", "live-0001", ex).get("cancelled") and user.get("/transactions").json()["total"] == before


def test_live_multi_turn_context(live):
    user, acct, ex = live
    from langchain_core.messages import AIMessage, HumanMessage

    first = process_message("What is my food budget?", "live-0001", ex)
    history = [HumanMessage(content="What is my food budget?"), AIMessage(content=first["output"])]
    second = process_message("Am I close to exceeding it?", "live-0001", ex, chat_history=history)
    assert any(w in second["output"].lower() for w in ("80", "close", "800", "yes", "₹"))


@pytest.mark.live_langsmith
def test_live_langsmith_trace_has_session(live, ls_trace):
    user, acct, ex = live
    process_message("Show my financial dashboard", "obs-trace-002", ex)
    run = ls_trace.wait_for_run("AI-Readiness-POC-02-P4", "finance_chat_message")
    assert run.inputs.get("session_id") == "obs-trace-002"
