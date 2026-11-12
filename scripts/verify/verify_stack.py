"""Offline compatibility verification for the POC-02 dependency matrix (Python 3.13.1).

No network/LLM calls. Each check prints PASS/FAIL with detail.
"""
import asyncio
import os
import sys
import tempfile
import traceback

RESULTS = []


def check(name):
    def deco(fn):
        try:
            detail = fn()
            RESULTS.append((name, "PASS", detail or ""))
        except Exception as exc:  # noqa: BLE001
            RESULTS.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))
            traceback.print_exc(limit=3)
        return fn
    return deco


@check("python version")
def _():
    assert sys.version_info[:3] == (3, 13, 1), sys.version
    return sys.version.split()[0]


@check("imports: all required packages")
def _():
    import importlib
    mods = [
        "fastapi", "uvicorn", "sqlalchemy", "pydantic", "multipart", "jwt", "bcrypt", "structlog",
        "httpx", "requests", "dotenv", "langchain", "langchain_core", "langchain_community",
        "langchain_text_splitters", "langchain_google_genai", "langsmith", "chromadb", "langgraph",
        "langgraph.graph", "fastmcp", "mcp", "streamlit", "opentelemetry.sdk.trace",
    ]
    for m in mods:
        importlib.import_module(m)
    return f"{len(mods)} modules"


@check("langchain: AgentExecutor/create_tool_calling_agent/RetrievalQA/@tool importable")
def _():
    try:
        from langchain.agents import AgentExecutor, create_tool_calling_agent  # noqa: F401
        from langchain.chains import RetrievalQA  # noqa: F401
        from langchain.chains.summarize import load_summarize_chain  # noqa: F401
        where = "langchain"
    except ImportError:
        from langchain_classic.agents import AgentExecutor, create_tool_calling_agent  # noqa: F401
        from langchain_classic.chains import RetrievalQA  # noqa: F401
        from langchain_classic.chains.summarize import load_summarize_chain  # noqa: F401
        where = "langchain_classic"
    from langchain_core.tools import tool  # noqa: F401
    return where


@check("langchain_google_genai: classes build offline, bind_tools available")
def _():
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    from langchain_core.tools import tool

    @tool
    def ping(x: str) -> str:
        """Use this when you need to ping."""
        return x

    llm = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"), google_api_key="fake-key")
    llm.bind_tools([ping])
    GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key="fake-key")
    return "constructed (no network)"


@check("google proto: Part has thought_signature field (Gemini 3 function-calling need)")
def _():
    from google.ai import generativelanguage as gl
    fields = {f for f in gl.Part.meta.fields}
    import importlib.metadata as md
    ver = md.version("google-ai-generativelanguage")
    if "thought_signature" not in fields:
        raise AssertionError(f"google-ai-generativelanguage {ver}: Part fields={sorted(fields)}")
    return ver


@check("chromadb 0.5.7: persist, add, query, reset collection (numpy 2)")
def _():
    import chromadb
    import numpy as np
    d = tempfile.mkdtemp(dir=os.environ.get("SCRATCH", None))
    client = chromadb.PersistentClient(path=d)
    col = client.get_or_create_collection("finance_manual")
    emb = [np.random.rand(8).tolist() for _ in range(5)]
    col.add(ids=[str(i) for i in range(5)], embeddings=emb, documents=[f"doc {i}" for i in range(5)])
    res = col.query(query_embeddings=[emb[2]], n_results=4)
    assert len(res["ids"][0]) == 4 and res["ids"][0][0] == "2"
    client.delete_collection("finance_manual")
    assert col is not None
    return f"chromadb {chromadb.__version__}"


