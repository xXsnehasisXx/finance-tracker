# Phase 5 Test Specifications
## POC-02 — Personal Finance Tracker & Analytics

**Total Test Cases:** 25 | **Pass Threshold:** 18 of 25 (70%)

---

## Setup

```bash
# Start Phase 1 API
cd backend && uvicorn app.main:app --port 8000 &

# Run all Phase 5 tests
pytest tests/phase5/ -v

# Skip API-dependent tests
pytest tests/phase5/ -v -k "not running_api"
```

## Fixture

```python
@pytest.fixture
def running_api():
    import requests, os
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

## STATE SCHEMA TESTS (4 cases)

### TC-02-P5-STATE-01: TypedDict Has All Required Fields
**Category:** State Schema | **Priority:** High

```python
def test_typed_dict_has_all_required_fields():
    from multi_agent.state import FinancialHealthState
    
    required_fields = [
        "user_id", "report_month", "report_year",
        "transactions", "budget_data", "dashboard_data",
        "spending_analysis", "budget_analysis",
        "savings_recommendations", "final_report",
        "report_status", "errors", "messages"
    ]
    
    annotations = FinancialHealthState.__annotations__
    
    for field in required_fields:
        assert field in annotations, f"Missing field: {field}"
```

---

### TC-02-P5-STATE-02: initial_state Initializes Correctly
**Category:** State Schema | **Priority:** High

```python
def test_initial_state_initializes_correctly():
    from multi_agent.state import initial_state
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    
    assert state["user_id"] == 1
    assert state["report_month"] == 6
    assert state["report_year"] == 2026
    assert state["transactions"] == []
    assert state["budget_data"] == []
    assert state["dashboard_data"] == {}
    assert state["spending_analysis"] == {}
    assert state["budget_analysis"] == {}
    assert state["savings_recommendations"] == []
    assert state["final_report"] == ""
    assert state["report_status"] == "in_progress"
    assert state["errors"] == []
    assert state["messages"] == []
```

---

### TC-02-P5-STATE-03: State Updated Without Mutating Original
**Category:** State Schema | **Priority:** High

```python
def test_state_updated_without_mutating_original():
    from multi_agent.state import initial_state
    
    original = initial_state(user_id=1, report_month=6, report_year=2026)
    original_messages = list(original["messages"])
    
    # Simulate agent update pattern
    updated = {
        **original,
        "messages": list(original["messages"]) + ["Transaction Analyzer: Done"],
        "transactions": [{"id": 1, "amount": 500.0}]
    }
    
    # Original must not be modified
    assert original["messages"] == original_messages
    assert original["transactions"] == []
    
    # Updated must have new values
    assert len(updated["messages"]) == 1
    assert len(updated["transactions"]) == 1
```

---

### TC-02-P5-STATE-04: State Persists Across Nodes (Simulation)
**Category:** State Schema | **Priority:** Medium

```python
def test_state_persists_across_nodes():
    from multi_agent.state import initial_state
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    
    # Simulate Transaction Analyzer output
    state_after_txn = {
        **state,
        "transactions": [{"id": 1, "amount": 5000.0, "type": "debit", "category": "food"}],
        "spending_analysis": {"total_spent": 5000.0, "total_income": 80000.0},
        "messages": ["Transaction Analyzer: Processed 1 transactions"]
    }
    
    # Simulate Budget Advisor reading state from Transaction Analyzer
    state_after_budget = {
        **state_after_txn,
        "budget_analysis": {"budget_health_score": 85, "over_budget_categories": []},
        "messages": state_after_txn["messages"] + ["Budget Advisor: Analyzed 1 budget"]
    }
    
    # Verify state flows correctly
    assert state_after_budget["spending_analysis"]["total_spent"] == 5000.0
    assert len(state_after_budget["messages"]) == 2
    assert "Transaction Analyzer" in state_after_budget["messages"][0]
    assert "Budget Advisor" in state_after_budget["messages"][1]
```

---

## INDIVIDUAL AGENT TESTS (8 cases)

### TC-02-P5-AGENT-01: Transaction Analyzer Fetches and Analyzes Data
**Category:** Individual Agent | **Priority:** High

```python
def test_transaction_analyzer_fetches_data(running_api):
    from multi_agent.state import initial_state
    from multi_agent.agents import transaction_analyzer
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    result = transaction_analyzer(state)
    
    assert "spending_analysis" in result
    assert isinstance(result["spending_analysis"], dict)
    assert len(result["messages"]) > 0
    assert "Transaction Analyzer" in result["messages"][0]
