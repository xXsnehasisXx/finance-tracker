# Phase 3 Test Specifications
## POC-02 — Personal Finance Tracker & Analytics

**Total Test Cases:** 20 | **Pass Threshold:** 14 of 20 (70%)

---

## Setup

```bash
# Start Phase 1 API
cd backend && uvicorn app.main:app --port 8000 &

# Ensure Phase 2 ChromaDB is populated
python rag/ingest.py

# Set API_JWT_TOKEN in .env
# Run all Phase 3 tests
pytest tests/phase3/ -v

# Skip API-dependent tests
pytest tests/phase3/ -v -k "not running_api"
```

## Fixture

```python
import pytest
import os

@pytest.fixture
def running_api():
    import requests
    try:
        resp = requests.get(
            "http://localhost:8000/api/v1/dashboard",
            headers={"Authorization": f"Bearer {os.getenv('API_JWT_TOKEN')}"},
            timeout=3
        )
        if resp.status_code not in [200, 401]:
            pytest.skip("Phase 1 API not running")
    except Exception:
        pytest.skip("Phase 1 API not running")
```

---

## TOOL DEFINITION TESTS (4 cases)

### TC-02-P3-TOOL-01: All 5 Tools Have Name and Description
**Category:** Tool Definition | **Priority:** High

```python
def test_all_tools_have_name_and_description():
    from agent.tools import (
        get_budget_status, get_dashboard_summary,
        get_account_summary, get_transactions, search_finance_policy
    )
    
    tools = [get_budget_status, get_dashboard_summary,
             get_account_summary, get_transactions, search_finance_policy]
    
    for tool in tools:
        assert hasattr(tool, 'name'), f"Tool missing name attribute"
        assert hasattr(tool, 'description'), f"Tool {getattr(tool, 'name', '?')} missing description"
        assert len(tool.name) > 0
        assert len(tool.description) > 10
```

---

### TC-02-P3-TOOL-02: All Tools Registered in Executor
**Category:** Tool Definition | **Priority:** High

```python
def test_all_tools_registered_in_executor():
    from agent.agent import build_agent
    
    executor = build_agent()
    tool_names = {t.name for t in executor.tools}
    
    expected = {
        "get_budget_status", "get_dashboard_summary",
        "get_account_summary", "get_transactions", "search_finance_policy"
    }
    
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"
```

---

### TC-02-P3-TOOL-03: Tool Descriptions Have Usage Guidance
**Category:** Tool Definition | **Priority:** Medium

```python
def test_tool_descriptions_have_usage_guidance():
    from agent.tools import get_budget_status, get_dashboard_summary, search_finance_policy
    
    for tool in [get_budget_status, get_dashboard_summary, search_finance_policy]:
        desc = tool.description
        assert len(desc) >= 50, f"{tool.name} description too short: {len(desc)} chars"
        
        usage_indicators = ["use this", "use when", "when the user", "for questions", "get all"]
        assert any(ind in desc.lower() for ind in usage_indicators), \
            f"{tool.name} description lacks usage guidance"
```

---

### TC-02-P3-TOOL-04: Tool Accepts String Input
**Category:** Tool Definition | **Priority:** Medium

```python
def test_tool_accepts_string_input():
    from agent.tools import get_budget_status, get_dashboard_summary
    
    for tool in [get_budget_status, get_dashboard_summary]:
        try:
            result = tool.invoke("")
            assert isinstance(result, str)
        except TypeError as e:
            pytest.fail(f"{tool.name} rejected empty string input: {e}")
```

---

## TOOL EXECUTION TESTS (6 cases)

### TC-02-P3-EXEC-01: get_dashboard_summary Returns Key Metrics
**Category:** Tool Execution | **Priority:** High

```python
def test_dashboard_summary_returns_key_metrics(running_api):
    from agent.tools import get_dashboard_summary
    
    result = get_dashboard_summary.invoke("")
    
    assert isinstance(result, str)
    assert len(result) > 20
    # Should contain balance or income or expenses
    assert any(term in result.lower() for term in [
        "balance", "income", "expense", "savings", "₹", "monthly"
    ])
```

---

### TC-02-P3-EXEC-02: get_budget_status Returns Category Utilization
**Category:** Tool Execution | **Priority:** High

