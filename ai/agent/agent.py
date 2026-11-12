"""Phase 3 agent: LangChain tool-calling agent (AgentExecutor) over the finance tools + RAG, for ONE authenticated user."""
import datetime
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv  # noqa: E402
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # noqa: E402

from agent.prompts import FINANCE_AGENT_SYSTEM_PROMPT  # noqa: E402
from agent.tools import ToolContext, make_tools  # noqa: E402
from common.llm import message_text  # noqa: E402
from common.observability import get_logger, span, traceable_if_enabled  # noqa: E402

load_dotenv()
PHASE = 3
logger = get_logger("agent", PHASE)

NO_KEY_MESSAGE = "The AI assistant is not configured: GOOGLE_API_KEY is not set. Add it to .env to use live Gemini features."
FAILURE_MESSAGE = "Sorry, I couldn't complete that request just now. Please try again."


class FinanceAgentExecutor(AgentExecutor):
    """AgentExecutor that remembers the per-user tool context (used for the 'today' date)."""

    ctx: Any = None


def build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", FINANCE_AGENT_SYSTEM_PROMPT),
        ("system", "Today's date is {today}."),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])


def default_llm():
    """Gemini chat model from the environment. Without a key it still builds (so tools/structure are inspectable);
    the key is only needed when the model is actually called, and run_agent/process_message report that clearly."""
    from common.llm import MissingApiKeyError, chat_model_name, get_chat_model

    try:
        return get_chat_model(temperature=0)
    except MissingApiKeyError:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=chat_model_name(), google_api_key="missing-key", max_retries=0, timeout=5)


def build_agent(llm=None, token: str | None = None, base_url: str | None = None, rag_chain=None, today=None) -> AgentExecutor:
    """token/base_url bind the tools to one user (default: API_JWT_TOKEN / API_BASE_URL from the environment).
    `llm` is injectable for offline tests; the default is the Gemini model configured through the environment."""
    llm = llm or default_llm()
    ctx = ToolContext(base_url=base_url or os.getenv("API_BASE_URL"), token=token if token is not None else (os.getenv("API_JWT_TOKEN") or None),
                      rag_chain=rag_chain, today=today or datetime.date.today)
    tools = make_tools(lambda: ctx)
    agent = create_tool_calling_agent(llm, tools, build_prompt())
    executor = FinanceAgentExecutor(
        agent=agent, tools=tools, verbose=False, return_intermediate_steps=True, max_iterations=6,
        handle_parsing_errors=True, early_stopping_method="force", ctx=ctx,
    )
    return executor


@traceable_if_enabled(
    name="finance_agent_query",
    project_name="AI-Readiness-POC-02-P3",
    process_inputs=lambda inputs: {"question": inputs.get("question")},
)
def run_agent(question: str, executor: AgentExecutor, chat_history: list | None = None) -> dict:
    started = time.perf_counter()
    question = (question or "").strip()
    if not question:
        return {"output": "Please ask a question about your finances.", "intermediate_steps": []}
    today = getattr(getattr(executor, "ctx", None), "today", datetime.date.today)()
    with span("agent.execute", **{"question": question[:100], "phase": PHASE}) as sp:
        logger.info("agent_query_received", question=question[:80])
        try:
            result = executor.invoke({"input": question, "today": today.strftime("%A, %d %B %Y"), "chat_history": chat_history or []})
        except Exception as exc:  # noqa: BLE001
            no_key = os.getenv("GOOGLE_API_KEY", "") == ""
            logger.error("agent_query_failed", error_type=type(exc).__name__, question=question[:80], no_api_key=no_key)
            return {"output": NO_KEY_MESSAGE if no_key else FAILURE_MESSAGE, "intermediate_steps": [], "error": type(exc).__name__}
        steps = result.get("intermediate_steps", [])
        output = result.get("output", "")
        if not isinstance(output, str):
            output = message_text(output) if not isinstance(output, list) else "".join(b.get("text", "") for b in output if isinstance(b, dict))
        result["output"] = output
        sp.set_attribute("tool_calls_count", len(steps))
    logger.info(
        "agent_query_completed", tool_calls=len(steps), output_length=len(output),
        tools=[s[0].tool for s in steps], duration_ms=int((time.perf_counter() - started) * 1000), operation="agent_query", status="success",
    )
    return result
