"""Phase 5 agents (LangGraph nodes): Transaction Analyzer -> Budget Advisor -> Savings Optimizer -> Report Generator.

Design: figures are computed deterministically in Python (calculations.py) from data fetched through the REST API with the
caller's own token; the LLM (Gemini) only adds short narrative text, which is discarded if it contains numbers that are not
in the facts. Without an LLM the pipeline still produces a complete report. Every node returns `{**state, ...}` and never
mutates its input.
"""
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv  # noqa: E402

from common.api_client import FinanceApiClient  # noqa: E402
from common.llm import message_text  # noqa: E402
from common.observability import get_logger, span, traceable_if_enabled  # noqa: E402
from multi_agent import calculations as calc  # noqa: E402
from multi_agent.state import FinancialHealthState  # noqa: E402

load_dotenv()
PHASE = 5
logger = get_logger("multi_agent", PHASE)
PROJECT = "AI-Readiness-POC-02-P5"

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


@dataclass
class ReportContext:
    base_url: str | None = None
    token: str | None = None
    llm: Any = None            # injected in tests; None -> built lazily from the environment (None if unavailable)
    use_llm: bool = True


def env_context() -> ReportContext:
    return ReportContext(base_url=os.getenv("API_BASE_URL"), token=os.getenv("API_JWT_TOKEN") or None)


def get_context(config) -> ReportContext:
    return ((config or {}).get("configurable") or {}).get("report_ctx") or env_context()


def _llm(ctx: ReportContext):
    if not ctx.use_llm:
        return None
    if ctx.llm is None:
        try:
            from common.llm import get_chat_model

            ctx.llm = get_chat_model(temperature=0.2)
        except Exception as exc:  # noqa: BLE001  (no key): deterministic mode
            logger.warning("llm_unavailable", reason=type(exc).__name__)
            ctx.use_llm = False
            return None
    return ctx.llm


def narrate(ctx: ReportContext, agent: str, instruction: str, facts: dict) -> str | None:
    """Short LLM narrative grounded in `facts`; None if no LLM, on failure, or if it states numbers not in the facts."""
    llm = _llm(ctx)
    if llm is None:
        return None
    import json

    prompt = (
        f"You are the {agent} in a personal finance report for an Indian user (amounts in rupees).\n{instruction}\n"
        "Rules: write 2 to 3 plain sentences; use ONLY numbers that appear in the facts below; do not add new numbers, "
        "percentages or dates; do not give investment advice.\n\nFacts (JSON):\n" + json.dumps(facts, ensure_ascii=False, default=str)
    )
    try:
        text = message_text(llm.invoke(prompt)).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("narrative_failed", agent=agent, error_type=type(exc).__name__)
        return None
    ok, bad = calc.narrative_is_grounded(text, facts)
    if not text or not ok:
        logger.warning("narrative_rejected", agent=agent, reason="ungrounded_numbers" if text else "empty", count=len(bad))
        return None
    return text


def _log_activation(agent: str, **fields):
    logger.info("agent_activated", agent=agent, operation="agent_activate", status="success", **fields)


