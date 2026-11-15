"""Phase 5 — LIVE tier: real Gemini narratives inside the LangGraph pipeline, and real LangSmith traces.
Skipped (never counted as passed) without GOOGLE_API_KEY / LANGCHAIN_API_KEY.

Run once keys exist:  pytest tests/phase5/test_multi_agent_live.py -m "live_gemini or live_langsmith" -v
"""
import pytest

from multi_agent.graph import generate_financial_report
from test_multi_agent import BASE, M, Y, seed_month


@pytest.mark.live_gemini
def test_live_pipeline_with_gemini_narratives(finance_api):
    seed_month(finance_api, rent_card=6000)
    final = generate_financial_report(None, M, Y, token=finance_api.token, base_url=BASE)  # real Gemini via common.llm
    assert final["report_status"] == "complete" and len(final["messages"]) == 4
    assert "₹80,000.00" in final["final_report"] and final["final_report"].count("## ") >= 8
    # At least one Gemini narrative must have come back AND passed the grounding check (so Gemini really answered).
    assert "AI commentary" in final["final_report"]


@pytest.mark.live_langsmith
def test_live_pipeline_is_traced_in_langsmith(finance_api, ls_trace):
    seed_month(finance_api)
    final = generate_financial_report(None, M, Y, token=finance_api.token, base_url=BASE, use_llm=False)
    assert final["report_status"] == "complete"
    run = ls_trace.wait_for_run("AI-Readiness-POC-02-P5", "financial_health_report")
    children = ls_trace.child_names("AI-Readiness-POC-02-P5", run.trace_id)
    assert {"transaction_analyzer", "budget_advisor", "savings_optimizer", "report_generator"} <= children
