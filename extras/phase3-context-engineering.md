# Phase 3: Context Engineering & Tool Integration
## POC-02 — Personal Finance Tracker & Analytics

**Phase Weight:** 20% | **Duration:** 5 days | **Test Cases:** 20

---

## 1. Phase Overview

Extend the Phase 2 chatbot into a live financial data agent. Users can now ask "Am I over budget on food this month?" and the agent will call the Phase 1 REST API to fetch actual spending data, combine it with Phase 2 RAG guidance, and provide a data-grounded answer. This phase introduces LangChain tool-calling, ReAct reasoning, and a system prompt with financial advisor context.

### 5-Day Schedule
| Day | Focus |
|-----|-------|
| Day 1 | Understand tool-calling agents, ReAct loop, context injection |
| Day 2 | Write `agent/tools.py` — 5 tools wrapping Phase 1 API endpoints |
| Day 3 | Write `agent/agent.py` — system prompt, ReAct executor, LangSmith tracing |
| Day 4 | Write `agent/summarizer.py` for long API responses, test tool calls |
| Day 5 | End-to-end testing, fix tool errors, run all 20 test cases |

---

## 2. Prerequisites
- Phase 1 API running on `http://localhost:8000`
- Phase 2 ChromaDB populated (`python rag/ingest.py`)
- `API_JWT_TOKEN` in `.env` (obtain via POST /api/v1/auth/login)
- LangSmith project `AI-Readiness-POC-02-P3`

---

## 3. Concepts to Self-Learn
| Concept | Search Term |
|---------|-------------|
| LangChain tool calling | "LangChain @tool decorator tutorial" |
| ReAct agent pattern | "ReAct reasoning acting LangChain" |
| System prompt engineering | "LangChain system prompt context injection" |
| LangChain agent executor | "LangChain AgentExecutor tutorial" |
| Summarization chain | "LangChain summarize chain Python" |

---

## 4. Project Structure

```
poc-02-finance-tracker/
├── agent/
│   ├── tools.py           ← 5 tool functions wrapping Phase 1 API
│   ├── agent.py           ← Build executor with system prompt
│   ├── summarizer.py      ← Summarize long API responses
│   └── prompts.py         ← System prompt template
├── rag/                   ← Phase 2 (used by search_finance_policy tool)
└── tests/phase3/
```

---

## 5. User Stories

### US-02-P3-01: Live Budget Status Query
**Priority:** Must Have | **Story Points:** 5

> As a user, I want to ask "Am I over budget on food this month?" and get a data-grounded answer that compares my actual spending against the budget.

**Given** Phase 1 API has budget and transaction data, **When** user asks the question, **Then** agent calls get_budget_status tool, retrieves actual spent vs limit, and answers with numbers.
**Given** no food budget set, **When** asked, **Then** agent says no budget configured for food.

---

### US-02-P3-02: Account Balance Query
**Priority:** Must Have | **Story Points:** 3

> As a user, I want to ask "What is my total balance across all accounts?" and get an accurate, live answer.

**Given** user has multiple accounts, **When** query sent to agent, **Then** agent calls get_account_summary tool and returns total_balance from the dashboard.

---

### US-02-P3-03: Transaction Analysis with RAG Context
**Priority:** Must Have | **Story Points:** 5

> As a user, I want to ask "How am I doing on spending and what categories should I cut?" and get live spending data combined with finance best-practice guidance.

**Given** Phase 1 data and Phase 2 knowledge base available, **When** compound query asked, **Then** agent uses get_dashboard_summary AND search_finance_policy tools in combination.
**Given** two tools needed, **When** executed, **Then** intermediate_steps contains at least 2 tool calls.

---

### US-02-P3-04: Finance Policy Q&A via Agent
**Priority:** Must Have | **Story Points:** 2

> As a user, I want to ask general app usage questions ("How is savings rate calculated?") and have the agent answer from the user manual.

**Given** policy question asked, **When** processed, **Then** agent uses search_finance_policy tool and returns grounded answer.

---

### US-02-P3-05: Error-Resilient Tool Execution
**Priority:** Must Have | **Story Points:** 2

> As a developer, I want all tool errors to be caught and returned as readable messages rather than crashing the agent.

**Given** API is unavailable, **When** tool called, **Then** error is caught and returned as string "Service unavailable...".
**Given** non-existent account_id queried, **When** tool called, **Then** "Account not found" returned as string.

---

## 6. Architecture Diagram

