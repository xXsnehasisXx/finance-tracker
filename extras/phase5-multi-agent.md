# Phase 5: Multi-Agent Financial Health Report
## POC-02 — Personal Finance Tracker & Analytics

**Phase Weight:** 20% | **Duration:** 5 days | **Test Cases:** 25

---

## 1. Phase Overview

Build a LangGraph multi-agent pipeline that automatically generates a comprehensive **Financial Health Report**. Four specialized agents — Transaction Analyzer, Budget Advisor, Savings Optimizer, and Report Generator — each analyze a different aspect of the user's finances and collaborate to produce a single actionable report with personalized recommendations.

### 5-Day Schedule
| Day | Focus |
|-----|-------|
| Day 1 | Understand LangGraph StateGraph, TypedDict state, node functions |
| Day 2 | Implement Transaction Analyzer and Budget Advisor agents |
| Day 3 | Implement Savings Optimizer and Report Generator agents |
| Day 4 | Wire up the graph: nodes, edges, conditional routing |
| Day 5 | Add observability, run all 25 test cases |

---

## 2. Prerequisites
- Phase 1 API running on `http://localhost:8000`
- `langgraph==0.1.17` installed
- `API_JWT_TOKEN` in `.env`
- LangSmith project `AI-Readiness-POC-02-P5`

---

## 3. Concepts to Self-Learn
| Concept | Search Term |
|---------|-------------|
| LangGraph StateGraph | "LangGraph StateGraph tutorial Python" |
| TypedDict in Python | "Python TypedDict tutorial" |
| LangGraph conditional edges | "LangGraph add_conditional_edges example" |
| Multi-agent patterns | "LangGraph multi-agent supervisor pattern" |
| LangGraph state updates | "LangGraph state update node function" |

---

## 4. Project Structure

```
poc-02-finance-tracker/
├── multi_agent/
│   ├── state.py           ← FinancialHealthState TypedDict
│   ├── agents.py          ← 4 agent node functions
│   ├── graph.py           ← Build and run the StateGraph
│   └── report_runner.py   ← Entry point to trigger report generation
└── tests/phase5/
```

---

## 5. Why Multi-Agent for Financial Health Reports?

A single LLM prompt cannot effectively:
- Calculate DTI ratio AND recommend budget reallocation AND project savings AND format a professional report all at once
- Apply specialized financial analysis frameworks per domain
- Produce auditable intermediate results showing each analysis step

**Multi-agent advantages:**
- **Separation of Concerns:** Each agent has a focused, narrow job
- **Specialized Prompts:** The Savings Optimizer uses different financial frameworks than the Transaction Analyzer
- **Auditability:** Each agent's analysis is captured in state — you can see exactly what the Budget Advisor found
- **Extensibility:** Add a fifth agent (e.g., Investment Advisor) without changing the other four

---

## 6. Agent Definitions

| Agent | Role | Input from State | Output to State |
|-------|------|-----------------|-----------------|
| Transaction Analyzer | Categorizes spending, identifies patterns, flags unusual activity | raw transaction data from API | spending_analysis dict |
| Budget Advisor | Compares actual spending to budgets, identifies over/under budget categories | spending_analysis, budget data from API | budget_analysis dict |
| Savings Optimizer | Calculates savings rate, identifies reduction opportunities, projects savings scenarios | spending_analysis, budget_analysis, dashboard data | savings_recommendations list |
| Report Generator | Synthesizes all analyses into a structured, human-readable report with action items | all analysis fields | final_report string |

---

## 7. State Schema

```python
# multi_agent/state.py
from typing import TypedDict, Optional, List, Dict, Any

class FinancialHealthState(TypedDict):
    # Input
    user_id: int
    report_month: int
    report_year: int
    
    # Raw data (fetched by Transaction Analyzer)
    transactions: List[Dict[str, Any]]
    budget_data: List[Dict[str, Any]]
    dashboard_data: Dict[str, Any]
    
    # Agent outputs
    spending_analysis: Dict[str, Any]     # From Transaction Analyzer
    budget_analysis: Dict[str, Any]       # From Budget Advisor
    savings_recommendations: List[str]    # From Savings Optimizer
    
    # Final
    final_report: str
    report_status: str                    # "in_progress" | "complete" | "error"
    errors: List[str]
    messages: List[str]                   # Audit trail of agent activations
```

