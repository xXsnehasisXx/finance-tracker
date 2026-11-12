"""Phase 3 LangChain tools over the Finance REST API (+ RAG).

* Tools are built by `make_tools(get_context)`; the context carries the *caller's own* token, so an agent can only see
  that user's data (the backend enforces authorization). The module-level tools use the environment (API_JWT_TOKEN,
  API_BASE_URL) for CLI/tests; `build_agent(token=...)` creates per-user tools.
* Tools NEVER raise: every failure is returned as a readable string so the agent loop keeps working.
* Read-only: no tool can create, change or delete financial data.
"""
import datetime
import functools
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv  # noqa: E402
from langchain_core.tools import tool  # noqa: E402

from agent.summarizer import _summarize_if_long  # noqa: E402
from common.api_client import FinanceApiClient  # noqa: E402
from common.observability import get_logger, span  # noqa: E402

load_dotenv()
PHASE = 3
logger = get_logger("agent.tools", PHASE)

CATEGORIES = ("food", "transport", "utilities", "entertainment", "health", "salary", "other")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
_PERIOD = re.compile(r"\b(\d{4})-(\d{1,2})\b")


@dataclass
class ToolContext:
    base_url: str | None = None
    token: str | None = None
    rag_chain: Any = None          # a RagChain, or None to build one lazily from the environment
    summarizer_llm: Any = None     # optional (tests)
    today: Callable[[], datetime.date] = datetime.date.today


def env_context() -> ToolContext:
    return ToolContext(base_url=os.getenv("API_BASE_URL"), token=os.getenv("API_JWT_TOKEN") or None)


def _inr(value) -> str:
    return f"₹{float(value or 0):,.2f}"


def _title(s: str) -> str:
    return s.replace("_", " ").title()


def _parse_hint(text: str, today: datetime.date):
    """Pull an optional category and an optional YYYY-MM period out of free text such as 'food 2026-06'."""
    text = (text or "").strip().lower()
    category = next((c for c in CATEGORIES if re.search(rf"\b{c}\b", text)), None)
    m = _PERIOD.search(text)
    year, month = (int(m.group(1)), int(m.group(2))) if m and 1 <= int(m.group(2)) <= 12 else (today.year, today.month)
    return category, year, month


_rag_cache: dict = {}


def _default_rag_chain():
    if "chain" not in _rag_cache:
        from rag.rag_chain import build_rag_chain

        _rag_cache["chain"] = build_rag_chain()  # cached: building per call is slow
    return _rag_cache["chain"]