```mermaid
graph TB
    User[User Question] --> AE[AgentExecutor<br/>ReAct Loop]
    
    subgraph "LangChain Agent"
        AE --> LLM[Gemini 2.0 Flash]
        LLM -->|select tool| AE
        AE --> T1[get_budget_status<br/>GET /budgets]
        AE --> T2[get_dashboard_summary<br/>GET /dashboard]
        AE --> T3[get_account_summary<br/>GET /accounts/{id}/summary]
        AE --> T4[get_transactions<br/>GET /transactions]
        AE --> T5[search_finance_policy<br/>ChromaDB RAG]
    end
    
    T1 & T2 & T3 & T4 -->|HTTP + JWT| API[Phase 1 FastAPI :8000]
    T5 --> CDB[(ChromaDB)]
    
    AE --> LS[LangSmith Traces<br/>AI-Readiness-POC-02-P3]
    AE --> OTEL[OTel Spans]
```

---

## 7. Implementation Guide

### Step 1: Write `agent/prompts.py`

```python
# agent/prompts.py

FINANCE_AGENT_SYSTEM_PROMPT = """You are a personal finance assistant for the Finance Tracker application.
You help users understand their financial data and make informed spending decisions.

You have access to 5 tools:
1. get_budget_status — Use when the user asks about budgets, spending limits, or whether they are over/under budget for a category
2. get_dashboard_summary — Use when the user asks about total balance, monthly income/expenses, savings rate, or top spending categories
3. get_account_summary — Use when the user asks about a specific account's balance, transaction history, or spending breakdown
4. get_transactions — Use when the user asks to see or filter transactions by date, category, or account
5. search_finance_policy — Use when the user asks how something works in the app, about categories, how to set budgets, how alerts work, or wants guidance on financial best practices

Tool selection guidelines:
- Questions about live data (balances, spending, budgets this month) → use API tools (1-4)
- Questions about how the app works, finance concepts, or best practices → use search_finance_policy (tool 5)
- Complex questions needing both live data AND guidance → use both API tools AND search_finance_policy

Always be specific: if you have the data, show numbers (amounts in ₹). If the user is over budget, say so clearly.
If you cannot answer with the available tools, explain what information is missing.
"""
```

### Step 2: Write `agent/summarizer.py`

```python
# agent/summarizer.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.summarize import load_summarize_chain
from langchain.docstore.document import Document
import os
from opentelemetry import trace

tracer = trace.get_tracer("poc-02-agent")

def summarize_text(text: str) -> str:
    """Summarize long text using Gemini. Returns original if under 2000 chars."""
    if len(text) <= 2000:
        return text
    
    with tracer.start_as_current_span("agent.summarize") as span:
        span.set_attribute("input_length", len(text))
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0
        )
        
        docs = [Document(page_content=text)]
        chain = load_summarize_chain(llm, chain_type="stuff")
        summary = chain.run(docs)
        
        span.set_attribute("output_length", len(summary))
        return summary

def _summarize_if_long(text: str) -> str:
    """Helper used by tools — returns text unchanged if short."""
    if len(text) <= 2000:
        return text
    return summarize_text(text)
```

### Step 3: Write `agent/tools.py`

