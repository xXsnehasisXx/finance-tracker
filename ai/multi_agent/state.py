"""Shared state for the Phase 5 financial-health workflow (LangGraph)."""
from typing import Any, Dict, List, TypedDict


class FinancialHealthState(TypedDict):
    # Input
    user_id: int
    report_month: int
    report_year: int
    # Raw data (fetched by the Transaction Analyzer through the REST API)
    transactions: List[Dict[str, Any]]
    budget_data: List[Dict[str, Any]]
    dashboard_data: Dict[str, Any]
    # Agent outputs
    spending_analysis: Dict[str, Any]       # Transaction Analyzer
    budget_analysis: Dict[str, Any]         # Budget Advisor
    savings_recommendations: List[str]      # Savings Optimizer
    # Final
    final_report: str                       # Report Generator
    report_status: str                      # "in_progress" | "complete" | "error"
    errors: List[str]
    messages: List[str]                     # audit trail of agent activations


def initial_state(user_id: int, report_month: int, report_year: int) -> FinancialHealthState:
    return FinancialHealthState(
        user_id=user_id,
        report_month=report_month,
        report_year=report_year,
        transactions=[],
        budget_data=[],
        dashboard_data={},
        spending_analysis={},
        budget_analysis={},
        savings_recommendations=[],
        final_report="",
        report_status="in_progress",
        errors=[],
        messages=[],
    )