```python
def test_budget_status_returns_utilization(running_api):
    from agent.tools import get_budget_status
    
    result = get_budget_status.invoke("")
    
    assert isinstance(result, str)
    assert len(result) > 0
    # Either budget data or no-budget message
    assert any(term in result.lower() for term in [
        "budget", "category", "no budget", "configured", "₹", "%"
    ])
```

---

### TC-02-P3-EXEC-03: get_transactions Returns Transaction List
**Category:** Tool Execution | **Priority:** High

```python
def test_get_transactions_returns_list(running_api):
    from agent.tools import get_transactions
    
    result = get_transactions.invoke('{"category": "food"}')
    
    assert isinstance(result, str)
    assert len(result) > 0
    assert any(term in result.lower() for term in [
        "transaction", "debit", "credit", "food", "no transactions", "₹"
    ])
```

---

### TC-02-P3-EXEC-04: search_finance_policy Returns Manual Content
**Category:** Tool Execution | **Priority:** High

```python
def test_search_finance_policy_returns_manual_content():
    from agent.tools import search_finance_policy
    
    result = search_finance_policy.invoke("What account types are supported?")
    
    assert isinstance(result, str)
    assert len(result) > 20
    assert any(t in result.lower() for t in ["savings", "checking", "credit", "account"])
```

---

### TC-02-P3-EXEC-05: Tool Handles 404 Gracefully
**Category:** Tool Execution | **Priority:** High

```python
def test_tool_handles_404_gracefully(running_api):
    from agent.tools import get_account_summary
    
    result = get_account_summary.invoke("99999")
    
    assert isinstance(result, str)
    assert any(phrase in result.lower() for phrase in [
        "not found", "error", "account 99999", "could not"
    ])
```

---

### TC-02-P3-EXEC-06: Tool Handles API Unavailable
**Category:** Tool Execution | **Priority:** Medium

```python
def test_tool_handles_api_unavailable(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "http://localhost:9999/api/v1")
    
    import importlib
    import agent.tools as tools
    importlib.reload(tools)
    
    result = tools.get_dashboard_summary.invoke("")
    
    assert isinstance(result, str)
    assert any(phrase in result.lower() for phrase in [
        "unavailable", "error", "connection", "could not"
    ])
```

---

## CONTEXT MANAGEMENT TESTS (4 cases)

### TC-02-P3-CTX-01: System Prompt Contains Role Definition
**Category:** Context Management | **Priority:** High

```python
def test_system_prompt_contains_role():
    from agent.prompts import FINANCE_AGENT_SYSTEM_PROMPT
    
    prompt = FINANCE_AGENT_SYSTEM_PROMPT.lower()
    
    assert "finance" in prompt or "financial" in prompt
    assert "assistant" in prompt
    assert len(FINANCE_AGENT_SYSTEM_PROMPT) > 200
    assert "when" in prompt  # Tool selection guidance
```

---

### TC-02-P3-CTX-02: Long Response Is Summarized
**Category:** Context Management | **Priority:** High

```python
def test_long_response_is_summarized():
    from agent.summarizer import summarize_text
    
    long_text = "Budget category: food. Spent: ₹2000. Limit: ₹10000. " * 60
    assert len(long_text) > 2000
    
    summary = summarize_text(long_text)
    
    assert isinstance(summary, str)
    assert len(summary) < len(long_text), "Summary must be shorter than original"
    assert len(summary) > 0
```

---

### TC-02-P3-CTX-03: Short Response Not Summarized
**Category:** Context Management | **Priority:** Medium

```python
def test_short_response_not_summarized():
    from agent.summarizer import _summarize_if_long
    
    short_text = "Food budget: ₹10,000. Spent: ₹7,500. Remaining: ₹2,500. Utilization: 75%."
    assert len(short_text) < 2000
    
    result = _summarize_if_long(short_text)
    assert result == short_text  # Must be returned unchanged
```

---

### TC-02-P3-CTX-04: Prompt Template Renders Correctly
**Category:** Context Management | **Priority:** Medium