---

## 8. Implementation Guide

### Step 1: Write `multi_agent/state.py`

```python
# multi_agent/state.py
from typing import TypedDict, Optional, List, Dict, Any

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
        messages=[]
    )
```

### Step 2: Write `multi_agent/agents.py`

```python
# multi_agent/agents.py
import os
import json
import requests
import structlog
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langsmith import traceable
from opentelemetry import trace
from dotenv import load_dotenv

from multi_agent.state import FinancialHealthState

load_dotenv()

logger = structlog.get_logger()
tracer = trace.get_tracer("poc-02-multiagent")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
JWT_TOKEN = os.getenv("API_JWT_TOKEN", "")

def _headers():
    return {"Authorization": f"Bearer {JWT_TOKEN}"}

def _get(path: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def _get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.2
    )

# ─── Agent 1: Transaction Analyzer ────────────────────────────────────────────

@traceable(name="transaction_analyzer", project_name="AI-Readiness-POC-02-P5")
def transaction_analyzer(state: FinancialHealthState) -> FinancialHealthState:
    """Fetches transaction data and analyzes spending patterns."""
    with tracer.start_as_current_span("agent.transaction_analyzer.activate") as span:
        span.set_attribute("user_id", state["user_id"])
        span.set_attribute("poc_id", "POC-02")
        
        month = state["report_month"]
        year = state["report_year"]
        
        # Fetch transactions for the report month
        date_from = f"{year}-{month:02d}-01"
        date_to = f"{year}-{month:02d}-28"
        
        txn_data = _get(f"/transactions?date_from={date_from}&date_to={date_to}")
        dashboard_data = _get("/dashboard")
        budget_data = _get("/budgets")
        
        transactions = txn_data if isinstance(txn_data, list) else txn_data.get("items", [])
        
        errors = list(state["errors"])
        if "error" in txn_data:
            errors.append(f"Transaction fetch failed: {txn_data['error']}")
        
        # Analyze spending patterns with Gemini
        llm = _get_llm()
        
        txn_summary = json.dumps(transactions[:20], indent=2) if transactions else "No transactions found"
        
        prompt = f"""You are a Transaction Analyzer. Analyze the following transactions for month {month}/{year}.

Transactions:
{txn_summary}

Provide a JSON analysis with:
- total_transactions: count
- total_spent: sum of all debit amounts (number)
- total_income: sum of all credit amounts (number)
- spending_by_category: dict of category to total amount
- largest_expense: single transaction description and amount
- unusual_patterns: list of any suspicious patterns (e.g., high single transactions, duplicate merchants)
- top_merchant: merchant with highest total spend

Return ONLY valid JSON, no explanation."""
        
        try:
            response = llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1].lstrip("json").strip()
            spending_analysis = json.loads(content)
        except Exception as e:
            spending_analysis = {
                "total_transactions": len(transactions),
                "total_spent": sum(t.get("amount", 0) for t in transactions if t.get("type") == "debit"),
                "total_income": sum(t.get("amount", 0) for t in transactions if t.get("type") == "credit"),
                "spending_by_category": {},
                "error": str(e)
            }
        
        messages = list(state["messages"])
        messages.append(f"Transaction Analyzer: Processed {len(transactions)} transactions for {month}/{year}")
        
        logger.info("agent_activated",
                    agent="transaction_analyzer",
                    transaction_count=len(transactions),
                    poc_id="POC-02",
                    phase=5)
        
        return {
            **state,
            "transactions": transactions,
            "dashboard_data": dashboard_data if "error" not in dashboard_data else {},
            "budget_data": budget_data if isinstance(budget_data, list) else [],
            "spending_analysis": spending_analysis,
            "errors": errors,
            "messages": messages
        }

# ─── Agent 2: Budget Advisor ───────────────────────────────────────────────────

@traceable(name="budget_advisor", project_name="AI-Readiness-POC-02-P5")
def budget_advisor(state: FinancialHealthState) -> FinancialHealthState:
    """Compares actual spending to budgets and identifies over/under budget categories."""
    with tracer.start_as_current_span("agent.budget_advisor.activate") as span:
        span.set_attribute("poc_id", "POC-02")
        
        spending = state["spending_analysis"]
        budget_data = state["budget_data"]
        
        llm = _get_llm()
        
        prompt = f"""You are a Budget Advisor. Compare actual spending to budget limits.

Spending Analysis:
{json.dumps(spending, indent=2)}

Budget Data:
{json.dumps(budget_data[:10], indent=2)}

Provide a JSON analysis with:
- over_budget_categories: list of categories where spent > limit (include category, spent, limit, overage_amount, overage_percent)
- under_budget_categories: list of categories with >20% budget remaining
- no_budget_categories: list of spending categories with no budget set
- total_budget_utilization: average utilization across all budgeted categories (percent)
- budget_health_score: 0-100 score (100=all under budget, 0=all exceeded)
- recommendations: list of 2-3 specific budget adjustment recommendations

Return ONLY valid JSON."""
        
        try:
            response = llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1].lstrip("json").strip()
            budget_analysis = json.loads(content)
        except Exception as e:
            budget_analysis = {
                "over_budget_categories": [],
                "under_budget_categories": [],
                "no_budget_categories": [],
                "total_budget_utilization": 0,
                "budget_health_score": 50,
                "recommendations": ["Unable to analyze budget data"],
                "error": str(e)
            }
        
        messages = list(state["messages"])
        messages.append(f"Budget Advisor: Analyzed {len(budget_data)} budget categories")
        
        logger.info("agent_activated",
                    agent="budget_advisor",
                    budget_count=len(budget_data),
                    poc_id="POC-02",
                    phase=5)
        
        return {**state, "budget_analysis": budget_analysis, "messages": messages}

# ─── Agent 3: Savings Optimizer ────────────────────────────────────────────────

@traceable(name="savings_optimizer", project_name="AI-Readiness-POC-02-P5")
def savings_optimizer(state: FinancialHealthState) -> FinancialHealthState:
    """Calculates savings rate and generates personalized savings improvement recommendations."""
    with tracer.start_as_current_span("agent.savings_optimizer.activate") as span:
        span.set_attribute("poc_id", "POC-02")
        
        spending = state["spending_analysis"]
        budget = state["budget_analysis"]
        dashboard = state["dashboard_data"]
        
        total_income = spending.get("total_income", dashboard.get("monthly_income", 0))
        total_spent = spending.get("total_spent", dashboard.get("monthly_expenses", 0))
        savings_rate = ((total_income - total_spent) / total_income * 100) if total_income > 0 else 0
        
        llm = _get_llm()
        
        prompt = f"""You are a Savings Optimizer. Generate personalized savings recommendations.

Current Financial Data:
- Monthly Income: ₹{total_income:,.2f}
- Monthly Expenses: ₹{total_spent:,.2f}
- Current Savings Rate: {savings_rate:.1f}%
- Spending by Category: {json.dumps(spending.get('spending_by_category', {}), indent=2)}
- Over-budget categories: {json.dumps(budget.get('over_budget_categories', []), indent=2)}

Using the 50/30/20 rule as a framework (50% needs, 30% wants, 20% savings):

Generate 5-7 specific, actionable savings recommendations as a JSON list.
Each recommendation should be a string describing ONE specific action.
Focus on:
1. Which categories to reduce and by how much
2. Expected monthly savings from each action
3. One stretch goal (if savings rate < 20%)

Return ONLY a JSON list of strings. Example:
["Reduce food spending by ₹2000/month by meal prepping instead of food delivery apps",
 "Cancel unused entertainment subscriptions to save ₹500/month"]"""
        
        try:
            response = llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1].lstrip("json").strip()
            recommendations = json.loads(content)
            if not isinstance(recommendations, list):
                recommendations = [str(recommendations)]
        except Exception:
            recommendations = [
                f"Your current savings rate is {savings_rate:.1f}%. Target 20% or above.",
                "Review your top spending categories for reduction opportunities.",
                "Set budget alerts to be notified before overspending."
            ]
        
        messages = list(state["messages"])
        messages.append(f"Savings Optimizer: Generated {len(recommendations)} recommendations. Current savings rate: {savings_rate:.1f}%")
        
        logger.info("agent_activated",
                    agent="savings_optimizer",
                    savings_rate=round(savings_rate, 2),
                    recommendations_count=len(recommendations),
                    poc_id="POC-02",
                    phase=5)
        
        return {**state, "savings_recommendations": recommendations, "messages": messages}

# ─── Agent 4: Report Generator ──────────────────────────────────────────────────

@traceable(name="report_generator", project_name="AI-Readiness-POC-02-P5")
def report_generator(state: FinancialHealthState) -> FinancialHealthState:
    """Synthesizes all analyses into a comprehensive, human-readable financial health report."""
    with tracer.start_as_current_span("agent.report_generator.activate") as span:
        span.set_attribute("poc_id", "POC-02")
        
        spending = state["spending_analysis"]
        budget = state["budget_analysis"]
        recommendations = state["savings_recommendations"]
        month = state["report_month"]
        year = state["report_year"]
        
        llm = _get_llm()
        
        prompt = f"""You are a Report Generator. Create a professional Financial Health Report.

Month: {month}/{year}

TRANSACTION ANALYSIS:
{json.dumps(spending, indent=2)}

BUDGET ANALYSIS:
{json.dumps(budget, indent=2)}

SAVINGS RECOMMENDATIONS:
{json.dumps(recommendations, indent=2)}

Generate a structured Financial Health Report in Markdown format with these sections:
1. **Executive Summary** (2-3 sentences with key financial metrics)
2. **Income & Expense Overview** (table with income, expenses, savings)
3. **Spending Analysis** (top categories, notable patterns)
4. **Budget Performance** (which budgets were on track vs exceeded)
5. **Savings Optimizer Recommendations** (numbered list from savings_recommendations)
6. **Action Items for Next Month** (3-5 concrete steps)
7. **Financial Health Score** (0-100 with brief justification)

Use ₹ for amounts. Be specific with numbers. Keep a professional yet approachable tone."""
        
        response = llm.invoke(prompt)
        final_report = response.content
        
        messages = list(state["messages"])
        messages.append(f"Report Generator: Financial health report generated ({len(final_report)} characters)")
        
        logger.info("agent_activated",
                    agent="report_generator",
                    report_length=len(final_report),
                    poc_id="POC-02",
                    phase=5)
        
        return {
            **state,
            "final_report": final_report,
            "report_status": "complete",
            "messages": messages
        }
```

