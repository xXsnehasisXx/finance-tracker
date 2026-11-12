"""LangChain 1.0 migration verification (Matrix B). Offline & deterministic.

Exercises the spec's legacy APIs *functionally* (not just imports): RAG (RetrievalQA + LCEL), @tool string invocation as
the Phase 3 tests do it, tool-calling + ReAct agents, summarizer, LangGraph Phase 5 pipeline, LangSmith/OTel hooks.
"""
import hashlib
import importlib
import json
import math
import os
import sys
import tempfile
import warnings
from typing import Any, Dict, List, TypedDict

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.pop("LANGCHAIN_API_KEY", None)
HERE = os.path.dirname(os.path.abspath(__file__))
res = []
caught_warnings = []


def ok(name, cond, detail=""):
    res.append((name, "PASS" if cond else "FAIL", str(detail)[:170]))


def guard(name):
    def deco(fn):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                d = fn()
                ok(name, True, d or "")
            except Exception as e:  # noqa: BLE001
                ok(name, False, f"{type(e).__name__}: {e}")
            for x in w:
                if "deprecat" in str(x.category).lower() or "deprecat" in str(x.message).lower():
                    caught_warnings.append((name, str(x.message)[:140]))
        return fn
    return deco


from langchain_core.documents import Document  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402
from langchain_core.language_models.fake_chat_models import FakeListChatModel  # noqa: E402


class HashEmbeddings(Embeddings):
    def _vec(self, text):
        v = [0.0] * 256
        for w in text.lower().replace(".", " ").replace("?", " ").split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 256] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


# ------------------------------------------------------------------ 1. legacy import map
LEGACY = [
    ("from langchain.prompts import PromptTemplate", "langchain.prompts", "PromptTemplate", "langchain_core.prompts"),
    ("from langchain.tools import tool", "langchain.tools", "tool", "langchain.tools still exports it; prefer langchain_core.tools"),
    ("from langchain.text_splitter import RecursiveCharacterTextSplitter", "langchain.text_splitter", "RecursiveCharacterTextSplitter", "langchain_text_splitters"),
    ("from langchain.docstore.document import Document", "langchain.docstore.document", "Document", "langchain_core.documents"),
    ("from langchain.chains import RetrievalQA", "langchain.chains", "RetrievalQA", "langchain_classic.chains (or LCEL)"),
    ("from langchain.chains.summarize import load_summarize_chain", "langchain.chains.summarize", "load_summarize_chain", "langchain_classic.chains.summarize"),
    ("from langchain.agents import AgentExecutor", "langchain.agents", "AgentExecutor", "langchain_classic.agents"),
    ("from langchain.agents import create_react_agent", "langchain.agents", "create_react_agent", "langchain_classic.agents"),
    ("from langchain_community.vectorstores import Chroma", "langchain_community.vectorstores", "Chroma", "unchanged (kept; langchain-chroma needs chromadb>=1)"),
    ("from langchain_community.document_loaders import TextLoader", "langchain_community.document_loaders", "TextLoader", "unchanged"),
    ("from langchain_core.runnables import RunnableConfig", "langchain_core.runnables", "RunnableConfig", "unchanged"),
    ("from langchain_google_genai import ChatGoogleGenerativeAI", "langchain_google_genai", "ChatGoogleGenerativeAI", "unchanged"),
    ("from langchain_google_genai import GoogleGenerativeAIEmbeddings", "langchain_google_genai", "GoogleGenerativeAIEmbeddings", "unchanged"),
    ("from langgraph.graph import StateGraph, END", "langgraph.graph", "END", "unchanged"),
    ("from langsmith import traceable", "langsmith", "traceable", "unchanged"),
]
print("LEGACY IMPORT MAP")
for stmt, mod, attr, repl in LEGACY:
    try:
        getattr(importlib.import_module(mod), attr)
        st = "works as-is"
    except Exception as e:  # noqa: BLE001
        st = f"BROKEN ({type(e).__name__})"
    print(f"  {st:<26} {stmt}  ->  {repl}")