```python
# agent/tools.py
import os
import json
import requests
import structlog
from langchain.tools import tool
from opentelemetry import trace
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()
tracer = trace.get_tracer("poc-02-agent")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
JWT_TOKEN = os.getenv("API_JWT_TOKEN", "")

def _get_headers():
    return {"Authorization": f"Bearer {JWT_TOKEN}"}

def _api_get(path: str) -> dict:
    """Make a GET request to the Phase 1 API with error handling."""
    with tracer.start_as_current_span("api.call") as span:
        span.set_attribute("path", path)
        try:
            resp = requests.get(f"{API_BASE_URL}{path}", headers=_get_headers(), timeout=10)
            span.set_attribute("status_code", resp.status_code)
            if resp.status_code == 404:
                return {"error": "not_found", "message": f"Resource not found: {path}"}
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"error": "unavailable", "message": "Finance API service unavailable. Please ensure the backend is running."}
        except requests.exceptions.Timeout:
            return {"error": "timeout", "message": "Request timed out. Try again later."}
        except Exception as e:
            return {"error": "unknown", "message": str(e)}

def _format_currency(amount: float) -> str:
    return f"₹{amount:,.2f}"

@tool
def get_budget_status(input: str = "") -> str:
    """Use this when the user asks about budgets, spending limits, whether they are over or under budget for any category, or wants to see budget utilization. Returns all budgets with current spending and remaining amounts."""
    with tracer.start_as_current_span("agent.tool_call") as span:
        span.set_attribute("tool", "get_budget_status")
        span.set_attribute("poc_id", "POC-02")
        
        data = _api_get("/budgets")
        
        if "error" in data:
            return f"Could not retrieve budget data: {data['message']}"
        
        if not data:
            return "No budgets have been configured. Use the Budget section to set monthly spending limits."
        
        budgets = data if isinstance(data, list) else data.get("items", [])
        if not budgets:
            return "No budgets configured for any category this month."
        
        lines = ["**Current Budget Status:**\n"]
        for b in budgets:
            category = b.get("category", "unknown")
            limit = b.get("monthly_limit", 0)
            spent = b.get("spent", 0)
            remaining = b.get("remaining", limit - spent)
            utilization = b.get("utilization_percent", (spent / limit * 100) if limit > 0 else 0)
            has_alert = b.get("has_alert", False)
            
            status_icon = "🔴" if utilization >= 100 else "🟠" if utilization >= 80 else "🟢"
            alert_note = " ⚠️ ALERT TRIGGERED" if has_alert else ""
            
            lines.append(
                f"{status_icon} **{category.title()}**: Spent {_format_currency(spent)} of "
                f"{_format_currency(limit)} ({utilization:.1f}% used) — "
                f"{_format_currency(remaining)} remaining{alert_note}"
            )
        
        from agent.summarizer import _summarize_if_long
        result = "\n".join(lines)
        
        logger.info("tool_executed", tool="get_budget_status", poc_id="POC-02", phase=3)
        return _summarize_if_long(result)

@tool
def get_dashboard_summary(input: str = "") -> str:
    """Use this when the user asks about their total balance, monthly income, monthly expenses, savings rate, or top spending categories. Returns the financial dashboard overview."""
    with tracer.start_as_current_span("agent.tool_call") as span:
        span.set_attribute("tool", "get_dashboard_summary")
        span.set_attribute("poc_id", "POC-02")
        
        data = _api_get("/dashboard")
        
        if "error" in data:
            return f"Could not retrieve dashboard data: {data['message']}"
        
        total_balance = data.get("total_balance", 0)
        monthly_income = data.get("monthly_income", 0)
        monthly_expenses = data.get("monthly_expenses", 0)
        savings_rate = data.get("savings_rate", 0)
        top_categories = data.get("top_3_categories", [])
        alert_count = data.get("budget_alerts_count", 0)
        
        top_cat_str = ", ".join(
            [f"{c['category']} ({_format_currency(c['amount'])})" for c in top_categories]
        ) if top_categories else "No spending recorded"
        
        summary = f"""**Financial Dashboard Summary:**
- Total Balance (all accounts): {_format_currency(total_balance)}
- Monthly Income: {_format_currency(monthly_income)}
- Monthly Expenses: {_format_currency(monthly_expenses)}
- Savings Rate: {savings_rate:.1f}%
- Top Spending Categories: {top_cat_str}
- Active Budget Alerts: {alert_count}"""
        
        logger.info("tool_executed", tool="get_dashboard_summary", poc_id="POC-02", phase=3)
        return summary

@tool
def get_account_summary(account_id: str) -> str:
    """Use this when the user asks about a specific account's details, balance, spending breakdown by category, or monthly spending trend. Input: account ID as a string (e.g., '1')."""
    with tracer.start_as_current_span("agent.tool_call") as span:
        span.set_attribute("tool", "get_account_summary")
        span.set_attribute("account_id", account_id)
        span.set_attribute("poc_id", "POC-02")
        
        data = _api_get(f"/accounts/{account_id}/summary")
        
        if "error" in data:
            if data["error"] == "not_found":
                return f"Account {account_id} not found. Please verify the account ID."
            return f"Could not retrieve account summary: {data['message']}"
        
        total_credit = data.get("total_credit", 0)
        total_debit = data.get("total_debit", 0)
        balance = data.get("balance", 0)
        spending = data.get("spending_by_category", {})
        
        spending_lines = [
            f"  - {cat.title()}: {_format_currency(amt)}"
            for cat, amt in sorted(spending.items(), key=lambda x: x[1], reverse=True)
        ] if spending else ["  - No spending recorded"]
        
        result = f"""**Account {account_id} Summary:**
- Current Balance: {_format_currency(balance)}
- Total Credits (income): {_format_currency(total_credit)}
- Total Debits (expenses): {_format_currency(total_debit)}
- Spending by Category:
{chr(10).join(spending_lines)}"""
        
        logger.info("tool_executed", tool="get_account_summary", account_id=account_id, poc_id="POC-02", phase=3)
        
        from agent.summarizer import _summarize_if_long
        return _summarize_if_long(result)

@tool
def get_transactions(input: str) -> str:
    """Use this when the user asks to see transactions, filter by category/date/type, or wants to analyze recent spending. Input: a JSON string with optional filters: {"account_id": 1, "category": "food", "date_from": "2026-06-01", "date_to": "2026-06-30", "type": "debit"}"""
    with tracer.start_as_current_span("agent.tool_call") as span:
        span.set_attribute("tool", "get_transactions")
        span.set_attribute("poc_id", "POC-02")
        
        try:
            filters = json.loads(input) if input.strip().startswith("{") else {}
        except Exception:
            filters = {}
        
        params = []
        for key in ["account_id", "category", "date_from", "date_to", "type"]:
            if key in filters and filters[key]:
                params.append(f"{key}={filters[key]}")
        
        query_string = "&".join(params)
        path = f"/transactions?{query_string}" if query_string else "/transactions"
        
        data = _api_get(path)
        
        if "error" in data:
            return f"Could not retrieve transactions: {data['message']}"
        
        items = data if isinstance(data, list) else data.get("items", [])
        
        if not items:
            return "No transactions found matching the specified filters."
        
        lines = [f"**Found {len(items)} transaction(s):**\n"]
        for t in items[:10]:
            txn_type = "💸 Debit" if t.get("type") == "debit" else "💰 Credit"
            lines.append(
                f"- {t.get('transaction_date')} | {txn_type} | "
                f"{_format_currency(t.get('amount', 0))} | "
                f"{t.get('category', 'N/A').title()} | "
                f"{t.get('description', '')[:50]}"
            )
        
        if len(items) > 10:
            lines.append(f"\n... and {len(items) - 10} more transactions.")
        
        logger.info("tool_executed", tool="get_transactions", filter_count=len(filters), poc_id="POC-02", phase=3)
        
        from agent.summarizer import _summarize_if_long
        return _summarize_if_long("\n".join(lines))

@tool
def search_finance_policy(question: str) -> str:
    """Use this when the user asks how something works in the Finance Tracker app, about transaction categories, how to set budgets, how alerts work, or wants financial advice and best practices. Searches the user manual using RAG."""
    with tracer.start_as_current_span("agent.tool_call") as span:
        span.set_attribute("tool", "search_finance_policy")
        span.set_attribute("question", question[:100])
        span.set_attribute("poc_id", "POC-02")
        
        from rag.rag_chain import build_rag_chain, ask_question
        chain = build_rag_chain()
        result = ask_question(question, chain)
        
        answer = result.get("answer", "No answer found.")
        logger.info("tool_executed", tool="search_finance_policy", poc_id="POC-02", phase=3)
        return answer
```