### Step 3: Write `multi_agent/graph.py`

```python
# multi_agent/graph.py
import os
import structlog
from langgraph.graph import StateGraph, END
from langsmith import traceable
from opentelemetry import trace
from dotenv import load_dotenv

from multi_agent.state import FinancialHealthState, initial_state
from multi_agent.agents import (
    transaction_analyzer, budget_advisor,
    savings_optimizer, report_generator
)

load_dotenv()

logger = structlog.get_logger()
tracer = trace.get_tracer("poc-02-multiagent")

def should_continue_after_analysis(state: FinancialHealthState) -> str:
    """Conditional edge: if transaction analysis failed critically, skip to report."""
    if state["report_status"] == "error":
        return "report_generator"
    if len(state["errors"]) > 2:
        return "report_generator"  # Too many errors — generate partial report
    return "budget_advisor"

def build_financial_report_graph() -> StateGraph:
    workflow = StateGraph(FinancialHealthState)
    
    # Add nodes
    workflow.add_node("transaction_analyzer", transaction_analyzer)
    workflow.add_node("budget_advisor", budget_advisor)
    workflow.add_node("savings_optimizer", savings_optimizer)
    workflow.add_node("report_generator", report_generator)
    
    # Set entry point
    workflow.set_entry_point("transaction_analyzer")
    
    # Conditional edge after transaction analysis
    workflow.add_conditional_edges(
        "transaction_analyzer",
        should_continue_after_analysis,
        {
            "budget_advisor": "budget_advisor",
            "report_generator": "report_generator"
        }
    )
    
    # Linear edges for remaining agents
    workflow.add_edge("budget_advisor", "savings_optimizer")
    workflow.add_edge("savings_optimizer", "report_generator")
    workflow.add_edge("report_generator", END)
    
    return workflow.compile()

@traceable(name="financial_health_report", project_name="AI-Readiness-POC-02-P5")
def generate_financial_report(user_id: int, report_month: int, report_year: int) -> FinancialHealthState:
    with tracer.start_as_current_span("graph.execute") as span:
        span.set_attribute("user_id", user_id)
        span.set_attribute("report_month", report_month)
        span.set_attribute("report_year", report_year)
        span.set_attribute("poc_id", "POC-02")
        span.set_attribute("phase", 5)
        
        logger.info("report_generation_started",
                    user_id=user_id,
                    month=report_month,
                    year=report_year,
                    poc_id="POC-02",
                    phase=5)
        
        graph = build_financial_report_graph()
        state = initial_state(user_id, report_month, report_year)
        
        final_state = graph.invoke(state)
        
        logger.info("report_generation_completed",
                    user_id=user_id,
                    status=final_state["report_status"],
                    agents_activated=len(final_state["messages"]),
                    poc_id="POC-02",
                    phase=5)
        
        span.set_attribute("status", final_state["report_status"])
        return final_state
```