def make_tools(get_context: Callable[[], ToolContext]) -> list:
    def client() -> FinanceApiClient:
        ctx = get_context()
        return FinanceApiClient(ctx.base_url, ctx.token)

    def guarded(name: str):
        """Wraps a tool body: span + logging + never-raise + long-output summarization."""

        def deco(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                started = time.perf_counter()
                with span("agent.tool_call", **{"tool.name": name}) as sp:
                    try:
                        out = fn(*args, **kwargs)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("tool_failed", tool=name, error_type=type(exc).__name__)
                        out = f"Could not complete {name}: an unexpected error occurred ({type(exc).__name__})."
                    out = _summarize_if_long(out, get_context().summarizer_llm)
                    sp.set_attribute("tool.output_length", len(out))
                logger.info("tool_executed", tool=name, output_length=len(out), duration_ms=int((time.perf_counter() - started) * 1000), operation="tool_call", status="success")
                return out

            return wrapper

        return deco

    @tool
    @guarded("get_budget_status")
    def get_budget_status(input: str = "") -> str:
        """Use this when the user asks about budgets, spending limits, whether they are over or under budget for a category, or budget utilization. Optional input: a category name and/or a month as YYYY-MM (default: the current month). Returns each budget with spent, remaining and percent used."""
        today = get_context().today()
        category, year, month = _parse_hint(input, today)
        res = client().get("/budgets", month=month, year=year)
        if not res.ok:
            return f"Could not retrieve budget data: {res.error}"
        budgets = [b for b in res.data if category is None or b["category"] == category]
        period = f"{MONTHS[month - 1]} {year}"
        if not budgets:
            if category:
                return f"No budget is configured for {category} in {period}."
            return f"No budgets are configured for {period}. Set monthly budgets in the Budgets section."
        lines = [f"Budget status for {period}:"]
        for b in budgets:
            pct = b["utilization_percent"]
            flag = "OVER BUDGET" if pct >= 100 else "warning (80% reached)" if pct >= 80 else "on track"
            left = f"{_inr(b['remaining'])} remaining" if b["remaining"] >= 0 else f"{_inr(-b['remaining'])} over the limit"
            alert = " - alert triggered" if b["has_alert"] else ""
            lines.append(f"- {_title(b['category'])}: spent {_inr(b['spent'])} of {_inr(b['monthly_limit'])} ({pct:.1f}% used), {left} - {flag}{alert}")
        return "\n".join(lines)

    @tool
    @guarded("get_dashboard_summary")
    def get_dashboard_summary(input: str = "") -> str:
        """Use this when the user asks about their total balance, monthly income, monthly expenses, net cash flow, savings rate, or top spending categories. Optional input: a month as YYYY-MM (default: the current month). Returns the financial dashboard overview."""
        today = get_context().today()
        _, year, month = _parse_hint(input, today)
        res = client().get("/dashboard", month=month, year=year)
        if not res.ok:
            return f"Could not retrieve dashboard data: {res.error}"
        d = res.data
        top = ", ".join(f"{_title(c['category'])} ({_inr(c['amount'])})" for c in d["top_3_categories"]) or "no spending recorded"
        return (
            f"Financial dashboard for {MONTHS[d['month'] - 1]} {d['year']}:\n"
            f"- Net balance (assets minus credit owed): {_inr(d['total_balance'])}\n"
            f"- Total assets (savings and checking): {_inr(d['total_assets'])}\n"
            f"- Credit owed: {_inr(d['total_liabilities'])}\n"
            f"- Monthly income: {_inr(d['monthly_income'])}\n"
            f"- Monthly expenses: {_inr(d['monthly_expenses'])}\n"
            f"- Net cash flow: {_inr(d['net_cash_flow'])}\n"
            f"- Savings rate: {d['savings_rate']:.1f}%\n"
            f"- Top spending categories: {top}\n"
            f"- Budget alerts this month: {d['budget_alerts_count']}"
        )

    @tool
    @guarded("get_accounts")
    def get_accounts(input: str = "") -> str:
        """Use this when the user asks which accounts they have, wants account balances, or when you need an account id. Returns every account with its id, type and balance (for credit accounts the balance is the amount owed)."""
        res = client().get("/accounts")
        if not res.ok:
            return f"Could not retrieve accounts: {res.error}"
        if not res.data:
            return "You have no accounts yet. Create one in the Accounts section."
        lines = ["Your accounts:"]
        for a in res.data:
            label = "owed" if a["account_type"] == "credit" else "balance"
            lines.append(f"- id {a['id']}: {a['account_name']} ({a['account_type']}) - {label} {_inr(a['balance'])}")
        return "\n".join(lines)

    @tool
    @guarded("get_account_summary")
    def get_account_summary(account_id: str) -> str:
        """Use this when the user asks about a specific account's details, balance, spending breakdown by category, or monthly spending trend. Input: the account ID as a string (for example '1'). Use get_accounts first if the id is unknown."""
        account_id = str(account_id).strip()
        if not account_id.isdigit():
            return f"Could not retrieve account summary: '{account_id}' is not a valid account id."
        res = client().get(f"/accounts/{account_id}/summary")
        if not res.ok:
            if res.status == 404:
                return f"Account {account_id} not found. Please verify the account ID."
            return f"Could not retrieve account summary for account {account_id}: {res.error}"
        d = res.data
        spending = "\n".join(f"  - {_title(c)}: {_inr(a)}" for c, a in d["spending_by_category"].items()) or "  - No spending recorded"
        trend = ", ".join(f"{t['month']}: {_inr(t['spending'])}" for t in d["monthly_trend"])
        return (
            f"Account {account_id} summary:\n"
            f"- Current balance: {_inr(d['balance'])}\n"
            f"- Total credits: {_inr(d['total_credit'])}\n"
            f"- Total debits: {_inr(d['total_debit'])}\n"
            f"- Spending by category:\n{spending}\n"
            f"- Monthly spending trend (last 6 months): {trend}"
        )

    @tool
    @guarded("get_transactions")
    def get_transactions(input: str = "") -> str:
        """Use this when the user asks to see transactions, filter them by category, date or type, or analyze recent spending. Input: a JSON string with optional filters, for example {"account_id": 1, "category": "food", "date_from": "2026-06-01", "date_to": "2026-06-30", "type": "debit"}."""
        raw = (input or "").strip()
        filters: dict = {}
        if raw.startswith("{"):
            try:
                filters = json.loads(raw)
            except json.JSONDecodeError:
                return "Could not read the filters: input must be valid JSON such as {\"category\": \"food\"}."
            if not isinstance(filters, dict):
                return "Could not read the filters: input must be a JSON object."
        elif raw.lower() in CATEGORIES:
            filters = {"category": raw.lower()}
        allowed = {k: filters[k] for k in ("account_id", "category", "date_from", "date_to", "type") if filters.get(k)}
        res = client().get("/transactions", page_size=20, **allowed)
        if not res.ok:
            return f"Could not retrieve transactions: {res.error}"
        items, total = res.data["items"], res.data["total"]
        if not items:
            return "No transactions found matching the specified filters."
        lines = [f"Found {total} transaction(s); showing the {min(len(items), 10)} most recent:"]
        for t in items[:10]:
            kind = "Debit" if t["type"] == "debit" else "Credit"
            extra = f" ({t['merchant']})" if t.get("merchant") else ""
            mark = " [transfer]" if t.get("is_transfer") else ""
            lines.append(f"- {t['transaction_date']} | {kind} | {_inr(t['amount'])} | {_title(t['category'])} | {t['description'][:60]}{extra}{mark}")
        if total > 10:
            lines.append(f"... and {total - 10} more.")
        return "\n".join(lines)

    @tool
    @guarded("get_spending_by_category")
    def get_spending_by_category(input: str = "") -> str:
        """Use this when the user asks where their money goes or how much they spent in each category. Optional input: a month as YYYY-MM (default: the current month). Excludes transfers between accounts."""
        today = get_context().today()
        _, year, month = _parse_hint(input, today)
        res = client().get("/analytics/spending-by-category", month=month, year=year)
        if not res.ok:
            return f"Could not retrieve spending by category: {res.error}"
        if not res.data:
            return f"No spending recorded for {MONTHS[month - 1]} {year}."
        total = sum(c["amount"] for c in res.data)
        lines = [f"Spending by category for {MONTHS[month - 1]} {year} (total {_inr(total)}):"]
        lines += [f"- {_title(c['category'])}: {_inr(c['amount'])}" for c in res.data]
        return "\n".join(lines)

    @tool
    @guarded("search_finance_policy")
    def search_finance_policy(question: str) -> str:
        """Use this when the user asks how something works in the Finance Tracker app, about transaction categories, how to set budgets, how alerts work, or wants financial guidance and best practices. Searches the user manual using retrieval (RAG)."""
        from common.llm import MissingApiKeyError
        from rag.rag_chain import ask_question

        ctx = get_context()
        try:
            chain = ctx.rag_chain or _default_rag_chain()
        except MissingApiKeyError:
            return "The knowledge base is unavailable because GOOGLE_API_KEY is not set."
        except RuntimeError as exc:
            return f"The knowledge base is unavailable: {exc}"
        result = ask_question(question, chain)
        sections = sorted({s["section"] for s in result.get("source_details", [])})
        suffix = f"\n(Sources: {'; '.join(sections)})" if sections else ""
        return result["answer"] + suffix

    return [get_budget_status, get_dashboard_summary, get_accounts, get_account_summary, get_transactions, get_spending_by_category, search_finance_policy]


# Module-level tools (env-configured) - used by the POC tests and CLI; per-user agents use make_tools(...) instead.
_default_tools = make_tools(env_context)
(get_budget_status, get_dashboard_summary, get_accounts, get_account_summary,
 get_transactions, get_spending_by_category, search_finance_policy) = _default_tools
TOOLS = _default_tools
