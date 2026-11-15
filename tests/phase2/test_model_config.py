"""Gemini model configuration: one source of truth (common.llm), stale ids cannot override it, and the vector store
refuses to be queried with a different embedding model than it was built with."""
import os
import re

import pytest
from testsupport.fakes import HashEmbeddings, ScriptedChatModel

from common import llm
from rag.ingest import ingest_manual
from rag.rag_chain import build_rag_chain

pytestmark = pytest.mark.mock
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_defaults_are_the_working_models(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    assert llm.chat_model_name() == "gemini-3.5-flash-lite" and llm.embedding_model_name() == "models/gemini-embedding-001"
    monkeypatch.setenv("GEMINI_MODEL", "")
    assert llm.chat_model_name() == "gemini-3.5-flash-lite"  # an empty .env entry does not override the default


def test_explicit_models_are_honoured(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")
    monkeypatch.setenv("EMBEDDING_MODEL", "models/custom-embed")
    assert llm.chat_model_name() == "gemini-custom" and llm.embedding_model_name() == "models/custom-embed"


@pytest.mark.parametrize("var,stale,expected", [
    ("EMBEDDING_MODEL", "models/text-embedding-004", "models/gemini-embedding-001"),
    ("GEMINI_MODEL", "gemini-3.6-flash", "gemini-3.5-flash-lite"),
])
def test_stale_env_values_cannot_override_the_default(monkeypatch, var, stale, expected):
    monkeypatch.setenv(var, stale)
    assert (llm.embedding_model_name() if var == "EMBEDDING_MODEL" else llm.chat_model_name()) == expected


def test_factories_pass_the_configured_ids(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key-for-construction-only")
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert llm.get_embeddings().model == "models/gemini-embedding-001"
    assert llm.get_chat_model().model.endswith("gemini-3.5-flash-lite")


def test_no_stale_model_id_in_active_code_or_config():
    stale = re.compile(r"text-embedding-004|gemini-3\.6-flash")
    allowed = {os.path.join("ai", "common", "llm.py"), os.path.join("tests", "phase2", "test_model_config.py")}  # the retired-id map / this test
    offenders = []
    for base in ("ai", "backend", "scripts", "tests", ".env.example", "conftest.py"):
        path = os.path.join(ROOT, base)
        files = [path] if os.path.isfile(path) else [os.path.join(d, f) for d, _, fs in os.walk(path) for f in fs if f.endswith((".py", ".sh", ".md", ".txt", ".env"))]
        for f in files:
            rel = os.path.relpath(f, ROOT)
            if rel in allowed or "__pycache__" in rel:
                continue
            if stale.search(open(f, encoding="utf-8", errors="ignore").read()):
                offenders.append(rel)
    assert offenders == []


def test_vector_store_records_embedding_model_and_rejects_a_mismatch(tmp_path):
    class OtherEmbeddings(HashEmbeddings):
        model = "models/some-other-embedding"

    ingest_manual(embeddings=HashEmbeddings(), persist_dir=str(tmp_path))
    llm_stub = ScriptedChatModel(script=["x"], calls=[])
    build_rag_chain(llm=llm_stub, embeddings=HashEmbeddings(), persist_dir=str(tmp_path))  # same model: fine
    with pytest.raises(RuntimeError, match="Re-run `python ai/rag/ingest.py`"):
        build_rag_chain(llm=llm_stub, embeddings=OtherEmbeddings(), persist_dir=str(tmp_path))