@check("langchain_community Chroma + text splitter + fake embeddings (retriever k=4)")
def _():
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import FakeEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
    text = ("Budget alerts fire at 80% and 100%.\n\n" * 60)
    chunks = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50).split_documents([Document(page_content=text)])
    assert all(len(c.page_content) <= 600 for c in chunks)
    d = tempfile.mkdtemp(dir=os.environ.get("SCRATCH", None))
    vs = Chroma.from_documents(chunks, FakeEmbeddings(size=16), persist_directory=d, collection_name="finance_manual")
    docs = vs.as_retriever(search_kwargs={"k": 4}).invoke("budget alert")
    assert len(docs) == 4
    return f"{len(chunks)} chunks"


@check("LCEL RAG chain with fake LLM (retriever -> prompt -> llm)")
def _():
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import FakeEmbeddings
    from langchain_core.documents import Document
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    d = tempfile.mkdtemp(dir=os.environ.get("SCRATCH", None))
    vs = Chroma.from_documents([Document(page_content="Savings rate formula")], FakeEmbeddings(size=8), persist_directory=d)
    prompt = ChatPromptTemplate.from_template("Context: {context}\nQ: {question}")
    chain = prompt | FakeListChatModel(responses=["grounded answer"]) | StrOutputParser()
    docs = vs.as_retriever().invoke("x")
    assert chain.invoke({"context": docs[0].page_content, "question": "q"}) == "grounded answer"


@check("tool-calling agent (fake tool-calling model) executes 2 tool calls + final answer")
def _():
    from typing import Any
    try:
        from langchain.agents import AgentExecutor, create_tool_calling_agent
    except ImportError:
        from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.tools import tool

    @tool
    def get_budget_status(input: str = "") -> str:
        """Use this when the user asks about budgets."""
        return "food 85% used"

    @tool
    def search_finance_policy(question: str) -> str:
        """Use this when the user asks how the app works."""
        return "80% warning"

    class FakeToolModel(BaseChatModel):
        step: int = 0

        @property
        def _llm_type(self) -> str:
            return "fake-tool"

        def bind_tools(self, tools: Any, **kw: Any):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kw):
            self.step += 1
            if self.step == 1:
                msg = AIMessage(content="", tool_calls=[
                    {"name": "get_budget_status", "args": {"input": ""}, "id": "c1"},
                    {"name": "search_finance_policy", "args": {"question": "alerts"}, "id": "c2"}])
            else:
                msg = AIMessage(content="You used 85% of food; warnings fire at 80%.")
            return ChatResult(generations=[ChatGeneration(message=msg)])

    tools = [get_budget_status, search_finance_policy]
    prompt = ChatPromptTemplate.from_messages([
        ("system", "finance assistant"), ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
    ex = AgentExecutor(agent=create_tool_calling_agent(FakeToolModel(), tools, prompt), tools=tools,
                       return_intermediate_steps=True, max_iterations=6)
    out = ex.invoke({"input": "Am I over budget on food?"})
    assert len(out["intermediate_steps"]) == 2 and "85%" in out["output"]
    assert {t.name for t in ex.tools} == {"get_budget_status", "search_finance_policy"}


@check("langgraph: StateGraph + conditional edges + END, state not mutated")
def _():
    from typing import Any, Dict, List, TypedDict
    from langgraph.graph import END, StateGraph

    class S(TypedDict):
        errors: List[str]
        messages: List[str]
        data: Dict[str, Any]

    def a(s):
        return {**s, "messages": s["messages"] + ["a"]}

    def b(s):
        return {**s, "messages": s["messages"] + ["b"]}

    def c(s):
        return {**s, "messages": s["messages"] + ["c"]}

    def route(s):
        return "c" if len(s["errors"]) > 2 else "b"

    g = StateGraph(S)
    for n, f in (("a", a), ("b", b), ("c", c)):
        g.add_node(n, f)
    g.set_entry_point("a")
    g.add_conditional_edges("a", route, {"b": "b", "c": "c"})
    g.add_edge("b", "c")
    g.add_edge("c", END)
    app = g.compile()
    init = {"errors": [], "messages": [], "data": {}}
    out = app.invoke(init)
    assert out["messages"] == ["a", "b", "c"] and init["messages"] == []
    out2 = app.invoke({"errors": ["1", "2", "3"], "messages": [], "data": {}})
    assert out2["messages"] == ["a", "c"]
    assert set(app.get_graph().nodes) >= {"a", "b", "c"}


@check("fastmcp 0.4.1 + mcp 1.30: register tools, list, call over real MCP in-memory session")
def _():
    from fastmcp import FastMCP
    import importlib.metadata as md
    mcp = FastMCP("Finance Tracker MCP Server")

    @mcp.tool()
    def add(a: int, b: int) -> dict:
        """Add numbers."""
        return {"sum": a + b}

    @mcp.tool()
    def boom() -> dict:
        """Always errors."""
        raise ValueError("bad")

    assert callable(add) and add(1, 2) == {"sum": 3}, "decorated function no longer plain-callable"
    assert hasattr(mcp, "run")

    async def go():
        from mcp.shared.memory import create_connected_server_and_client_session
        server = getattr(mcp, "_mcp_server", None)
        async with create_connected_server_and_client_session(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            res = await client.call_tool("add", {"a": 2, "b": 3})
            err = await client.call_tool("boom", {})
            return names, res, err

    names, res, err = asyncio.run(go())
    assert names == {"add", "boom"}, names
    assert "5" in res.content[0].text, res
    return f"fastmcp {md.version('fastmcp')} / mcp {md.version('mcp')}; isError(boom)={err.isError}"


@check("opentelemetry-sdk 1.24: console exporter span with attributes")
def _():
    import io
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    buf = io.StringIO()
    p = TracerProvider()
    p.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=buf)))
    t = p.get_tracer("poc-02-rag")
    with t.start_as_current_span("rag.retrieve") as s:
        s.set_attribute("poc_id", "POC-02")
    assert "rag.retrieve" in buf.getvalue()