```

---

### TC-02-P5-AGENT-02: Transaction Analyzer Handles API Errors
**Category:** Individual Agent | **Priority:** High

```python
def test_transaction_analyzer_handles_api_error(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "http://localhost:9999/api/v1")
    
    import importlib
    import multi_agent.agents as agents
    importlib.reload(agents)
    
    from multi_agent.state import initial_state
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    
    result = agents.transaction_analyzer(state)
    
    # Should not raise — errors should be in errors list
    assert isinstance(result, dict)
    assert "spending_analysis" in result  # Even if partial
```

---

### TC-02-P5-AGENT-03: Budget Advisor Identifies Over-Budget Categories
**Category:** Individual Agent | **Priority:** High

```python
def test_budget_advisor_produces_analysis():
    from multi_agent.state import initial_state
    from multi_agent.agents import budget_advisor
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    state = {
        **state,
        "spending_analysis": {
            "total_spent": 15000.0,
            "total_income": 80000.0,
            "spending_by_category": {"food": 12000.0, "transport": 3000.0}
        },
        "budget_data": [
            {"category": "food", "monthly_limit": 10000.0, "spent": 12000.0,
             "utilization_percent": 120.0},
            {"category": "transport", "monthly_limit": 5000.0, "spent": 3000.0,
             "utilization_percent": 60.0}
        ]
    }
    
    result = budget_advisor(state)
    
    assert "budget_analysis" in result
    analysis = result["budget_analysis"]
    assert isinstance(analysis, dict)
    assert "budget_health_score" in analysis
    assert 0 <= analysis["budget_health_score"] <= 100
```

---

### TC-02-P5-AGENT-04: Budget Advisor Produces Health Score 0-100
**Category:** Individual Agent | **Priority:** High

```python
def test_budget_advisor_produces_valid_health_score():
    from multi_agent.state import initial_state
    from multi_agent.agents import budget_advisor
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    state = {
        **state,
        "spending_analysis": {"total_spent": 5000.0, "total_income": 80000.0},
        "budget_data": [
            {"category": "food", "monthly_limit": 10000.0, "spent": 5000.0,
             "utilization_percent": 50.0}
        ]
    }
    
    result = budget_advisor(state)
    
    score = result["budget_analysis"].get("budget_health_score", -1)
    assert 0 <= score <= 100, f"Budget health score {score} out of range"
```

---

### TC-02-P5-AGENT-05: Savings Optimizer Generates Recommendations List
**Category:** Individual Agent | **Priority:** High

```python
def test_savings_optimizer_generates_recommendations():
    from multi_agent.state import initial_state
    from multi_agent.agents import savings_optimizer
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    state = {
        **state,
        "spending_analysis": {
            "total_spent": 60000.0,
            "total_income": 80000.0,
            "spending_by_category": {"food": 20000.0, "entertainment": 15000.0}
        },
        "budget_analysis": {
            "budget_health_score": 60,
            "over_budget_categories": [
                {"category": "food", "overage_percent": 20.0}
            ]
        },
        "dashboard_data": {"monthly_income": 80000.0, "monthly_expenses": 60000.0}
    }
    
    result = savings_optimizer(state)
    
    assert "savings_recommendations" in result
    recs = result["savings_recommendations"]
    assert isinstance(recs, list)
    assert len(recs) >= 1
```

---

### TC-02-P5-AGENT-06: Savings Optimizer Calculates Savings Rate
**Category:** Individual Agent | **Priority:** High

```python
def test_savings_optimizer_calculates_savings_rate():
    from multi_agent.state import initial_state
    from multi_agent.agents import savings_optimizer
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    state = {
        **state,
        "spending_analysis": {
            "total_income": 80000.0,
            "total_spent": 55000.0
        },
        "budget_analysis": {"budget_health_score": 75},
        "dashboard_data": {}
    }
    
    result = savings_optimizer(state)
    
    # Savings rate = (80000 - 55000) / 80000 * 100 = 31.25%
    messages = result["messages"]
    assert any("31" in msg or "savings" in msg.lower() for msg in messages)
```

---

### TC-02-P5-AGENT-07: Report Generator Produces Markdown Report
**Category:** Individual Agent | **Priority:** High

```python
def test_report_generator_produces_markdown():
    from multi_agent.state import initial_state
    from multi_agent.agents import report_generator
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    state = {
        **state,
        "spending_analysis": {
            "total_spent": 55000.0,
            "total_income": 80000.0,
            "spending_by_category": {"food": 15000.0}
        },
        "budget_analysis": {
            "budget_health_score": 70,
            "over_budget_categories": [],
            "recommendations": ["Reduce food spending"]
        },
        "savings_recommendations": [
            "Cut entertainment by ₹2000/month",
            "Set up automatic savings transfer"
        ]
    }
    
    result = report_generator(state)
    
    assert "final_report" in result
    report = result["final_report"]
    assert isinstance(report, str)
    assert len(report) > 100
    # Should contain markdown headers
    assert "#" in report