### Step 4: Write `agent/agent.py`

```python
# agent/agent.py
import os
import structlog
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langsmith import traceable
from opentelemetry import trace
from dotenv import load_dotenv

from agent.tools import (get_budget_status, get_dashboard_summary,
                          get_account_summary, get_transactions, search_finance_policy)
from agent.prompts import FINANCE_AGENT_SYSTEM_PROMPT

load_dotenv()

logger = structlog.get_logger()
tracer = trace.get_tracer("poc-02-agent")

TOOLS = [get_budget_status, get_dashboard_summary, get_account_summary,
         get_transactions, search_finance_policy]

REACT_PROMPT = PromptTemplate.from_template(
    FINANCE_AGENT_SYSTEM_PROMPT + """

Tools available:
{tools}

Tool names: {tool_names}

Use the following format:
Question: the user's question
Thought: consider which tool to use
Action: the tool name
Action Input: the tool input
Observation: the tool output
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now know the final answer
Final Answer: the complete answer with financial data

Question: {input}
Thought: {agent_scratchpad}"""
)

def build_agent() -> AgentExecutor:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0
    )
    
    agent = create_react_agent(llm=llm, tools=TOOLS, prompt=REACT_PROMPT)
    executor = AgentExecutor(
        agent=agent,
        tools=TOOLS,
        verbose=True,
        return_intermediate_steps=True,
        max_iterations=6,
        handle_parsing_errors=True
    )
    return executor

@traceable(name="finance_agent_query", project_name="AI-Readiness-POC-02-P3")
def run_agent(question: str, executor: AgentExecutor) -> dict:
    with tracer.start_as_current_span("agent.execute") as span:
        span.set_attribute("question", question[:100])
        span.set_attribute("poc_id", "POC-02")
        span.set_attribute("phase", 3)
        
        logger.info("agent_query_received",
                    question=question[:80],
                    poc_id="POC-02",
                    phase=3)
        
        result = executor.invoke({"input": question})
        
        steps = result.get("intermediate_steps", [])
        span.set_attribute("tool_calls_count", len(steps))
        
        logger.info("agent_query_completed",
                    tool_calls=len(steps),
                    output_length=len(result.get("output", "")),
                    poc_id="POC-02",
                    phase=3)
        
        return result
```

