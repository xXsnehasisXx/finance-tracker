"""Phase 4 MCP server (fastmcp, stdio). Exposes the finance operations as MCP tools; every tool calls the REST API.

* The user's identity comes from the server PROCESS environment (API_JWT_TOKEN, API_BASE_URL, MCP_SESSION_ID), set by the
  client that starts the server for one signed-in user. It is never a tool argument, so a model cannot pick another user.
* Business rules and authorization stay in the backend: the server validates obvious input errors, then forwards.
* Tools never raise: failures are returned as {"error": "..."} so callers can show a readable message.
* The functions stay plain callables (importable and testable); `@mcp.tool()` only registers them.

Run (stdio):  python ai/mcp_server/mcp_app.py
"""
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fastmcp import FastMCP  # noqa: E402

from common.api_client import FinanceApiClient  # noqa: E402
from common.observability import get_logger, span  # noqa: E402

PHASE = 4
logger = get_logger("mcp_app", PHASE)

mcp = FastMCP("Finance Tracker MCP Server")

CATEGORIES = ("food", "transport", "utilities", "entertainment", "health", "salary", "other")
BUDGET_CATEGORIES = tuple(c for c in CATEGORIES if c != "salary")
TRANSACTION_TYPES = ("debit", "credit")


def _client() -> FinanceApiClient:
    return FinanceApiClient(os.getenv("API_BASE_URL"), os.getenv("API_JWT_TOKEN") or None)


def _tool(name: str, fn, **log_fields):
    """Runs a tool body with a span, a structured log line and the never-raise contract."""
    started = time.perf_counter()
    session_id = os.getenv("MCP_SESSION_ID", "")
    with span("mcp.tool_invoke", **{"mcp.tool_name": name, "mcp.session_id": session_id}) as sp:
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            logger.error("mcp_tool_failed", tool=name, session_id=session_id, error_type=type(exc).__name__)
            result = {"error": f"Unexpected error in {name} ({type(exc).__name__})."}
        ok = "error" not in result
        sp.set_attribute("mcp.success", ok)
    logger.info("mcp_tool_invoked", tool=name, session_id=session_id, success=ok, duration_ms=int((time.perf_counter() - started) * 1000),
                operation="mcp_tool", status="success" if ok else "failure", **log_fields)
    return result


def _result(res):
    return res.data if res.ok else {"error": res.error}


def _check_date(value: str, field: str) -> str | None:
    try:
        datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return f"{field} must be a date in YYYY-MM-DD format (got {value!r})."
    return None


def validate_transaction_args(account_id, amount, transaction_type, category, description, transaction_date) -> str | None:
    """Returns an error message for invalid input, else None. Shared with the chat layer's confirmation step."""
    if not isinstance(account_id, int) or isinstance(account_id, bool) or account_id <= 0:
        return "account_id must be a positive integer."
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        return "amount must be a number greater than 0."
    if transaction_type not in TRANSACTION_TYPES:
        return f"transaction_type must be 'debit' (expense) or 'credit' (income), not {transaction_type!r}."
    if category not in CATEGORIES:
        return f"category must be one of: {', '.join(CATEGORIES)} (got {category!r})."
    if not description or not str(description).strip():
        return "description is required."
    return _check_date(transaction_date, "transaction_date")


def validate_budget_args(category, monthly_limit, month, year) -> str | None:
    if category not in BUDGET_CATEGORIES:
        return f"category must be one of: {', '.join(BUDGET_CATEGORIES)} (salary cannot have a budget)."
    if not isinstance(monthly_limit, (int, float)) or isinstance(monthly_limit, bool) or monthly_limit <= 0:
        return "monthly_limit must be a number greater than 0."
    if not isinstance(month, int) or not 1 <= month <= 12:
        return "month must be between 1 and 12."
    if not isinstance(year, int) or not 2000 <= year <= 2100:
        return "year must be between 2000 and 2100."
    return None