### Step 4: Write `multi_agent/report_runner.py`

```python
# multi_agent/report_runner.py
import sys
from multi_agent.graph import generate_financial_report

if __name__ == "__main__":
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    month = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    year = int(sys.argv[3]) if len(sys.argv) > 3 else 2026
    
    print(f"Generating Financial Health Report for User {user_id} — {month}/{year}")
    print("=" * 60)
    
    result = generate_financial_report(user_id, month, year)
    
    print("\nAgent Execution Log:")
    for msg in result["messages"]:
        print(f"  ✓ {msg}")
    
    if result["errors"]:
        print("\nErrors encountered:")
        for err in result["errors"]:
            print(f"  ✗ {err}")
    
    print("\n" + "=" * 60)
    print("FINANCIAL HEALTH REPORT")
    print("=" * 60)
    print(result["final_report"])
```

---

## 9. Logging & Observability Requirements

| Event | Level | Required Fields |
|-------|-------|----------------|
| Report generation started | INFO | user_id, month, year, poc_id, phase |
| Agent activated | INFO | agent name, poc_id, phase, (agent-specific metrics) |
| Report generation completed | INFO | user_id, status, agents_activated, poc_id, phase |

**OTel spans required:**
- `graph.execute` — attributes: user_id, report_month, report_year, poc_id, phase, status
- `agent.transaction_analyzer.activate` — attributes: user_id, poc_id
- `agent.budget_advisor.activate` — attributes: poc_id
- `agent.savings_optimizer.activate` — attributes: poc_id
- `agent.report_generator.activate` — attributes: poc_id