@guard("replacement imports all resolve")
def _():
    from langchain_core.prompts import PromptTemplate  # noqa: F401
    from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: F401
    from langchain_classic.chains import RetrievalQA  # noqa: F401
    from langchain_classic.chains.summarize import load_summarize_chain  # noqa: F401
    from langchain_classic.agents import AgentExecutor, create_react_agent, create_tool_calling_agent  # noqa: F401


# ------------------------------------------------------------------ 2. RAG: spec path (TextLoader -> splitter -> Chroma -> RetrievalQA)
MANUAL = "\n\n".join(
    [f"Section {i}: Budget alerts fire at 80 percent warning_80 and at 100 percent exceeded for every category in the app. " * 3 for i in range(40)]
    + ["Account types supported are savings checking and credit. " * 4] * 4
)
VS = {}


@guard("RAG ingest: TextLoader -> RecursiveCharacterTextSplitter(512/50) -> community Chroma (persist) ")
def _():
    from langchain_community.document_loaders import TextLoader
    from langchain_community.vectorstores import Chroma
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    d = tempfile.mkdtemp()
    p = os.path.join(d, "user_manual.md")
    open(p, "w", encoding="utf-8").write(MANUAL)
    docs = TextLoader(p, encoding="utf-8").load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50, separators=["\n\n", "\n", ".", " "]).split_documents(docs)
    assert len(chunks) >= 20 and all(len(c.page_content) <= 600 for c in chunks), len(chunks)
    VS["vs"] = Chroma.from_documents(chunks, HashEmbeddings(), persist_directory=os.path.join(d, "chroma"), collection_name="finance_manual")
    return f"{len(chunks)} chunks, all <=600 chars"


@guard("RAG chain A (spec): RetrievalQA(stuff, return_source_documents) via langchain_classic.invoke({'query'})")
def _():
    from langchain_classic.chains import RetrievalQA
    from langchain_core.prompts import PromptTemplate
    prompt = PromptTemplate(template="Context:\n{context}\nQuestion: {question}\nAnswer:", input_variables=["context", "question"])
    chain = RetrievalQA.from_chain_type(llm=FakeListChatModel(responses=["Warnings fire at 80%."]), chain_type="stuff",
                                        retriever=VS["vs"].as_retriever(search_kwargs={"k": 4}), return_source_documents=True,
                                        chain_type_kwargs={"prompt": prompt})
    out = chain.invoke({"query": "When do budget alerts fire?"})
    assert out["result"] == "Warnings fire at 80%." and len(out["source_documents"]) == 4
    return "result + 4 source_documents"


@guard("RAG chain B (planned): LCEL retriever|prompt|llm returning answer+sources")
def _():
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda, RunnablePassthrough
    ret = VS["vs"].as_retriever(search_kwargs={"k": 4})
    prompt = ChatPromptTemplate.from_template("Context:\n{context}\nQuestion: {question}")
    gen = prompt | FakeListChatModel(responses=["grounded"]) | StrOutputParser()
    chain = RunnableLambda(lambda q: {"question": q, "docs": ret.invoke(q)}) | RunnablePassthrough.assign(
        answer=lambda x: gen.invoke({"context": "\n".join(d.page_content for d in x["docs"]), "question": x["question"]}))
    out = chain.invoke("account types?")
    assert out["answer"] == "grounded" and len(out["docs"]) == 4
    return "answer + 4 docs"


@guard("RAG: reopen persisted store with a new Chroma() object (spec RET tests pattern)")
def _():
    from langchain_community.vectorstores import Chroma
    d = VS["vs"]._persist_directory
    again = Chroma(persist_directory=d, embedding_function=HashEmbeddings(), collection_name="finance_manual")
    r = again.similarity_search("savings checking credit account types", k=4)
    assert len(r) == 4 and "Account types" in r[0].page_content
    return "reopened, relevant hit"


# ------------------------------------------------------------------ 3. @tool: Phase 3 tests invoke with bare strings
from langchain_core.tools import tool  # noqa: E402
from langchain.tools import tool as lc_tool  # noqa: E402,F401  (legacy path)

CALLS = []


@lc_tool
def get_dashboard_summary(input: str = "") -> str:
    """Use this when the user asks about their total balance, monthly income, monthly expenses, savings rate, or top spending categories. Returns the dashboard."""
    CALLS.append(("dash", input))
    return "dash ok"


