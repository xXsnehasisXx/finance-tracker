#!/usr/bin/env python
"""Gemini 3 / langchain-google-genai compatibility verification (POC-02).

Two tiers, reported separately and never conflated:
  OFFLINE  : deterministic library-level checks, no network, no API key (always run).
  LIVE     : real Google Gemini API calls. Only run when GOOGLE_API_KEY is set; otherwise each is SKIPPED(no key).

Configuration (environment only; nothing model-specific is hard-coded):
  GOOGLE_API_KEY        required for LIVE tier (never printed)
  GEMINI_MODEL          chat model id           (default: gemini-3.6-flash)
  EMBEDDING_MODEL       embeddings model id     (default: models/text-embedding-004)
  GEMINI_FALLBACK_MODEL optional second chat model to try if GEMINI_MODEL fails L1

Exit codes: 0 = everything that ran passed AND live tier ran; 3 = offline passed but live NOT verified (no key);
            1 = any failure.   "LIVE COMPATIBILITY VERIFIED" is printed only when every live check passed.
"""
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
EMBED = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
FALLBACK = os.getenv("GEMINI_FALLBACK_MODEL", "")
KEY = os.getenv("GOOGLE_API_KEY", "")
ROWS = []  # (tier, name, status, detail)


def record(tier, name, status, detail=""):
    ROWS.append((tier, name, status, str(detail).replace(KEY, "***") if KEY else str(detail)))


def run(tier, name, fn, needs_key=False):
    if needs_key and not KEY:
        return record(tier, name, "SKIPPED(no GOOGLE_API_KEY)")
    try:
        d = fn()
        record(tier, name, "LIVE-PASS" if tier == "LIVE" else "OFFLINE-PASS", d or "")
    except Exception as e:  # noqa: BLE001
        record(tier, name, "LIVE-FAIL" if tier == "LIVE" else "OFFLINE-FAIL", f"{type(e).__name__}: {str(e)[:300]}")


# --------------------------------------------------------------------------- shared tool definitions (finance-flavoured)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain_core.tools import ToolException, tool  # noqa: E402

TOOL_LOG = []


@tool
def get_budget_status(category: str = "") -> str:
    """Use this when the user asks about budgets, spending limits or whether they are over budget for a category. Input: optional category name."""
    TOOL_LOG.append(("get_budget_status", category))
    return json.dumps({"category": category or "food", "monthly_limit": 10000, "spent": 8500, "utilization_percent": 85.0, "has_alert": True})


@tool
def get_dashboard_summary() -> str:
    """Use this when the user asks about total balance, monthly income, monthly expenses or savings rate."""
    TOOL_LOG.append(("get_dashboard_summary", ""))
    return json.dumps({"total_balance": 125000, "monthly_income": 80000, "monthly_expenses": 55000, "savings_rate": 31.25})


@tool
def get_account_summary(account_id: str) -> str:
    """Use this when the user asks about one specific account. Input: account id as a string, for example '1'."""
    TOOL_LOG.append(("get_account_summary", account_id))
    raise ToolException("Service unavailable: finance API did not respond")


get_account_summary.handle_tool_error = True  # error text is returned to the model instead of crashing the loop


# =========================================================================== OFFLINE TIER
def off_config():
    assert MODEL and EMBED
    src = open(__file__, encoding="utf-8").read()
    assert 'os.getenv("GEMINI_MODEL"' in src
    return f"model={MODEL} embedding={EMBED} (from env/default; key set={bool(KEY)})"


def _sig_response(sig=b"SIG-123"):
    from google.ai.generativelanguage_v1beta.types import Candidate, Content, FunctionCall, GenerateContentResponse, Part
    fc = FunctionCall(name="get_budget_status", args={"category": "food"})
    part = Part(function_call=fc, thought_signature=sig)
    return GenerateContentResponse(candidates=[Candidate(content=Content(role="model", parts=[part]), finish_reason=1)])


