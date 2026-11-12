"""Phase 2 (RAG) — MOCK tier: fake embeddings + scripted LLM. Proves wiring, retrieval, grounding prompt, logging, spans.
These tests do NOT verify real Gemini behaviour; see test_rag_live.py for that tier.
"""
import json
import os
import time

import pytest
import streamlit as st
from testsupport.fakes import HashEmbeddings, ScriptedChatModel

from common.llm import MissingApiKeyError
from rag import ingest as ingest_mod
from rag import rag_chain as chain_mod
from rag.ingest import COLLECTION_NAME, ingest_manual, load_and_split
from rag.rag_chain import EMPTY_QUESTION, LLM_UNAVAILABLE, NO_INFO, ask_question, build_rag_chain

pytestmark = pytest.mark.mock

MANUAL = os.path.join(os.path.dirname(ingest_mod.__file__), "user_manual.md")


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    d = str(tmp_path_factory.mktemp("chroma"))
    count = ingest_manual(embeddings=HashEmbeddings(), persist_dir=d)
    return {"dir": d, "count": count}


def make_chain(store, responses=("Grounded answer.",)):
    llm = ScriptedChatModel(script=list(responses), calls=[])
    return build_rag_chain(llm=llm, embeddings=HashEmbeddings(), persist_dir=store["dir"]), llm


# ---------------------------------------------------------------- ingestion (TC-02-P2-ING-*)
def test_ing_01_manual_loads_successfully():
    from langchain_community.document_loaders import TextLoader

    docs = TextLoader(MANUAL, encoding="utf-8").load()
    assert len(docs) > 0 and len(docs[0].page_content) > 1000
    assert docs[0].page_content.count("#### Section") == 16  # the 15 POC sections + transfers addendum


def test_ing_02_chunks_at_most_600_chars():
    assert all(len(c.page_content) <= 600 for c in load_and_split())


def test_ing_03_at_least_20_chunks():
    assert len(load_and_split()) >= 20


def test_ing_04_chromadb_stores_chunks(store):
    import chromadb

    col = chromadb.PersistentClient(path=store["dir"]).get_collection(COLLECTION_NAME)
    assert col.count() == store["count"] >= 20
    peek = col.peek(limit=1)
    assert len(peek["ids"]) > 0 and peek["documents"][0]


def test_ingest_resets_collection_no_duplicates(tmp_path):
    d = str(tmp_path)
    first = ingest_manual(embeddings=HashEmbeddings(), persist_dir=d)
    second = ingest_manual(embeddings=HashEmbeddings(), persist_dir=d)
    import chromadb

    assert first == second == chromadb.PersistentClient(path=d).get_collection(COLLECTION_NAME).count()


def test_chunks_carry_manual_section_metadata():
    chunks = load_and_split()
    sections = {c.metadata["section"] for c in chunks}
    assert "Section 7: Setting Monthly Budgets" in sections and "Section 2: Account Types" in sections
    assert all(c.metadata["source"] == "user_manual.md" for c in chunks)
    budget_chunk = next(c for c in chunks if "Budget rules" in c.page_content)
    assert budget_chunk.metadata["section"] == "Section 7: Setting Monthly Budgets"


def test_manual_documents_transfers_and_net_balance():
    text = open(MANUAL, encoding="utf-8").read()
    assert "Transfers and Credit Card Payments" in text and "net balance" in text


def test_ingest_logs_chunk_count(tmp_path, capsys):
    n = ingest_manual(embeddings=HashEmbeddings(), persist_dir=str(tmp_path))
    entry = next(e for e in _log_lines(capsys.readouterr().out) if e.get("event") == "manual_ingested")
    assert entry["chunk_count"] == n and entry["collection_name"] == COLLECTION_NAME and entry["poc_id"] == "POC-02" and entry["phase"] == 2


# ---------------------------------------------------------------- retrieval (TC-02-P2-RET-*)
def test_ret_01_budget_question_returns_budget_content(store):
    chain, _ = make_chain(store)
    combined = " ".join(d.page_content.lower() for d in chain.retrieve("How do I set a monthly budget?"))
    assert "budget" in combined and any(t in combined for t in ("category", "monthly", "limit", "spending"))


def test_ret_02_top_k_is_exactly_4(store):
    chain, _ = make_chain(store)
    assert len(chain.retrieve("budget alerts at 80 percent")) == 4


def test_ret_03_irrelevant_query_scores_worse_than_relevant(store):
    from langchain_community.vectorstores import Chroma

    vs = Chroma(persist_directory=store["dir"], embedding_function=HashEmbeddings(), collection_name=COLLECTION_NAME)
    relevant = vs.similarity_search_with_score("How do I set a monthly budget?", k=4)[0][1]
    off_topic = vs.similarity_search_with_score("pasta recipe cooking instructions", k=4)[0][1]
    assert off_topic > relevant  # chroma returns distances: larger = less similar


def test_ret_04_account_types_query_retrieves_account_section(store):
    chain, _ = make_chain(store)
    docs = chain.retrieve("what types of accounts are supported?")
    assert any("savings" in d.page_content.lower() and "checking" in d.page_content.lower() for d in docs)


def test_ret_05_empty_query_handled_gracefully(store):
    chain, llm = make_chain(store)
    for q in ("", "   ", None):
        r = ask_question(q, chain)
        assert r["answer"] == EMPTY_QUESTION and r["sources"] == []
    assert llm.calls == []  # no LLM call for empty input


def test_ret_06_retrieval_latency_under_5_seconds(store):
    chain, _ = make_chain(store)
    t0 = time.perf_counter()
    chain.retrieve("budget alerts 80 percent")
    assert time.perf_counter() - t0 < 5.0