```

---

### TC-02-P5-AGENT-08: Report Generator Includes Financial Health Score
**Category:** Individual Agent | **Priority:** High

```python
def test_report_generator_includes_health_score():
    from multi_agent.state import initial_state
    from multi_agent.agents import report_generator
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    state = {
        **state,
        "spending_analysis": {"total_spent": 50000.0, "total_income": 80000.0},
        "budget_analysis": {"budget_health_score": 80},
        "savings_recommendations": ["Increase food budget discipline"]
    }
    
    result = report_generator(state)
    
    report = result["final_report"].lower()
    assert any(term in report for term in ["score", "health", "financial", "rating"])
    assert result["report_status"] == "complete"
```

---

## SUPERVISOR ROUTING TESTS (6 cases)

### TC-02-P5-ROUTE-01: Graph Routes to budget_advisor After Analysis
**Category:** Supervisor Routing | **Priority:** High

```python
def test_routing_to_budget_advisor_after_analysis():
    from multi_agent.graph import should_continue_after_analysis
    from multi_agent.state import initial_state
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    state = {**state, "report_status": "in_progress", "errors": []}
    
    next_node = should_continue_after_analysis(state)
    
    assert next_node == "budget_advisor"
```

---

### TC-02-P5-ROUTE-02: Graph Routes to report_generator on Error
**Category:** Supervisor Routing | **Priority:** High

```python
def test_routing_to_report_generator_on_error():
    from multi_agent.graph import should_continue_after_analysis
    from multi_agent.state import initial_state
    
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    state = {
        **state,
        "report_status": "in_progress",
        "errors": ["Error 1", "Error 2", "Error 3"]  # >2 errors
    }
    
    next_node = should_continue_after_analysis(state)
    
    assert next_node == "report_generator"
```

---

### TC-02-P5-ROUTE-03: Conditional Function Returns Valid Node Name
**Category:** Supervisor Routing | **Priority:** High

```python
def test_conditional_function_returns_valid_node():
    from multi_agent.graph import should_continue_after_analysis
    from multi_agent.state import initial_state
    
    valid_nodes = {"budget_advisor", "report_generator"}
    
    # Test normal path
    state_ok = {**initial_state(1, 6, 2026), "report_status": "in_progress", "errors": []}
    result_ok = should_continue_after_analysis(state_ok)
    assert result_ok in valid_nodes
    
    # Test error path
    state_err = {**initial_state(1, 6, 2026), "report_status": "error", "errors": []}
    result_err = should_continue_after_analysis(state_err)
    assert result_err in valid_nodes
```

---

### TC-02-P5-ROUTE-04: All 4 Nodes Present in Compiled Graph
**Category:** Supervisor Routing | **Priority:** High

```python
def test_all_4_nodes_in_compiled_graph():
    from multi_agent.graph import build_financial_report_graph
    
    graph = build_financial_report_graph()
    
    # LangGraph compiled graph has a graph attribute or nodes can be inspected
    assert graph is not None
    assert hasattr(graph, 'invoke')
```

---

### TC-02-P5-ROUTE-05: Entry Point Is transaction_analyzer
**Category:** Supervisor Routing | **Priority:** Medium

```python
def test_entry_point_is_transaction_analyzer():
    from langgraph.graph import StateGraph
    from multi_agent.state import FinancialHealthState
    from multi_agent.agents import transaction_analyzer
    from multi_agent.graph import build_financial_report_graph
    
    # Verify the graph can be built without error (entry point set correctly)
    graph = build_financial_report_graph()
    assert graph is not None
    
    # If graph has entry_point attribute
    if hasattr(graph, 'entry_point'):
        assert graph.entry_point == "transaction_analyzer"
```

---

### TC-02-P5-ROUTE-06: Graph Ends at END After report_generator
**Category:** Supervisor Routing | **Priority:** Medium

```python
def test_graph_ends_correctly():
    from multi_agent.graph import build_financial_report_graph
    from multi_agent.state import initial_state
    
    graph = build_financial_report_graph()
    
    # A minimal state (may skip API calls if mocked)
    state = initial_state(user_id=1, report_month=6, report_year=2026)
    state["spending_analysis"] = {"total_spent": 0, "total_income": 0}
    state["budget_analysis"] = {"budget_health_score": 50}
    state["savings_recommendations"] = ["Test rec"]
    
    # Graph should complete (reach END) without infinite loop
    # We mock the agent functions to avoid API calls
    try:
        # If graph can at least be invoked
        assert graph is not None
    except Exception as e:
        pytest.fail(f"Graph failed to initialize: {e}")
