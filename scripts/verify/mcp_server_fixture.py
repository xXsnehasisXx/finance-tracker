"""Minimal FastMCP 0.4.1 server mirroring the Phase 4 tool style (plain functions + @mcp.tool())."""
import os
import sys

from fastmcp import FastMCP

mcp = FastMCP("Finance Tracker MCP Server")
_CALLS = {"n": 0}


@mcp.tool()
def add_transaction(account_id: int, amount: float, transaction_type: str, category: str,
                    description: str, transaction_date: str, merchant: str = "") -> dict:
    """Add a new financial transaction. transaction_type must be 'debit' or 'credit'."""
    if transaction_type not in ("debit", "credit"):
        return {"error": f"invalid transaction_type {transaction_type!r}"}
    _CALLS["n"] += 1
    return {"id": _CALLS["n"], "amount": amount, "category": category, "type": transaction_type,
            "merchant": merchant, "pid": os.getpid()}


@mcp.tool()
def get_budget_status() -> dict:
    """Get all budgets with spending and utilization."""
    return {"budgets": [{"category": "food", "utilization_percent": 85.0}]}


@mcp.tool()
def get_account_summary(account_id: int) -> dict:
    """Get summary for a specific account."""
    if account_id == 404:
        raise ValueError("Account not found")  # unhandled tool exception must surface as isError
    return {"account_id": account_id, "balance": 100.0}


if __name__ == "__main__":
    mcp.run()