# =====================================================================================================================
@traceable_if_enabled(name="transaction_analyzer", project_name=PROJECT)
def transaction_analyzer(state: FinancialHealthState, config=None) -> FinancialHealthState:
    """Fetches the month's transactions, dashboard and budgets (REST API, caller's token) and analyses spending patterns."""
    ctx = get_context(config)
    month, year = state["report_month"], state["report_year"]
    with span("agent.transaction_analyzer.activate", **{"user_id": state["user_id"], "agent.name": "transaction_analyzer"}) as sp:
        errors, messages = list(state["errors"]), list(state["messages"])
        client = FinanceApiClient(ctx.base_url, ctx.token)
        empty = {**state, "spending_analysis": {"total_transactions": 0, "total_spent": 0.0, "total_income": 0.0, "spending_by_category": {}, "unusual_patterns": []}}

        me = client.get("/users/me")
        if not me.ok:
            errors.append(f"Could not verify the user: {me.error}")
            messages.append("Transaction Analyzer: could not load data (user verification failed)")
            _log_activation("transaction_analyzer", transaction_count=0, errors=len(errors))
            return {**empty, "errors": errors, "messages": messages, "report_status": "error"}
        if me.data["id"] != state["user_id"]:
            errors.append("The authenticated user does not match the requested user; no data was loaded.")
            messages.append("Transaction Analyzer: refused (user mismatch)")
            logger.warning("report_user_mismatch")
            return {**empty, "errors": errors, "messages": messages, "report_status": "error"}

        date_from, date_to = calc.month_bounds(year, month)
        transactions: list[dict] = []
        page, pages = 1, 1
        while page <= pages and page <= 50:
            res = client.get("/transactions", date_from=date_from, date_to=date_to, page=page, page_size=100)
            if not res.ok:
                errors.append(f"Transaction fetch failed: {res.error}")
                break
            transactions += res.data["items"]
            pages, page = res.data["pages"], page + 1

        dash = client.get("/dashboard", month=month, year=year)
        if not dash.ok:
            errors.append(f"Dashboard fetch failed: {dash.error}")
        budgets = client.get("/budgets", month=month, year=year)
        if not budgets.ok:
            errors.append(f"Budget fetch failed: {budgets.error}")

        py, pm = calc.previous_period(year, month)
        previous = None
        prev_dash = client.get("/dashboard", month=pm, year=py)
        prev_cats = client.get("/analytics/spending-by-category", month=pm, year=py)
        if prev_dash.ok and prev_cats.ok:
            previous = {"month": pm, "year": py, "dashboard": prev_dash.data, "categories": prev_cats.data}

        dashboard = dash.data if dash.ok else {}
        analysis = calc.analyze_transactions(transactions, dashboard, previous)
        facts = {"month": f"{MONTH_NAMES[month - 1]} {year}", **{k: analysis[k] for k in ("total_spent", "total_income", "spending_by_category", "largest_expense", "top_merchant", "unusual_patterns", "previous_period")}}
        story = narrate(ctx, "Transaction Analyzer", "Summarise the spending pattern and anything unusual.", facts) if transactions else None
        if story:
            analysis["narrative"] = story
        messages.append(f"Transaction Analyzer: Processed {len(transactions)} transactions for {month}/{year}")
        sp.set_attribute("transaction_count", len(transactions))
    _log_activation("transaction_analyzer", transaction_count=len(transactions), errors=len(errors))
    return {
        **state, "transactions": transactions, "dashboard_data": dashboard, "budget_data": budgets.data if budgets.ok else [],
        "spending_analysis": analysis, "errors": errors, "messages": messages,
    }


@traceable_if_enabled(name="budget_advisor", project_name=PROJECT)
def budget_advisor(state: FinancialHealthState, config=None) -> FinancialHealthState:
    """Compares actual spending to budgets: over/under budget categories, risks, health score and budget adjustments."""
    ctx = get_context(config)
    with span("agent.budget_advisor.activate", **{"agent.name": "budget_advisor"}):
        analysis = calc.analyze_budgets(state["budget_data"], state["spending_analysis"])
        analysis["recommendations"] = calc.budget_recommendations(analysis)
        story = narrate(ctx, "Budget Advisor", "Explain how the user is doing against their budgets.", analysis) if state["budget_data"] else None
        if story:
            analysis["narrative"] = story
        messages = list(state["messages"]) + [f"Budget Advisor: Analyzed {len(state['budget_data'])} budget categories. Health score: {analysis['budget_health_score']}"]
    _log_activation("budget_advisor", budget_count=len(state["budget_data"]), health_score=analysis["budget_health_score"])
    return {**state, "budget_analysis": analysis, "messages": messages}