**LangSmith:** Each agent function is `@traceable`. The full graph shows as a tree of 4 agent traces under one parent `financial_health_report` trace.

---

## 10. Test Case Summary

| # | ID | Category | Description |
|---|-----|---------|-------------|
| 1 | TC-02-P5-STATE-01 | State Schema | TypedDict has all 12 required fields |
| 2 | TC-02-P5-STATE-02 | State Schema | initial_state initializes correctly |
| 3 | TC-02-P5-STATE-03 | State Schema | State updated without mutating original |
| 4 | TC-02-P5-STATE-04 | State Schema | State persists across nodes |
| 5 | TC-02-P5-AGENT-01 | Individual Agent | Transaction Analyzer fetches and analyzes data |
| 6 | TC-02-P5-AGENT-02 | Individual Agent | Transaction Analyzer handles API errors |
| 7 | TC-02-P5-AGENT-03 | Individual Agent | Budget Advisor identifies over-budget categories |
| 8 | TC-02-P5-AGENT-04 | Individual Agent | Budget Advisor produces health score 0-100 |
| 9 | TC-02-P5-AGENT-05 | Individual Agent | Savings Optimizer generates recommendations list |
| 10 | TC-02-P5-AGENT-06 | Individual Agent | Savings Optimizer calculates savings rate |
| 11 | TC-02-P5-AGENT-07 | Individual Agent | Report Generator produces markdown report |
| 12 | TC-02-P5-AGENT-08 | Individual Agent | Report Generator includes financial health score |
| 13 | TC-02-P5-ROUTE-01 | Supervisor Routing | Graph routes to budget_advisor after analysis |
| 14 | TC-02-P5-ROUTE-02 | Supervisor Routing | Graph routes to report_generator on error |
| 15 | TC-02-P5-ROUTE-03 | Supervisor Routing | should_continue function returns correct node name |
| 16 | TC-02-P5-ROUTE-04 | Supervisor Routing | All 4 nodes present in compiled graph |
| 17 | TC-02-P5-ROUTE-05 | Supervisor Routing | Entry point is transaction_analyzer |
| 18 | TC-02-P5-ROUTE-06 | Supervisor Routing | Graph ends at END after report_generator |
| 19 | TC-02-P5-E2E-01 | End-to-End | Full graph executes without exception |
| 20 | TC-02-P5-E2E-02 | End-to-End | final_report is non-empty string |
| 21 | TC-02-P5-E2E-03 | End-to-End | All 4 messages logged (one per agent) |
| 22 | TC-02-P5-E2E-04 | End-to-End | report_status is "complete" |
| 23 | TC-02-P5-E2E-05 | End-to-End | LangSmith traces all 4 agents |
| 24 | TC-02-P5-E2E-06 | End-to-End | spending_analysis contains total_spent |
| 25 | TC-02-P5-E2E-07 | End-to-End | savings_recommendations is non-empty list |