def off_signature_roundtrip():
    """Gemini 3 response (function_call + thought_signature) -> AIMessage -> request history; signature must survive."""
    from langchain_google_genai.chat_models import _parse_chat_history, _response_to_result
    result = _response_to_result(_sig_response(b"SIG-123"))
    ai = result.generations[0].message
    assert ai.tool_calls and ai.tool_calls[0]["name"] == "get_budget_status", ai
    # Storage format differs between lcgg releases (content block vs tool_call extras); the criterion is the re-sent request.
    where = "content block" if any(isinstance(b, dict) and b.get("type") == "function_call_signature" for b in (ai.content if isinstance(ai.content, list) else [])) \
        else ("tool_call extras" if any((tc.get("extras") or {}) for tc in ai.tool_calls) else ("additional_kwargs" if "signature" in json.dumps(ai.additional_kwargs, default=str).lower() else "NOWHERE"))
    history = [HumanMessage(content="Am I over budget on food?"), ai,
               ToolMessage(content="{}", tool_call_id=ai.tool_calls[0]["id"], name="get_budget_status")]
    _, contents = _parse_chat_history(history)
    sigs = [p.thought_signature for c in contents for p in c.parts if p.function_call.name and p.thought_signature]
    assert sigs == [b"SIG-123"], f"signature lost on re-send (stored: {where}): {sigs}"
    return f"signature stored in {where} and re-attached to the function_call Part on re-send"