```python
def test_prompt_template_renders_correctly():
    from langchain.prompts import PromptTemplate
    from agent.prompts import FINANCE_AGENT_SYSTEM_PROMPT
    
    prompt = PromptTemplate.from_template(
        FINANCE_AGENT_SYSTEM_PROMPT + """

Tools: {tools}
Tool names: {tool_names}
Question: {input}
Thought: {agent_scratchpad}"""
    )
    
    rendered = prompt.format(
        tools="tool descriptions",
        tool_names="get_budget_status, get_dashboard_summary",
        input="Am I over budget on food?",
        agent_scratchpad=""
    )
    
    assert "Am I over budget on food?" in rendered
    assert "get_budget_status" in rendered
    assert len(rendered) > 0
```

---

## END-TO-END REASONING TESTS (6 cases)

### TC-02-P3-E2E-01: Agent Answers Budget Status Query
**Category:** End-to-End | **Priority:** High

```python
def test_agent_answers_budget_status_query(running_api):
    from agent.agent import build_agent, run_agent
    
    executor = build_agent()
    result = run_agent("Am I over budget on food this month?", executor)
    
    output = result.get("output", "").lower()
    assert len(output) > 10
    assert any(term in output for term in [
        "food", "budget", "₹", "spent", "no budget", "configured"
    ])
```

---

### TC-02-P3-E2E-02: Agent Uses Multiple Tools for Compound Query
**Category:** End-to-End | **Priority:** High

```python
def test_agent_uses_multiple_tools_for_compound_query(running_api):
    from agent.agent import build_agent, run_agent
    
    executor = build_agent()
    result = run_agent(
        "What is my savings rate and how is savings rate calculated?",
        executor
    )
    
    steps = result.get("intermediate_steps", [])
    tool_names_used = [step[0].tool for step in steps]
    
    # Should use dashboard tool AND policy/RAG tool
    assert len(tool_names_used) >= 2
    assert "get_dashboard_summary" in tool_names_used or "get_budget_status" in tool_names_used
    assert "search_finance_policy" in tool_names_used
```

---

### TC-02-P3-E2E-03: Agent Answers Policy-Only Query with RAG Tool
**Category:** End-to-End | **Priority:** High

```python
def test_agent_answers_policy_query_with_rag_tool():
    from agent.agent import build_agent, run_agent
    
    executor = build_agent()
    result = run_agent("What transaction categories are available?", executor)
    
    steps = result.get("intermediate_steps", [])
    tool_names_used = [step[0].tool for step in steps]
    
    assert "search_finance_policy" in tool_names_used
    output = result.get("output", "").lower()
    assert any(cat in output for cat in ["food", "transport", "utilities"])
```

---

### TC-02-P3-E2E-04: Agent Answers Dashboard Query
**Category:** End-to-End | **Priority:** High

```python
def test_agent_answers_dashboard_query(running_api):
    from agent.agent import build_agent, run_agent
    
    executor = build_agent()
    result = run_agent("What is my total balance across all accounts?", executor)
    
    output = result.get("output", "")
    assert len(output) > 10
    assert any(term in output.lower() for term in ["balance", "₹", "account", "total"])
```

---

### TC-02-P3-E2E-05: Agent Handles Ambiguous Query
**Category:** End-to-End | **Priority:** Medium

```python
def test_agent_handles_ambiguous_query():
    from agent.agent import build_agent, run_agent
    
    executor = build_agent()
    result = run_agent("Tell me about my finances", executor)
    
    output = result.get("output", "")
    assert len(output) > 10
    # Should not error out
    assert "traceback" not in output.lower()
    assert "exception" not in output.lower()
```

---

### TC-02-P3-E2E-06: Agent Reasoning Traced in LangSmith
**Category:** End-to-End | **Priority:** High

```python
def test_agent_reasoning_traced_in_langsmith():
    import os
    import time
    from langsmith import Client
    from agent.agent import build_agent, run_agent
    
    executor = build_agent()
    run_agent("What are the supported account types?", executor)
    
    time.sleep(3)
    
    client = Client(api_key=os.getenv("LANGCHAIN_API_KEY"))
    runs = list(client.list_runs(
        project_name="AI-Readiness-POC-02-P3",
        limit=3
    ))
    
    assert len(runs) > 0, "No traces found in AI-Readiness-POC-02-P3"
```
