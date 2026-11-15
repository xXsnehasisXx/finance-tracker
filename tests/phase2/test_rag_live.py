"""Phase 2 (RAG) — LIVE tier: real Gemini embeddings + chat. SKIPPED (not passed) without GOOGLE_API_KEY.

Run once a key exists:   GOOGLE_API_KEY=... pytest tests/phase2/test_rag_live.py -m live_gemini -v
"""
import os
import time

import pytest

from rag.ingest import COLLECTION_NAME, ingest_manual
from rag.rag_chain import NO_INFO, ask_question, build_rag_chain

pytestmark = pytest.mark.live_gemini


@pytest.fixture(scope="module")
def live_chain(tmp_path_factory):
    d = str(tmp_path_factory.mktemp("live_chroma"))
    assert ingest_manual(persist_dir=d) >= 20  # real embeddings (EMBEDDING_MODEL)
    return build_rag_chain(persist_dir=d)  # real chat model (GEMINI_MODEL)


def _ask(chain, q):
    r = ask_question(q, chain)
    assert "error" not in r, r
    return r


def test_live_budget_steps(live_chain):
    a = _ask(live_chain, "How do I set a monthly budget?")["answer"].lower()
    assert "budget" in a and any(w in a for w in ("category", "limit")) and len(a) > 30


def test_live_budget_alert_thresholds(live_chain):
    a = _ask(live_chain, "How do budget alerts work?")["answer"]
    assert "80" in a and "100" in a


def test_live_account_types_lists_all_three(live_chain):
    a = _ask(live_chain, "What account types are supported?")["answer"].lower()
    assert all(t in a for t in ("savings", "checking", "credit"))


def test_live_categories_lists_all_seven(live_chain):
    a = _ask(live_chain, "What transaction categories are available?")["answer"].lower()
    found = [c for c in ("food", "transport", "utilities", "entertainment", "health", "salary", "other") if c in a]
    assert len(found) >= 6, found


def test_live_savings_rate_formula(live_chain):
    a = _ask(live_chain, "How is the savings rate calculated?")["answer"].lower()
    assert "income" in a and ("expenses" in a or "expense" in a)


def test_live_out_of_scope_declined(live_chain):
    a = _ask(live_chain, "What is the stock market?")["answer"].lower()
    assert "don't have information" in a or NO_INFO.lower() in a or "do not have information" in a


def test_live_sources_returned_and_grounded(live_chain):
    r = _ask(live_chain, "How do budget alerts work?")
    assert len(r["source_details"]) == 4 and any("Section 8" in s["section"] for s in r["source_details"])


def test_live_does_not_invent_features(live_chain):
    a = _ask(live_chain, "Does the app have a dark mode and a mobile app?")["answer"].lower()
    assert "no dedicated mobile app" in a or "don't have information" in a or "web application only" in a


def test_live_latency_reasonable(live_chain):
    t0 = time.perf_counter()
    _ask(live_chain, "Can I have multiple accounts?")
    assert time.perf_counter() - t0 < 30


@pytest.mark.live_langsmith
def test_live_langsmith_trace_created(live_chain, ls_trace):
    ask_question("How do I set a monthly budget?", live_chain)
    run = ls_trace.wait_for_run("AI-Readiness-POC-02-P2", "finance_rag_query")
    assert run.inputs.get("question") == "How do I set a monthly budget?"