@check("langsmith @traceable works with tracing disabled (no key) ")
def _():
    os.environ.pop("LANGCHAIN_API_KEY", None)
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    from langsmith import traceable

    @traceable(name="x", project_name="AI-Readiness-POC-02-P2")
    def f(a):
        return a + 1

    assert f(1) == 2


@check("streamlit 1.36: AppTest chat page runs with session_state")
def _():
    from streamlit.testing.v1 import AppTest
    src = (
        "import streamlit as st\n"
        "if 'messages' not in st.session_state: st.session_state.messages=[]\n"
        "if p := st.chat_input('Ask'):\n"
        "    st.session_state.messages.append(p)\n"
        "st.write(len(st.session_state.messages))\n"
    )
    at = AppTest.from_string(src).run(timeout=30)
    assert not at.exception
    at.chat_input[0].set_value("hello").run(timeout=30)
    assert not at.exception


@check("structlog JSON logging + FastAPI TestClient(httpx 0.28) + SQLAlchemy 2 + bcrypt + PyJWT")
def _():
    import datetime
    import bcrypt
    import jwt
    import structlog
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text

    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    structlog.get_logger().info("x", poc_id="POC-02")
    app = FastAPI()

    @app.get("/h")
    def h():
        return {"ok": True}

    assert TestClient(app).get("/h").json() == {"ok": True}
    e = create_engine("sqlite://")
    with e.connect() as c:
        assert c.execute(text("select 1")).scalar() == 1
        assert c.execute(text("select strftime('%Y','2026-06-01')")).scalar() == "2026"
    assert bcrypt.checkpw(b"pw", bcrypt.hashpw(b"pw", bcrypt.gensalt()))
    tok = jwt.encode({"sub": "1", "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=24)}, "k" * 32, algorithm="HS256")
    assert jwt.decode(tok, "k" * 32, algorithms=["HS256"])["sub"] == "1"


w = max(len(n) for n, _, _ in RESULTS)
for n, st, d in RESULTS:
    print(f"{st:5} {n:<{w}}  {d}")
sys.exit(1 if any(s == 'FAIL' for _, s, _ in RESULTS) else 0)