# ---------------------------------------------------------------- generation (wiring; real model quality is LIVE tier)
def test_gen_answer_is_non_empty_string_and_prompt_is_grounded(store):
    chain, llm = make_chain(store, ["Navigate to Budgets and click Set Budget."])
    r = ask_question("How do I set a monthly budget?", chain)
    assert isinstance(r["answer"], str) and r["answer"] == "Navigate to Budgets and click Set Budget."
    prompt = llm.prompts[0]
    assert "ONLY the information provided in the context" in prompt and NO_INFO in prompt
    assert "How do I set a monthly budget?" in prompt and "Section 7: Setting Monthly Budgets" in prompt
    assert "Do NOT make up information" in prompt


def test_gen_no_retrieved_context_declines_without_calling_llm(store):
    chain, llm = make_chain(store)
    chain.retriever = type("EmptyRetriever", (), {"invoke": lambda self, q: []})()
    r = ask_question("What is the stock market?", chain)
    assert r["answer"] == NO_INFO and r["sources"] == [] and llm.calls == []


def test_gen_handles_gemini_content_blocks(store):
    blocks = [{"type": "thinking", "thinking": "hidden"}, {"type": "text", "text": "Visible answer."}]
    from langchain_core.messages import AIMessage

    chain, _ = make_chain(store, [AIMessage(content=blocks)])
    assert ask_question("budget?", chain)["answer"] == "Visible answer."


def test_gen_llm_failure_is_handled_and_logged(store, capsys):
    chain, _ = make_chain(store, [RuntimeError("boom")])
    r = ask_question("How do I set a budget?", chain)
    assert r["answer"] == LLM_UNAVAILABLE and r["error"] == "RuntimeError" and r["sources"] == []
    entry = next(e for e in _log_lines(capsys.readouterr().out) if e.get("event") == "llm_call_failed")
    assert entry["error_type"] == "RuntimeError" and entry["poc_id"] == "POC-02" and entry["phase"] == 2 and entry["level"] == "error"
    assert "boom" not in json.dumps(entry)  # no raw exception text in logs


def test_missing_api_key_gives_clear_error(store, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError, match="GOOGLE_API_KEY"):
        build_rag_chain(persist_dir=store["dir"])


def test_empty_knowledge_base_gives_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="ingest"):
        build_rag_chain(llm=ScriptedChatModel(script=["x"], calls=[]), embeddings=HashEmbeddings(), persist_dir=str(tmp_path / "empty"))


# ---------------------------------------------------------------- observability (TC-02-P2-OBS-*)
def _log_lines(out):
    lines = []
    for line in out.splitlines():
        try:
            lines.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return lines


def test_obs_03_structured_log_fields(store, capsys):
    chain, _ = make_chain(store)
    ask_question("What are the transaction categories?", chain)
    entry = next(e for e in _log_lines(capsys.readouterr().out) if e.get("event") == "rag_query_completed")
    assert entry["poc_id"] == "POC-02" and entry["phase"] == 2
    assert entry["answer_length"] > 0 and entry["source_count"] == 4 and "duration_ms" in entry


def test_obs_02_required_otel_spans_present(store, monkeypatch, tmp_path):
    names = []
    from contextlib import contextmanager

    @contextmanager
    def recording_span(name, **attrs):
        names.append(name)

        class S:
            def set_attribute(self, *a):
                pass

        yield S()

    monkeypatch.setattr(ingest_mod, "span", recording_span)
    monkeypatch.setattr(chain_mod, "span", recording_span)
    ingest_manual(embeddings=HashEmbeddings(), persist_dir=str(tmp_path))
    chain, _ = make_chain(store)
    ask_question("budget alerts", chain)
    assert {"rag.document_load", "rag.chunk", "rag.embed", "rag.retrieve", "rag.generate"} <= set(names)


def test_obs_04_source_documents_returned(store):
    chain, _ = make_chain(store)
    r = ask_question("How do budget alerts work?", chain)
    assert isinstance(r["sources"], list) and len(r["sources"]) == 4
    assert all(isinstance(s, str) and s for s in r["sources"])
    assert all(d["section"].startswith(("Section", "Introduction")) and d["snippet"] for d in r["source_details"])


def test_tracing_disabled_without_langsmith_key(store):
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"
    chain, _ = make_chain(store)
    assert ask_question("budget", chain)["answer"]  # @traceable is a harmless no-op


# ---------------------------------------------------------------- Streamlit chatbot (mock chain)
def test_chatbot_ui_shows_history_answer_and_sources(store, monkeypatch):
    from streamlit.testing.v1 import AppTest

    st.cache_resource.clear()
    monkeypatch.setattr(chain_mod, "build_rag_chain", lambda *a, **k: make_chain(store, ["Use Budgets > Set Budget."])[0])
    path = os.path.join(os.path.dirname(ingest_mod.__file__), "chatbot.py")
    at = AppTest.from_file(path, default_timeout=60).run()
    assert not at.exception
    at.chat_input[0].set_value("How do I set a monthly budget?").run()
    assert not at.exception
    texts = [m.value for m in at.markdown]
    assert any("Use Budgets > Set Budget." in t for t in texts)
    at.chat_input[0].set_value("What account types exist?").run()
    assert len(at.session_state["messages"]) == 4  # history persists across turns
    assert at.expander  # sources expander rendered


def test_chatbot_ui_shows_clear_error_without_api_key(monkeypatch):
    from streamlit.testing.v1 import AppTest

    st.cache_resource.clear()
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    path = os.path.join(os.path.dirname(ingest_mod.__file__), "chatbot.py")
    at = AppTest.from_file(path, default_timeout=60).run()
    assert not at.exception and any("GOOGLE_API_KEY" in e.value for e in at.error)