@tool
def get_account_summary(account_id: str) -> str:
    """Use this when the user asks about a specific account's balance. Input: account ID as a string (e.g., '1')."""
    return f"Account {account_id} not found." if account_id == "99999" else f"acct {account_id}"


@tool
def get_transactions(input: str) -> str:
    """Use this when the user asks to see transactions. Input: a JSON string with optional filters like {"category": "food"}."""
    return json.dumps(json.loads(input))


@guard("@tool: .name/.description present, >=50 chars with 'use this'")
def _():
    for t in (get_dashboard_summary, get_account_summary, get_transactions):
        assert t.name and len(t.description) >= 50 and "use this" in t.description.lower()
    return get_account_summary.description[:50]


@guard("@tool: .invoke('') / .invoke('99999') / .invoke('{\"category\":\"food\"}') (exact Phase 3 test calls)")
def _():
    assert get_dashboard_summary.invoke("") == "dash ok"
    assert "not found" in get_account_summary.invoke("99999")
    assert json.loads(get_transactions.invoke('{"category": "food"}')) == {"category": "food"}


@guard("@tool: dict input and wrong shape handled (no TypeError for string input, TC-TOOL-04)")
def _():
    assert get_account_summary.invoke({"account_id": "7"}) == "acct 7"
    try:
        get_account_summary.invoke({})
        raise AssertionError("expected validation error")
    except AssertionError:
        raise
    except Exception as e:  # noqa: BLE001
        return type(e).__name__


# ------------------------------------------------------------------ 4. agents
from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # noqa: E402
from langchain_core.tools import ToolException  # noqa: E402


class ScriptedToolModel(BaseChatModel):
    """Emits scripted tool calls, then a final answer. Records messages it receives."""
    script: List[Any] = []
    seen: List[Any] = []
    step: int = 0

    @property
    def _llm_type(self):
        return "scripted"

    def bind_tools(self, tools, **kw):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kw):
        self.seen.append([type(m).__name__ for m in messages])
        item = self.script[min(self.step, len(self.script) - 1)]
        self.step += 1
        return ChatResult(generations=[ChatGeneration(message=item)])