@traceable_if_enabled(name="savings_optimizer", project_name=PROJECT)
def savings_optimizer(state: FinancialHealthState, config=None) -> FinancialHealthState:
    """Calculates the savings rate (50/30/20 framework) and recommends realistic savings opportunities."""
    with span("agent.savings_optimizer.activate", **{"agent.name": "savings_optimizer"}):
        metrics = calc.savings_metrics(state["spending_analysis"], state["dashboard_data"])
        recs = calc.build_recommendations(state["spending_analysis"], state["budget_analysis"], state["dashboard_data"])
        messages = list(state["messages"]) + [f"Savings Optimizer: Generated {len(recs)} recommendations. Current savings rate: {metrics['savings_rate']:.1f}%"]
    _log_activation("savings_optimizer", savings_rate=metrics["savings_rate"], recommendations_count=len(recs))
    return {**state, "savings_recommendations": recs, "messages": messages}


@traceable_if_enabled(name="report_generator", project_name=PROJECT)
def report_generator(state: FinancialHealthState, config=None) -> FinancialHealthState:
    """Consolidates all findings into a structured Markdown financial health report."""
    ctx = get_context(config)
    with span("agent.report_generator.activate", **{"agent.name": "report_generator"}):
        spending, budget = state["spending_analysis"], state["budget_analysis"]
        metrics = calc.savings_metrics(spending, state["dashboard_data"])
        score = calc.health_score(int(budget.get("budget_health_score", 50)), metrics["savings_rate"])
        summary = None
        if not state["errors"] or spending.get("total_transactions"):
            facts = {"income": metrics["income"], "expenses": metrics["expenses"], "savings_rate": metrics["savings_rate"], "health_score": score,
                     "over_budget": [o.get("category") for o in budget.get("over_budget_categories", [])], "recommendations": state["savings_recommendations"][:3]}
            summary = narrate(ctx, "Report Generator", "Write the executive summary of the month's financial health.", facts)
        report = render_report(state, metrics, score, summary)
        data_failed = spending.get("total_transactions", 0) == 0 and not state["dashboard_data"] and bool(state["errors"])
        status = "error" if data_failed or state["report_status"] == "error" else "complete"
        messages = list(state["messages"]) + [f"Report Generator: Financial health report generated ({len(report)} characters)"]
    _log_activation("report_generator", report_length=len(report), health_score=score, status_value=status)
    return {**state, "final_report": report, "report_status": status, "messages": messages}