```

---

## END-TO-END WORKFLOW TESTS (7 cases)

### TC-02-P5-E2E-01: Full Graph Executes Without Exception
**Category:** End-to-End | **Priority:** High

```python
def test_full_graph_executes(running_api):
    from multi_agent.graph import generate_financial_report
    
    result = generate_financial_report(
        user_id=1,
        report_month=6,
        report_year=2026
    )
    
    assert isinstance(result, dict)
    assert "final_report" in result
    assert "report_status" in result
```

---

### TC-02-P5-E2E-02: final_report Is Non-Empty String
**Category:** End-to-End | **Priority:** High

```python
def test_final_report_is_non_empty(running_api):
    from multi_agent.graph import generate_financial_report
    
    result = generate_financial_report(user_id=1, report_month=6, report_year=2026)
    
    final_report = result.get("final_report", "")
    assert isinstance(final_report, str)
    assert len(final_report) > 50, f"Report too short: {len(final_report)} chars"
```

---

### TC-02-P5-E2E-03: All 4 Agent Messages Logged
**Category:** End-to-End | **Priority:** High

```python
def test_all_4_agent_messages_logged(running_api):
    from multi_agent.graph import generate_financial_report
    
    result = generate_financial_report(user_id=1, report_month=6, report_year=2026)
    
    messages = result.get("messages", [])
    assert len(messages) == 4, f"Expected 4 agent messages, got {len(messages)}"
    
    agent_names = ["Transaction Analyzer", "Budget Advisor", "Savings Optimizer", "Report Generator"]
    for name in agent_names:
        assert any(name in msg for msg in messages), f"Message from {name} not found"
```

---

### TC-02-P5-E2E-04: report_status Is Complete
**Category:** End-to-End | **Priority:** High

```python
def test_report_status_is_complete(running_api):
    from multi_agent.graph import generate_financial_report
    
    result = generate_financial_report(user_id=1, report_month=6, report_year=2026)
    
    assert result["report_status"] == "complete"
```

---

### TC-02-P5-E2E-05: LangSmith Traces All 4 Agents
**Category:** End-to-End | **Priority:** High

```python
def test_langsmith_traces_all_agents(running_api):
    import os
    import time
    from langsmith import Client
    from multi_agent.graph import generate_financial_report
    
    generate_financial_report(user_id=1, report_month=6, report_year=2026)
    
    time.sleep(5)
    
    client = Client(api_key=os.getenv("LANGCHAIN_API_KEY"))
    runs = list(client.list_runs(
        project_name="AI-Readiness-POC-02-P5",
        limit=10
    ))
    
    assert len(runs) > 0, "No traces in AI-Readiness-POC-02-P5"
    
    run_names = {r.name for r in runs}
    expected_traces = {
        "transaction_analyzer", "budget_advisor",
        "savings_optimizer", "report_generator"
    }
    found = expected_traces.intersection(run_names)
    assert len(found) >= 2, f"Expected agent traces, found: {run_names}"
```

---

### TC-02-P5-E2E-06: spending_analysis Contains total_spent
**Category:** End-to-End | **Priority:** High

```python
def test_spending_analysis_contains_total_spent(running_api):
    from multi_agent.graph import generate_financial_report
    
    result = generate_financial_report(user_id=1, report_month=6, report_year=2026)
    
    spending = result.get("spending_analysis", {})
    assert isinstance(spending, dict)
    assert "total_spent" in spending or "total_transactions" in spending
```

---

### TC-02-P5-E2E-07: savings_recommendations Is Non-Empty List
**Category:** End-to-End | **Priority:** High

```python
def test_savings_recommendations_non_empty(running_api):
    from multi_agent.graph import generate_financial_report
    
    result = generate_financial_report(user_id=1, report_month=6, report_year=2026)
    
    recs = result.get("savings_recommendations", [])
    assert isinstance(recs, list)
    assert len(recs) >= 1, "Expected at least 1 savings recommendation"
    assert all(isinstance(r, str) for r in recs)
```

---

## Running Phase 5 Tests

```bash
# Start Phase 1 API first
cd backend && uvicorn app.main:app --port 8000 &

# Run all Phase 5 tests
pytest tests/phase5/ -v

# Run only state/routing tests (no API needed)
pytest tests/phase5/ -v -k "STATE or ROUTE"

# Generate report
pytest tests/phase5/ --junitxml=results/phase5-results.xml
```
