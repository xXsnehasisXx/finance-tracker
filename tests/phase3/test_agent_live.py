"""Phase 3 — LIVE tier: real Gemini tool calling against the real FastAPI app (in-process). SKIPPED without GOOGLE_API_KEY.

Run once a key exists:  GOOGLE_API_KEY=... pytest tests/phase3/test_agent_live.py -m live_gemini -v
"""
import os
import time

import pytest

from agent.agent import build_agent, run_agent

pytestmark = pytest.mark.live_gemini

BASE = "http://testserver/api/v1"


@pytest.fixture
def live_rag(tmp_path):
    from rag.ingest import ingest_manual
    from rag.rag_chain import build_rag_chain

    ingest_manual(persist_dir=str(tmp_path))
    return build_rag_chain(persist_dir=str(tmp_path))


def _run(question, api, rag=None):
    ex = build_agent(token=api.token, base_url=BASE, rag_chain=rag)
    result = run_agent(question, ex)
    assert "error" not in result, result
    return result, [s[0].tool for s in result["intermediate_steps"]]


def test_live_e2e_01_budget_status_query(finance_api):
    finance_api.seed_basic(spent_food=8500)
    result, tools = _run("Am I over budget on food this month?", finance_api)
    out = result["output"].lower()
    assert "get_budget_status" in tools and any(t in out for t in ("85", "8,500", "8500", "not over", "under", "close"))


def test_live_e2e_02_compound_query_uses_two_tools(finance_api, live_rag):
    finance_api.seed_basic()
    result, tools = _run("What is my savings rate and how is savings rate calculated?", finance_api, live_rag)
    assert len(tools) >= 2 and "search_finance_policy" in tools and ("get_dashboard_summary" in tools or "get_budget_status" in tools)


def test_live_e2e_03_policy_query_uses_rag_tool(finance_api, live_rag):
    result, tools = _run("What transaction categories are available?", finance_api, live_rag)
    assert "search_finance_policy" in tools and any(c in result["output"].lower() for c in ("food", "transport", "utilities"))


def test_live_e2e_04_dashboard_query(finance_api):
    finance_api.seed_basic()
    result, _ = _run("What is my total balance across all accounts?", finance_api)
    assert any(t in result["output"].lower() for t in ("balance", "₹", "121,500", "1,21,500"))


def test_live_e2e_05_ambiguous_query_does_not_error(finance_api):
    result, _ = _run("Tell me about my finances", finance_api)
    out = result["output"].lower()
    assert len(out) > 10 and "traceback" not in out and "exception" not in out


def test_live_tool_error_is_handled_by_the_model(finance_api):
    result, tools = _run("Show me the summary of account 99999.", finance_api)
    assert "get_account_summary" in tools and "not found" in result["output"].lower() or "couldn't" in result["output"].lower() or "no account" in result["output"].lower()


def test_live_does_not_invent_numbers_without_data(finance_api):
    result, _ = _run("How much did I spend on health this month?", finance_api)
    assert not any(ch.isdigit() and ch != "0" for ch in result["output"].replace("2026", "").replace("2025", "").replace("2027", "")) or "no " in result["output"].lower()


def test_live_cannot_write_data(finance_api):
    finance_api.seed_basic()
    before = finance_api.get("/transactions").json()["total"]
    _run("Add a ₹500 grocery expense for today", finance_api)
    assert finance_api.get("/transactions").json()["total"] == before


@pytest.mark.live_langsmith
def test_live_langsmith_trace_created(finance_api, ls_trace):
    _run("What is my total balance?", finance_api)
    run = ls_trace.wait_for_run("AI-Readiness-POC-02-P3", "finance_agent_query")
    assert run.inputs.get("question") == "What is my total balance?"