def render_report(state: FinancialHealthState, metrics: dict, score: int, summary: str | None) -> str:
    spending, budget, recs = state["spending_analysis"], state["budget_analysis"], state["savings_recommendations"]
    month, year = state["report_month"], state["report_year"]
    inr, title = calc.inr, calc.title
    lines = [f"# Financial Health Report — {MONTH_NAMES[month - 1]} {year}", ""]

    lines += ["## 1. Executive Summary", ""]
    if metrics["income"] > 0 or metrics["expenses"] > 0:
        lines.append(f"Income was {inr(metrics['income'])} and expenses were {inr(metrics['expenses'])}, leaving {inr(metrics['saved'])} "
                     f"(savings rate {metrics['savings_rate']}%). Overall financial health score: **{score}/100 ({calc.rating(score)})**.")
    else:
        lines.append(f"No income or expenses were recorded for {MONTH_NAMES[month - 1]} {year}. Overall financial health score: **{score}/100 ({calc.rating(score)})**, based on limited data.")
    if summary:
        lines += ["", f"*AI commentary:* {summary}"]
    lines.append("")

    lines += ["## 2. Income & Expense Overview", "", "| Item | Amount |", "|---|---|",
              f"| Income | {inr(metrics['income'])} |", f"| Expenses | {inr(metrics['expenses'])} |", f"| Net savings | {inr(metrics['saved'])} |",
              f"| Savings rate | {metrics['savings_rate']}% |"]
    prev = spending.get("previous_period")
    if prev:
        change = f" ({prev['spent_change_percent']:+}%)" if prev.get("spent_change_percent") is not None else ""
        lines.append(f"| Expenses last month ({prev['month']:02d}/{prev['year']}) | {inr(prev['total_spent'])}{change} |")
    if metrics.get("total_assets") is not None:
        lines.append(f"| Total assets (savings and checking) | {inr(metrics['total_assets'])} |")
    lines.append("")

    lines += ["## 3. Spending Analysis", ""]
    cats = spending.get("spending_by_category", {})
    if cats:
        total = sum(calc.D(v) for v in cats.values())
        lines += ["| Category | Spent | Share |", "|---|---|---|"] + [f"| {title(c)} | {inr(a)} | {calc.pct(a, total)}% |" for c, a in cats.items()]
    else:
        lines.append("No spending was recorded for this period.")
    if spending.get("largest_expense"):
        le = spending["largest_expense"]
        lines += ["", f"- Largest expense: {inr(le['amount'])} on {title(le['category'])} ({le['description']}, {le['date']})."]
    if spending.get("top_merchant"):
        lines.append(f"- Top merchant: {spending['top_merchant']['merchant']} ({inr(spending['top_merchant']['amount'])}).")
    for u in spending.get("unusual_patterns", []):
        lines.append(f"- Notable: {u}")
    if spending.get("narrative"):
        lines += ["", f"*AI commentary:* {spending['narrative']}"]
    lines.append("")

    lines += ["## 4. Budget Performance", ""]
    if budget.get("has_budgets"):
        lines.append(f"Budget health score: **{budget.get('budget_health_score')}/100**; overall budget utilization {budget.get('total_budget_utilization')}%.")
        for o in budget.get("over_budget_categories", []):
            lines.append(f"- 🔴 {title(o['category'])}: {inr(o['spent'])} of {inr(o['limit'])} ({o['utilization_percent']}%) — over budget")
        for w in budget.get("warning_categories", []):
            lines.append(f"- 🟠 {title(w['category'])}: {inr(w['spent'])} of {inr(w['limit'])} ({w['utilization_percent']}%) — warning")
        for u in budget.get("under_budget_categories", []):
            lines.append(f"- 🟢 {title(u['category'])}: {inr(u['spent'])} of {inr(u['limit'])} ({u['utilization_percent']}%) — on track")
        for r in budget.get("recommendations", []):
            lines.append(f"- Advice: {r}")
    else:
        lines.append("No budgets were set for this period, so budget performance cannot be assessed.")
    if budget.get("narrative"):
        lines += ["", f"*AI commentary:* {budget['narrative']}"]
    lines.append("")

    lines += ["## 5. Savings Optimizer Recommendations", ""]
    lines += [f"{i}. {r}" for i, r in enumerate(recs, 1)] or ["No recommendations could be generated."]
    if metrics["income"] > 0:
        lines += ["", f"*50/30/20 check:* essentials {metrics['needs_percent']}% (guide 50%), discretionary {metrics['wants_percent']}% (guide 30%), savings {metrics['savings_percent']}% (guide 20%). Categories are grouped in a simplified way."]
    lines.append("")

    lines += ["## 6. Financial Risks", ""]
    risks = calc.financial_risks(spending, budget, metrics)
    lines += [f"- {r}" for r in risks] or ["No significant risks were detected from this month's data."]
    lines.append("")

    lines += ["## 7. Action Items for Next Month", ""]
    lines += [f"{i}. {a}" for i, a in enumerate(calc.action_items(budget.get("recommendations", []), recs), 1)]
    lines.append("")

    lines += ["## 8. Financial Health Score", "",
              f"**{score}/100 — {calc.rating(score)}.** Score = 50% budget health ({budget.get('budget_health_score', 50)}) + 50% savings rate against a 30% target ({metrics['savings_rate']}%)."]
    if state["errors"]:
        lines += ["", "### Data notes", ""] + [f"- {e}" for e in state["errors"]]
    lines += ["", "---", "*Figures are calculated from your recorded transactions; transfers between your own accounts are excluded. This report is informational, not financial advice.*"]
    return "\n".join(lines)
