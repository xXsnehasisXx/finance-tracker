"""Phase 5 — LIVE tier: real Gemini narratives inside the LangGraph pipeline. SKIPPED without GOOGLE_API_KEY
(LangSmith trace check additionally needs LANGCHAIN_API_KEY).

Run once keys exist:  GOOGLE_API_KEY=... pytest tests/phase5/test_multi_agent_live.py -m live_gemini -v
"""
import os

import pytest

from multi_agent.graph import generate_financial_report
from test_multi_agent import BASE, M, Y, seed_month

pytestmark = pytest.mark.live_gemini


def test_live_pipeline_with_gemini_narratives(finance_api):
    seed_month(finance_api, rent_card=6000)
    final = generate_financial_report(None, M, Y, token=finance_api.token, base_url=BASE)  # real Gemini via common.llm
    assert final["report_status"] == "complete" and len(final["messages"]) == 4
    assert "₹80,000.00" in final["final_report"] and final["final_report"].count("## ") >= 8
    # Narratives are optional (discarded if they contain ungrounded numbers) but the Gemini call must not have raised.
    assert not [e for e in final["errors"] if "gemini" in e.lower()]


@pytest.mark.live_langsmith
def test_live_pipeline_is_traced_in_langsmith(finance_api, monkeypatch):
    if not os.getenv("LANGCHAIN_API_KEY"):
        pytest.skip("LANGCHAIN_API_KEY not set")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    seed_month(finance_api)
    final = generate_financial_report(None, M, Y, token=finance_api.token, base_url=BASE)
    assert final["report_status"] == "complete"