@mcp.tool()
def add_transaction(
    account_id: int,
    amount: float,
    transaction_type: str,
    category: str,
    description: str,
    transaction_date: str,
    merchant: str = "",
) -> dict:
    """Add a new financial transaction. transaction_type must be 'debit' (expense) or 'credit' (income).
    category must be one of: food, transport, utilities, entertainment, health, salary, other.
    transaction_date format: YYYY-MM-DD. Returns the created transaction or an error."""

    def run():
        problem = validate_transaction_args(account_id, amount, transaction_type, category, description, transaction_date)
        if problem:
            return {"error": problem}
        body = {"account_id": account_id, "amount": amount, "type": transaction_type, "category": category,
                "description": description.strip(), "transaction_date": transaction_date}
        if merchant and merchant.strip():
            body["merchant"] = merchant.strip()
        return _result(_client().post("/transactions", body))

    return _tool("add_transaction", run, amount=amount, category=category)


@mcp.tool()
def get_transactions(account_id: int = 0, category: str = "", date_from: str = "", date_to: str = "", transaction_type: str = "", page: int = 1) -> dict:
    """Get a page of transactions (20 per page) with optional filters. category options: food, transport, utilities,
    entertainment, health, salary, other. Dates use YYYY-MM-DD. transaction_type is 'debit' or 'credit'."""

    def run():
        for value, field in ((date_from, "date_from"), (date_to, "date_to")):
            if value and (problem := _check_date(value, field)):
                return {"error": problem}
        if category and category not in CATEGORIES:
            return {"error": f"category must be one of: {', '.join(CATEGORIES)}."}
        if transaction_type and transaction_type not in TRANSACTION_TYPES:
            return {"error": "transaction_type must be 'debit' or 'credit'."}
        return _result(_client().get("/transactions", account_id=account_id or None, category=category, date_from=date_from,
                                     date_to=date_to, type=transaction_type, page=page))

    return _tool("get_transactions", run)


@mcp.tool()
def get_budget_status(month: int = 0, year: int = 0) -> dict:
    """Get all budgets with current spending, remaining amounts and utilization percentages (default: all months).
    Optionally filter by month (1-12) and year. has_alert is true for budgets that triggered an alert."""

    def run():
        res = _client().get("/budgets", month=month or None, year=year or None)
        return {"budgets": res.data} if res.ok else {"error": res.error}

    return _tool("get_budget_status", run)


@mcp.tool()
def get_dashboard_summary(month: int = 0, year: int = 0) -> dict:
    """Get the financial dashboard: net balance, total assets and credit owed, monthly income and expenses, savings rate,
    top 3 spending categories and budget alert count. Optional month (1-12) and year (default: current month)."""
    return _tool("get_dashboard_summary", lambda: _result(_client().get("/dashboard", month=month or None, year=year or None)))


@mcp.tool()
def set_budget(category: str, monthly_limit: float, month: int, year: int) -> dict:
    """Set a monthly spending budget for a category (food, transport, utilities, entertainment, health, other).
    Returns the created budget, or an error if one already exists for that category and month."""

    def run():
        problem = validate_budget_args(category, monthly_limit, month, year)
        if problem:
            return {"error": problem}
        return _result(_client().post("/budgets", {"category": category, "monthly_limit": monthly_limit, "month": month, "year": year}))

    return _tool("set_budget", run, category=category, monthly_limit=monthly_limit)


@mcp.tool()
def get_account_summary(account_id: int) -> dict:
    """Get the summary of one account: total credits, total debits, balance, spending by category and the monthly trend
    for the last 6 months."""

    def run():
        if not isinstance(account_id, int) or account_id <= 0:
            return {"error": "account_id must be a positive integer."}
        return _result(_client().get(f"/accounts/{account_id}/summary"))

    return _tool("get_account_summary", run, account_id=account_id)


@mcp.tool()
def get_accounts() -> dict:
    """List the user's accounts with id, name, type and balance (for credit accounts the balance is the amount owed).
    Use it to find the account_id needed by add_transaction."""

    def run():
        res = _client().get("/accounts")
        return {"accounts": res.data} if res.ok else {"error": res.error}

    return _tool("get_accounts", run)


def main():
    from common.observability import configure_logging

    configure_logging(PHASE, stream=sys.stderr)  # stdout is the MCP protocol channel
    logger.info("mcp_server_started", tools=["add_transaction", "get_transactions", "get_budget_status", "get_dashboard_summary",
                                             "set_budget", "get_account_summary", "get_accounts"], operation="startup", status="success")
    mcp.run()


if __name__ == "__main__":
    main()