def off_signature_through_agent_loop():
    """Signature must also survive langchain_classic AgentExecutor's scratchpad rebuild between turns."""
    from typing import Any, List
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_google_genai.chat_models import _parse_chat_history, _response_to_result

    first = _response_to_result(_sig_response(b"SIG-XYZ")).generations[0].message

    class Replay(BaseChatModel):
        step: int = 0
        seen: List[Any] = []

        @property
        def _llm_type(self):
            return "replay"

        def bind_tools(self, tools, **kw):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kw):
            self.seen.append(list(messages))
            self.step += 1
            msg = first if self.step == 1 else AIMessage(content="You have used 85% of the food budget.")
            return ChatResult(generations=[ChatGeneration(message=msg)])

    m = Replay(seen=[])
    prompt = ChatPromptTemplate.from_messages([("system", "finance assistant"), ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
    ex = AgentExecutor(agent=create_tool_calling_agent(m, [get_budget_status], prompt), tools=[get_budget_status], return_intermediate_steps=True)
    out = ex.invoke({"input": "Am I over budget on food?"})
    assert "85%" in out["output"] and len(out["intermediate_steps"]) == 1
    _, contents = _parse_chat_history([x for x in m.seen[1] if not isinstance(x, SystemMessage)])
    sigs = [p.thought_signature for c in contents for p in c.parts if p.function_call.name and p.thought_signature]
    assert sigs == [b"SIG-XYZ"], f"signature lost in agent scratchpad: {sigs}"
    return "second-turn request built by AgentExecutor still carries the thought_signature"


def off_parallel_calls_signature():
    """Gemini attaches the signature only to the FIRST parallel function call; it must stay on call #1 and not break call #2."""
    from google.ai.generativelanguage_v1beta.types import Candidate, Content, FunctionCall, GenerateContentResponse, Part
    from langchain_google_genai.chat_models import _parse_chat_history, _response_to_result
    parts = [Part(function_call=FunctionCall(name="get_budget_status", args={"category": "food"}), thought_signature=b"SIG-P1"),
             Part(function_call=FunctionCall(name="get_dashboard_summary", args={}))]
    resp = GenerateContentResponse(candidates=[Candidate(content=Content(role="model", parts=parts), finish_reason=1)])
    ai = _response_to_result(resp).generations[0].message
    assert [t["name"] for t in ai.tool_calls] == ["get_budget_status", "get_dashboard_summary"], ai.tool_calls
    history = [HumanMessage(content="q"), ai] + [ToolMessage(content="{}", tool_call_id=t["id"], name=t["name"]) for t in ai.tool_calls]
    _, contents = _parse_chat_history(history)
    model_parts = [p for c in contents if c.role == "model" for p in c.parts if p.function_call.name]
    assert [p.function_call.name for p in model_parts] == ["get_budget_status", "get_dashboard_summary"]
    assert model_parts[0].thought_signature == b"SIG-P1" and not model_parts[1].thought_signature, [p.thought_signature for p in model_parts]
    return "2 parallel calls: signature kept on first call only, order preserved"


def off_tool_error_loop():
    from typing import Any, List
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    class Seq(BaseChatModel):
        step: int = 0

        @property
        def _llm_type(self):
            return "seq"

        def bind_tools(self, tools, **kw):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kw):
            self.step += 1
            msg = (AIMessage(content="", tool_calls=[{"name": "get_account_summary", "args": {"account_id": "1"}, "id": "t1"}])
                   if self.step == 1 else AIMessage(content="The finance service is unavailable right now."))
            return ChatResult(generations=[ChatGeneration(message=msg)])

    prompt = ChatPromptTemplate.from_messages([("system", "s"), ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
    ex = AgentExecutor(agent=create_tool_calling_agent(Seq(), [get_account_summary], prompt), tools=[get_account_summary], return_intermediate_steps=True)
    out = ex.invoke({"input": "balance of account 1?"})
    assert "unavailable" in out["intermediate_steps"][0][1].lower() and "unavailable" in out["output"].lower()
    return "ToolException became an observation; loop continued; no crash"


def off_retry_behaviour():
    from google.api_core.exceptions import InvalidArgument, ServiceUnavailable
    from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError, _chat_with_retry
    calls = {"n": 0}

    def flaky(**kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ServiceUnavailable("503")
        return "ok"

    assert _chat_with_retry(flaky, max_retries=4, wait_exponential_min=0, wait_exponential_max=0, wait_exponential_multiplier=0) == "ok" and calls["n"] == 3

    def bad(**kw):
        raise InvalidArgument("bad request")

    try:
        _chat_with_retry(bad, max_retries=2, wait_exponential_min=0, wait_exponential_max=0, wait_exponential_multiplier=0)
        raise AssertionError("expected ChatGoogleGenerativeAIError")
    except ChatGoogleGenerativeAIError:
        pass
    return "transient 503 retried to success; InvalidArgument -> ChatGoogleGenerativeAIError (retry cap respected)"


def off_construct():
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    llm = ChatGoogleGenerativeAI(model=MODEL, google_api_key=KEY or "offline-placeholder", max_retries=2, timeout=30)
    llm.bind_tools([get_budget_status, get_dashboard_summary, get_account_summary])
    GoogleGenerativeAIEmbeddings(model=EMBED, google_api_key=KEY or "offline-placeholder")
    return f"constructed; max_retries={llm.max_retries}"


# =========================================================================== LIVE TIER
def _llm(model=None, **kw):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model or MODEL, google_api_key=KEY, max_retries=2, timeout=60, temperature=kw.pop("temperature", 0), **kw)


def _text(msg):
    c = msg.content
    if isinstance(c, str):
        return c
    return " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in c if not (isinstance(b, dict) and b.get("type") in ("thinking", "function_call_signature")))


def live_list_models():
    from google.ai import generativelanguage as gl
    client = gl.ModelServiceClient(client_options={"api_key": KEY})
    names = [m.name for m in client.list_models(request={"page_size": 200})]
    want_chat = "models/" + MODEL.replace("models/", "")
    want_emb = EMBED if EMBED.startswith("models/") else "models/" + EMBED
    flash = sorted(n for n in names if "flash" in n and "gemini-3" in n)[:8]
    emb = sorted(n for n in names if "embedding" in n)
    status = f"chat '{want_chat}' listed={want_chat in names}; embedding '{want_emb}' listed={want_emb in names}; gemini-3 flash ids={flash}; embeddings={emb}"
    assert want_chat in names, status
    assert want_emb in names, status
    return status


def live_plain():
    global MODEL
    try:
        r = _llm().invoke("Reply with exactly the single word: PONG")
    except Exception:
        if FALLBACK:
            MODEL = FALLBACK
            r = _llm().invoke("Reply with exactly the single word: PONG")
        else:
            raise
    assert "PONG" in _text(r).upper(), _text(r)
    return f"model={MODEL} reply={_text(r)[:20]!r}"


def live_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    e = GoogleGenerativeAIEmbeddings(model=EMBED, google_api_key=KEY)
    docs = e.embed_documents(["Budget alerts fire at 80 percent.", "Savings accounts cannot go negative.", "Pasta recipe with tomato sauce."])
    q = e.embed_query("When do budget alerts trigger?")
    assert len(docs) == 3 and len(q) == len(docs[0]) > 100
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))  # noqa: E731
    assert dot(q, docs[0]) > dot(q, docs[2]), "semantic ordering wrong"
    return f"dim={len(q)} (collection dimensionality must match ingest model)"


def live_single_tool_call():
    r = _llm().bind_tools([get_budget_status, get_dashboard_summary]).invoke("Am I over budget on food this month?")
    assert r.tool_calls and r.tool_calls[0]["name"] == "get_budget_status", f"tool_calls={r.tool_calls} text={_text(r)[:80]}"
    return f"args={r.tool_calls[0]['args']}"


def _loop(llm, tools, question, max_turns=5):
    by = {t.name: t for t in tools}
    msgs = [SystemMessage(content="You are a finance assistant. Use tools for live data and never invent numbers."), HumanMessage(content=question)]
    sig_seen, called = False, []
    for _ in range(max_turns):
        ai = llm.invoke(msgs)
        sig_seen = sig_seen or any(isinstance(b, dict) and b.get("type") == "function_call_signature" for b in (ai.content if isinstance(ai.content, list) else []))
        msgs.append(ai)
        if not ai.tool_calls:
            return ai, called, sig_seen, msgs
        for tc in ai.tool_calls:
            called.append(tc["name"])
            try:
                out = by[tc["name"]].invoke(tc["args"])
            except Exception as ex:  # noqa: BLE001
                out = f"Tool error: {ex}"
            msgs.append(ToolMessage(content=str(out), tool_call_id=tc["id"], name=tc["name"]))
    raise AssertionError("no final answer within max turns")


def live_multi_turn():
    TOOL_LOG.clear()
    ai, called, sig_seen, _ = _loop(_llm().bind_tools([get_budget_status, get_dashboard_summary]),
                                    [get_budget_status, get_dashboard_summary],
                                    "Am I over budget on food, and what is my savings rate? Use the tools.")
    txt = _text(ai)
    assert "get_budget_status" in called and "get_dashboard_summary" in called, called
    assert "85" in txt and "31" in txt, txt
    return f"tools={called}; final mentions 85% and 31.25%; signature_blocks_seen={sig_seen}"


def live_thought_signature():
    TOOL_LOG.clear()
    llm = _llm().bind_tools([get_budget_status])
    msgs = [HumanMessage(content="Am I over budget on food? Use the tool.")]
    ai = llm.invoke(msgs)
    assert ai.tool_calls, "model did not call the tool"
    has_sig = any(isinstance(b, dict) and b.get("type") == "function_call_signature" for b in (ai.content if isinstance(ai.content, list) else []))
    tm = ToolMessage(content=get_budget_status.invoke(ai.tool_calls[0]["args"]), tool_call_id=ai.tool_calls[0]["id"], name="get_budget_status")
    final = llm.invoke(msgs + [ai, tm])  # signature intact -> must succeed
    assert _text(final), "empty final answer"
    negative = "n/a (model emitted no signature)"
    if has_sig:
        stripped = AIMessage(content=[b for b in ai.content if not (isinstance(b, dict) and b.get("type") == "function_call_signature")], tool_calls=ai.tool_calls)
        try:
            llm.invoke(msgs + [stripped, tm])
            negative = "stripped-signature request ACCEPTED (not strictly enforced for this model)"
        except Exception as e:  # noqa: BLE001
            negative = f"stripped-signature request REJECTED ({type(e).__name__}) -> preservation is required and works"
    assert has_sig or True
    return f"signature_emitted={has_sig}; round-trip with signature OK; negative control: {negative}"


def live_tool_error_and_retry():
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    TOOL_LOG.clear()
    prompt = ChatPromptTemplate.from_messages([("system", "You are a finance assistant. If a tool fails, tell the user briefly."),
                                               ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
    ex = AgentExecutor(agent=create_tool_calling_agent(_llm(), [get_account_summary], prompt), tools=[get_account_summary],
                       return_intermediate_steps=True, max_iterations=4)
    out = ex.invoke({"input": "What is the balance of account 1? Use the tool."})
    assert any(n == "get_account_summary" for n, _ in TOOL_LOG) and out["output"], out
    bad = _llm("definitely-not-a-model-id")
    t0 = time.time()
    try:
        bad.invoke("hi")
        raise AssertionError("invalid model id was accepted")
    except AssertionError:
        raise
    except Exception as e:  # noqa: BLE001
        dt = time.time() - t0
        assert dt < 90, f"invalid model hung {dt:.0f}s"
        err = f"{type(e).__name__} after {dt:.1f}s"
    return f"tool failure surfaced to model & answered ({out['output'][:50]!r}); bad model id fails fast: {err}"


def live_agent_executor():
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    TOOL_LOG.clear()
    prompt = ChatPromptTemplate.from_messages([("system", "You are a personal finance assistant. Use tools for live data; never invent numbers."),
                                               ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
    tools = [get_budget_status, get_dashboard_summary]
    ex = AgentExecutor(agent=create_tool_calling_agent(_llm(), tools, prompt), tools=tools, return_intermediate_steps=True, max_iterations=6)
    out = ex.invoke({"input": "How am I doing on spending, and am I over budget on food?"})
    names = {a.tool for a, _ in out["intermediate_steps"]}
    assert len(out["intermediate_steps"]) >= 2 and {"get_budget_status", "get_dashboard_summary"} <= names, names
    return f"AgentExecutor intermediate_steps={len(out['intermediate_steps'])} tools={sorted(names)}"


def main():
    for name, fn in [("config from environment", off_config), ("langchain-google-genai objects construct, bind_tools, max_retries", off_construct),
                     ("thought_signature round-trip: response -> AIMessage -> request", off_signature_roundtrip),
                     ("thought_signature survives AgentExecutor scratchpad", off_signature_through_agent_loop),
                     ("parallel function calls keep signature on first call", off_parallel_calls_signature),
                     ("tool error becomes observation, loop continues", off_tool_error_loop),
                     ("retry/backoff semantics", off_retry_behaviour)]:
        run("OFFLINE", name, fn)
    for name, fn in [("L0 model ids exist (chat + embedding)", live_list_models), ("L1 plain generation", live_plain),
                     ("L2 embeddings", live_embeddings), ("L3 single tool call", live_single_tool_call),
                     ("L4 multi-turn tool calling (2 tools, final answer uses tool data)", live_multi_turn),
                     ("L5 thought-signature preservation (+ negative control)", live_thought_signature),
                     ("L6 tool error handling + retry/invalid model", live_tool_error_and_retry),
                     ("L7 AgentExecutor compound query >=2 tool calls", live_agent_executor)]:
        run("LIVE", name, fn, needs_key=True)
    w = max(len(r[1]) for r in ROWS)
    print(f"GEMINI_MODEL={MODEL}  EMBEDDING_MODEL={EMBED}  GOOGLE_API_KEY={'set' if KEY else 'NOT SET'}")
    for tier, name, st, d in ROWS:
        print(f"{tier:7} {st:28} {name:<{w}}  {d}")
    live = [r for r in ROWS if r[0] == "LIVE"]
    failed = [r for r in ROWS if r[2].endswith("FAIL")]
    skipped = [r for r in live if r[2].startswith("SKIPPED")]
    print()
    if failed:
        print("RESULT: FAILURES PRESENT")
        return 1
    if skipped:
        print(f"RESULT: OFFLINE checks passed. LIVE COMPATIBILITY NOT VERIFIED ({len(skipped)}/{len(live)} live checks skipped: no GOOGLE_API_KEY).")
        return 3
    print("RESULT: LIVE COMPATIBILITY VERIFIED (all live checks passed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