def _agent(model, tools, **kw):
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
    prompt = ChatPromptTemplate.from_messages([("system", "finance assistant"), ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
    return AgentExecutor(agent=create_tool_calling_agent(model, tools, prompt), tools=tools, return_intermediate_steps=True, max_iterations=6, **kw)


@guard("agent: create_tool_calling_agent + AgentExecutor: compound query -> >=2 tool calls, intermediate_steps, .tools")
def _():
    m = ScriptedToolModel(script=[
        AIMessage(content="", tool_calls=[{"name": "get_dashboard_summary", "args": {"input": ""}, "id": "a"},
                                          {"name": "get_account_summary", "args": {"account_id": "1"}, "id": "b"}]),
        AIMessage(content="Savings rate fine."),
    ], seen=[])
    ex = _agent(m, [get_dashboard_summary, get_account_summary])
    out = ex.invoke({"input": "How am I doing?"})
    assert len(out["intermediate_steps"]) == 2 and out["output"] == "Savings rate fine."
    assert {t.name for t in ex.tools} == {"get_dashboard_summary", "get_account_summary"}
    assert m.seen[1][-1] == "ToolMessage", m.seen  # tool results are fed back on 2nd turn
    return "2 tool calls; tool results fed back"


@guard("agent: multi-turn tool loop (tool -> model -> tool -> final)")
def _():
    m = ScriptedToolModel(script=[
        AIMessage(content="", tool_calls=[{"name": "get_dashboard_summary", "args": {"input": ""}, "id": "a"}]),
        AIMessage(content="", tool_calls=[{"name": "get_account_summary", "args": {"account_id": "2"}, "id": "b"}]),
        AIMessage(content="done"),
    ], seen=[])
    out = _agent(m, [get_dashboard_summary, get_account_summary]).invoke({"input": "x"})
    assert len(out["intermediate_steps"]) == 2 and out["output"] == "done" and m.step == 3


@guard("agent: tool error handling -> returned to model as text, loop continues (handle_tool_error)")
def _():
    @tool
    def flaky(x: str) -> str:
        """Use this when testing failures of a tool call."""
        raise ToolException("Service unavailable")

    flaky.handle_tool_error = True

    m = ScriptedToolModel(script=[
        AIMessage(content="", tool_calls=[{"name": "flaky", "args": {"x": "1"}, "id": "a"}]),
        AIMessage(content="Sorry, the service is unavailable."),
    ], seen=[])
    out = _agent(m, [flaky]).invoke({"input": "x"})
    assert "unavailable" in out["intermediate_steps"][0][1].lower() and "Sorry" in out["output"]


@guard("agent: unknown tool name + max_iterations guard (no infinite loop)")
def _():
    m = ScriptedToolModel(script=[AIMessage(content="", tool_calls=[{"name": "get_dashboard_summary", "args": {"input": ""}, "id": "a"}])], seen=[])
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
    prompt = ChatPromptTemplate.from_messages([("system", "s"), ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
    ex = AgentExecutor(agent=create_tool_calling_agent(m, [get_dashboard_summary], prompt), tools=[get_dashboard_summary],
                       max_iterations=3, early_stopping_method="force", return_intermediate_steps=True)
    out = ex.invoke({"input": "loop"})
    assert len(out["intermediate_steps"]) == 3 and "stopped" in out["output"].lower()
    return out["output"][:60]


@guard("agent (spec Phase 3/4 style): create_react_agent + AgentExecutor still runs on langchain_classic")
def _():
    from langchain_classic.agents import AgentExecutor, create_react_agent
    from langchain_core.prompts import PromptTemplate
    prompt = PromptTemplate.from_template("Tools: {tools}\nNames: {tool_names}\nQuestion: {input}\nThought: {agent_scratchpad}")
    llm = FakeListChatModel(responses=["I know.\nFinal Answer: 42"])
    out = AgentExecutor(agent=create_react_agent(llm, [get_dashboard_summary], prompt), tools=[get_dashboard_summary],
                        return_intermediate_steps=True, handle_parsing_errors=True).invoke({"input": "q"})
    assert out["output"] == "42"


@guard("summarizer (spec): load_summarize_chain(stuff) .invoke on Documents (and legacy .run)")
def _():
    from langchain_classic.chains.summarize import load_summarize_chain
    chain = load_summarize_chain(FakeListChatModel(responses=["short summary", "short summary 2"]), chain_type="stuff")
    out = chain.invoke({"input_documents": [Document(page_content="x" * 3000)]})
    assert out["output_text"] == "short summary"
    legacy = chain.run([Document(page_content="y" * 3000)])
    return f"invoke ok; legacy run() -> {legacy!r}"


@guard("PromptTemplate renders system prompt with braces-free text (TC-CTX-04)")
def _():
    from langchain_core.prompts import PromptTemplate
    PromptTemplate.from_template("You are a finance assistant. {input}").format(input="hi")


# ------------------------------------------------------------------ 5. LangGraph 1.0 Phase 5 pipeline
class FinancialHealthState(TypedDict):
    user_id: int
    report_month: int
    report_year: int
    transactions: List[Dict[str, Any]]
    budget_data: List[Dict[str, Any]]
    dashboard_data: Dict[str, Any]
    spending_analysis: Dict[str, Any]
    budget_analysis: Dict[str, Any]
    savings_recommendations: List[str]
    final_report: str
    report_status: str
    errors: List[str]
    messages: List[str]


def init_state():
    return FinancialHealthState(user_id=1, report_month=6, report_year=2026, transactions=[], budget_data=[], dashboard_data={},
                                spending_analysis={}, budget_analysis={}, savings_recommendations=[], final_report="",
                                report_status="in_progress", errors=[], messages=[])


@guard("langgraph 1.0.10: spec graph (entry, conditional edge, linear edges, END) full run + error route")
def _():
    from langgraph.graph import END, StateGraph
    from langsmith import traceable

    @traceable(name="transaction_analyzer", project_name="AI-Readiness-POC-02-P5")
    def ta(s):
        return {**s, "spending_analysis": {"total_spent": 5000}, "messages": s["messages"] + ["Transaction Analyzer"]}

    def ba(s):
        return {**s, "budget_analysis": {"budget_health_score": 70}, "messages": s["messages"] + ["Budget Advisor"]}

    def so(s):
        return {**s, "savings_recommendations": ["r1"], "messages": s["messages"] + ["Savings Optimizer"]}

    def rg(s):
        return {**s, "final_report": "# Report", "report_status": "complete", "messages": s["messages"] + ["Report Generator"]}

    def route(s):
        return "report_generator" if (s["report_status"] == "error" or len(s["errors"]) > 2) else "budget_advisor"

    wf = StateGraph(FinancialHealthState)
    for n, f in (("transaction_analyzer", ta), ("budget_advisor", ba), ("savings_optimizer", so), ("report_generator", rg)):
        wf.add_node(n, f)
    wf.set_entry_point("transaction_analyzer")
    wf.add_conditional_edges("transaction_analyzer", route, {"budget_advisor": "budget_advisor", "report_generator": "report_generator"})
    wf.add_edge("budget_advisor", "savings_optimizer")
    wf.add_edge("savings_optimizer", "report_generator")
    wf.add_edge("report_generator", END)
    g = wf.compile()
    assert hasattr(g, "invoke")
    nodes = set(g.get_graph().nodes)
    assert {"transaction_analyzer", "budget_advisor", "savings_optimizer", "report_generator"} <= nodes, nodes
    s0 = init_state()
    out = g.invoke(s0)
    assert out["messages"] == ["Transaction Analyzer", "Budget Advisor", "Savings Optimizer", "Report Generator"]
    assert out["report_status"] == "complete" and s0["messages"] == [], "state mutated"
    s1 = {**init_state(), "errors": ["a", "b", "c"]}
    out2 = g.invoke(s1)
    assert out2["messages"] == ["Transaction Analyzer", "Report Generator"]
    edges = {(e.source, e.target) for e in g.get_graph().edges}
    assert ("__start__", "transaction_analyzer") in edges and ("report_generator", "__end__") in edges, edges
    return f"4 msgs; error route -> 2 msgs; entry/END edges present; has entry_point attr={hasattr(g, 'entry_point')}"


# ------------------------------------------------------------------ 6. observability hooks
@guard("langsmith: traceable(name, project_name) + Client.list_runs(project_name=...) signatures")
def _():
    import inspect
    from langsmith import Client, traceable
    assert "project_name" in inspect.signature(Client.list_runs).parameters

    @traceable(name="x", project_name="AI-Readiness-POC-02-P2", tags=["phase-2"], metadata={"poc_id": "POC-02"})
    def f(a):
        return a

    assert f(3) == 3


@guard("OpenTelemetry: manual ASGI-middleware http span + db.query/auth.validate spans on FastAPI 0.141 (console exporter)")
def _():
    import io
    import time
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    buf = io.StringIO()
    prov = TracerProvider()
    prov.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=buf)))
    tr = prov.get_tracer("poc-02")
    app = FastAPI()

    @app.middleware("http")
    async def http_span(request: Request, call_next):
        with tr.start_as_current_span("http.request") as sp:
            sp.set_attribute("http.method", request.method)
            sp.set_attribute("http.route", request.url.path)
            resp = await call_next(request)
            sp.set_attribute("http.status_code", resp.status_code)
            return resp

    @app.get("/h")
    def h():
        with tr.start_as_current_span("db.query") as s:
            s.set_attribute("poc_id", "POC-02")
        return {"ok": 1}

    assert TestClient(app).get("/h").status_code == 200
    out = buf.getvalue()
    assert "db.query" in out and "http.request" in out
    return "http.request + db.query spans"


@guard("INFO opentelemetry-instrumentation-fastapi 0.45b0 (transitive via chromadb) is NOT usable: needs pkg_resources")
def _():
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: F401
        return "importable (unexpected) -> could be used"
    except ModuleNotFoundError as e:
        return f"not importable as expected: {e} -> manual spans used instead"


w = max(len(n) for n, _, _ in res)
print("\nRESULTS")
for n, s, d in res:
    print(f"{s:5} {n:<{w}}  {d}")
print("\nDEPRECATION WARNINGS SEEN:", len(caught_warnings))
for n, m in caught_warnings[:8]:
    print("  -", n[:40], "|", m)
sys.exit(1 if any(s == "FAIL" for _, s, _ in res) else 0)