---

## 11. Submission Checklist

- [ ] `FinancialHealthState` TypedDict with all 12 fields
- [ ] `initial_state()` function sets all fields to empty defaults
- [ ] All 4 agent functions decorated with `@traceable`
- [ ] Each agent updates state with `{**state, new_field: value}` pattern
- [ ] `should_continue_after_analysis()` conditional edge function
- [ ] Graph compiled with correct node connections
- [ ] `generate_financial_report()` runs the full pipeline
- [ ] Final report in Markdown format with 7 required sections
- [ ] LangSmith project `AI-Readiness-POC-02-P5` shows 4-agent trace tree
- [ ] OTel span `graph.execute` with status attribute
- [ ] At least 18 of 25 test cases pass

---

## 12. Common Mistakes & Tips

| Mistake | Fix |
|---------|-----|
| Mutating state directly | Always use `{**state, field: new_value}` — never modify state in-place |
| LLM returns invalid JSON | Add try/except with fallback defaults; strip markdown code fences |
| Graph hangs in infinite loop | Ensure all conditional edges have matching keys in the dict |
| Agent uses wrong state field | Print state keys at each node during development |
| LangSmith shows flat trace (no tree) | Ensure all 4 agent functions have `@traceable` decorator |
| Savings rate calculation fails | Add `if total_income > 0:` guard before division |