---

## 8. Logging & Observability Requirements

| Event | Level | Required Fields |
|-------|-------|----------------|
| Agent query received | INFO | question (truncated), poc_id, phase |
| Tool executed | INFO | tool, poc_id, phase, (tool-specific fields) |
| Agent query completed | INFO | tool_calls, output_length, poc_id, phase |
| API call failed | ERROR | path, error_type, poc_id, phase |
| RAG tool invoked | INFO | question, poc_id, phase |

**OTel spans required:**
- `agent.tool_call` — attributes: tool name, poc_id
- `agent.execute` — attributes: question, tool_calls_count, poc_id, phase
- `api.call` — attributes: path, status_code
- `agent.summarize` — attributes: input_length, output_length

---

## 9. Test Case Summary

| # | ID | Category | Description |
|---|-----|---------|-------------|
| 1 | TC-02-P3-TOOL-01 | Tool Definition | All 5 tools have name and description |
| 2 | TC-02-P3-TOOL-02 | Tool Definition | All tools registered in executor |
| 3 | TC-02-P3-TOOL-03 | Tool Definition | Tool descriptions ≥50 chars with usage guidance |
| 4 | TC-02-P3-TOOL-04 | Tool Definition | Tool accepts string input without TypeError |
| 5 | TC-02-P3-EXEC-01 | Tool Execution | get_dashboard_summary returns balance and savings rate |
| 6 | TC-02-P3-EXEC-02 | Tool Execution | get_budget_status returns category utilization |
| 7 | TC-02-P3-EXEC-03 | Tool Execution | get_transactions returns transaction list |
| 8 | TC-02-P3-EXEC-04 | Tool Execution | search_finance_policy returns manual content |
| 9 | TC-02-P3-EXEC-05 | Tool Execution | Tool handles 404 gracefully |
| 10 | TC-02-P3-EXEC-06 | Tool Execution | Tool handles API unavailable gracefully |
| 11 | TC-02-P3-CTX-01 | Context Mgmt | System prompt contains role definition |
| 12 | TC-02-P3-CTX-02 | Context Mgmt | Long response summarized |
| 13 | TC-02-P3-CTX-03 | Context Mgmt | Short response not summarized |
| 14 | TC-02-P3-CTX-04 | Context Mgmt | Prompt template renders correctly |
| 15 | TC-02-P3-E2E-01 | End-to-End | Agent answers budget status query |
| 16 | TC-02-P3-E2E-02 | End-to-End | Agent uses multiple tools for compound query |
| 17 | TC-02-P3-E2E-03 | End-to-End | Agent answers policy-only query with RAG tool |
| 18 | TC-02-P3-E2E-04 | End-to-End | Agent answers dashboard query |
| 19 | TC-02-P3-E2E-05 | End-to-End | Agent handles ambiguous query |
| 20 | TC-02-P3-E2E-06 | End-to-End | Agent reasoning traced in LangSmith |

---

## 10. Submission Checklist

- [ ] All 5 tools defined with `@tool` decorator
- [ ] Each tool has a description ≥50 chars with "Use this when" guidance
- [ ] `get_budget_status` returns category, spent, limit, and utilization_percent
- [ ] `get_dashboard_summary` returns total_balance and savings_rate
- [ ] `search_finance_policy` calls Phase 2 ChromaDB RAG chain
- [ ] All tools catch API errors and return readable error strings
- [ ] `summarizer.py` compresses responses >2000 chars
- [ ] System prompt contains tool selection guidelines
- [ ] `run_agent()` decorated with `@traceable` for LangSmith
- [ ] LangSmith project `AI-Readiness-POC-02-P3` receives traces
- [ ] At least 14 of 20 test cases pass

---

## 11. Common Mistakes & Tips

| Mistake | Fix |
|---------|-----|
| Tool description too vague | Must include "Use this when" + specific trigger conditions |
| API returns list but code expects dict | Check `isinstance(data, list)` before accessing `.get()` |
| Tool crashes on API error | Wrap requests in try/except and return error string |
| Agent loops infinitely | Set `max_iterations=6` in AgentExecutor |
| RAG chain rebuilt every tool call | Cache the chain in module-level variable or pass it in |
| JWT token not loading | Check `.env` has `API_JWT_TOKEN` and `load_dotenv()` is called |
