"""Phase 5 LangGraph workflow: sequential supervisor pattern over four specialised agents with an error-routing edge."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv  # noqa: E402
from langgraph.graph import END, StateGraph  # noqa: E402

from common.api_client import FinanceApiClient  # noqa: E402
from common.observability import get_logger, span, traceable_if_enabled  # noqa: E402
from multi_agent.agents import PROJECT, ReportContext, budget_advisor, report_generator, savings_optimizer, transaction_analyzer  # noqa: E402
from multi_agent.state import FinancialHealthState, initial_state  # noqa: E402

load_dotenv()
PHASE = 5
logger = get_logger("multi_agent.graph", PHASE)


def should_continue_after_analysis(state: FinancialHealthState) -> str:
    """Supervisor routing: skip straight to the report (with a partial/error report) if analysis failed badly."""
    if state["report_status"] == "error":
        target, reason = "report_generator", "analysis_error"
    elif len(state["errors"]) > 2:
        target, reason = "report_generator", "too_many_errors"
    else:
        target, reason = "budget_advisor", "analysis_ok"
    with span("supervisor.route", **{"supervisor.from_agent": "transaction_analyzer", "supervisor.to_agent": target, "supervisor.routing_reason": reason}):
        logger.info("supervisor_route", from_agent="transaction_analyzer", to_agent=target, reason=reason)
    return target


def build_financial_report_graph():
    workflow = StateGraph(FinancialHealthState)
    workflow.add_node("transaction_analyzer", transaction_analyzer)
    workflow.add_node("budget_advisor", budget_advisor)
    workflow.add_node("savings_optimizer", savings_optimizer)
    workflow.add_node("report_generator", report_generator)
    workflow.set_entry_point("transaction_analyzer")
    workflow.add_conditional_edges(
        "transaction_analyzer", should_continue_after_analysis,
        {"budget_advisor": "budget_advisor", "report_generator": "report_generator"},
    )
    workflow.add_edge("budget_advisor", "savings_optimizer")
    workflow.add_edge("savings_optimizer", "report_generator")
    workflow.add_edge("report_generator", END)
    return workflow.compile()


@traceable_if_enabled(name="financial_health_report", project_name=PROJECT)
def generate_financial_report(user_id: int | None, report_month: int, report_year: int, token: str | None = None,
                              base_url: str | None = None, llm=None, use_llm: bool = True) -> FinancialHealthState:
    """Runs the four-agent pipeline for the user that owns `token` (default: API_JWT_TOKEN). If user_id is None it is taken
    from the token; a user_id that does not match the token is refused by the Transaction Analyzer."""
    started = time.perf_counter()
    ctx = ReportContext(base_url=base_url or os.getenv("API_BASE_URL"), token=token if token is not None else (os.getenv("API_JWT_TOKEN") or None), llm=llm, use_llm=use_llm)
    if user_id is None:
        me = FinanceApiClient(ctx.base_url, ctx.token).get("/users/me")
        user_id = me.data["id"] if me.ok else 0
    with span("graph.execute", **{"user_id": user_id, "report_month": report_month, "report_year": report_year, "phase": PHASE}) as sp:
        logger.info("report_generation_started", user_id=user_id, month=report_month, year=report_year)
        final_state = build_financial_report_graph().invoke(
            initial_state(user_id, report_month, report_year), config={"configurable": {"report_ctx": ctx}, "tags": ["phase-5"]}
        )
        sp.set_attribute("status", final_state["report_status"])
    logger.info(
        "report_generation_completed", user_id=user_id, status=final_state["report_status"], agents_activated=len(final_state["messages"]),
        duration_ms=int((time.perf_counter() - started) * 1000), operation="generate_report",
    )
    return final_state
