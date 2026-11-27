# Budget Advisor

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Node 2 of the [LangGraph pipeline](LangGraph_Architecture.md). Code: `agents.py::budget_advisor`, `calculations.py::{budget_item_score, analyze_budgets, budget_recommendations}`.

## 1. Purpose

Compare actual spending with the user's budgets for the month: which categories are over, near, or comfortably under budget; spending with no budget; an overall budget-health score (0–100); and concrete budget advice.

## 2. Inputs and outputs

| | |
|---|---|
| **Reads from state** | `budget_data` (list of `BudgetOut` dicts from `GET /budgets?month&year`), `spending_analysis` (for categories without budgets), `messages` |
| **Writes to state** | `budget_analysis` (dict), `messages` (+1 line) |
| **LLM** | optional 2–3 sentence narrative (only if there are budgets) |
| **Tools / API** | none — uses data already fetched by the Transaction Analyzer |
| **Runs only if** | the analyzer did not signal `error` and `len(errors) <= 2` |

## 3. Processing

```python
analysis = calc.analyze_budgets(state["budget_data"], state["spending_analysis"])
analysis["recommendations"] = calc.budget_recommendations(analysis)
story = narrate(ctx, "Budget Advisor", "Explain how the user is doing against their budgets.", analysis) if state["budget_data"] else None
```

### `analyze_budgets`
For each budget `b`: `util = b.utilization_percent` (from the API, or `spent/limit×100` if missing). Classification:

| Utilization | Bucket | Extra fields |
|---|---|---|
| ≥ 100 | `over_budget_categories` | `overage_amount = spent − limit`, `overage_percent = util − 100` |
| ≥ 80 and < 100 | `warning_categories` | `remaining = limit − spent` |
| < 80 | `ok` (internal) → `under_budget_categories` only if `remaining > 20 %` of the limit | `remaining` |

Each row: `{category, spent, limit, utilization_percent, …}` (floats, 2 dp from `Decimal`).

Other outputs:

| Key | Meaning |
|---|---|
| `no_budget_categories` | categories with spending > 0 in `spending_analysis` but no budget |
| `total_budget_utilization` | `Σspent / Σlimit × 100` over budgeted categories |
| `budget_health_score` | mean of per-budget scores, rounded half-up to an integer, clamped 0–100; **50** if there are no budgets |
| `has_budgets` | `bool(budget_data)` |

### Per-budget score (`budget_item_score`)
```
util <= 80          -> 100
80 < util <= 100    -> 100 − (util − 80) × 2.5     (falls linearly to 50 at 100%)
util > 100          -> max(0, 50 − (util − 100))   (reaches 0 at 150%)
```
Example: 90 % → 75; 100 % → 50; 120 % → 30. (`test_budget_item_score_curve`.)

### `budget_recommendations` (at most 6)
* Over budget: "<Cat> is over budget by ₹X (Y% above the ₹L limit). Cut the remaining <cat> spending, or raise the limit to ₹… if this level is unavoidable."
* Warning: "<Cat> has used P% of its budget; only ₹R is left for the rest of the month."
* Up to 2 unbudgeted categories: "Set a monthly budget for <Cat>: you spent ₹S there with no limit in place."
* No budgets at all: "No budgets are set for this month. Start with budgets for your top two spending categories."

### Narrative
`narrate(...)` sends the whole `analysis` dict as JSON facts. The text is kept only if every significant number appears in the facts ([Report_Generator §5](Report_Generator.md)).

## 4. Output example (illustrative)

```python
{"over_budget_categories": [{"category": "entertainment", "spent": 2600.0, "limit": 2000.0, "utilization_percent": 130.0,
                             "overage_amount": 600.0, "overage_percent": 30.0}],
 "warning_categories": [{"category": "food", "spent": 8500.0, "limit": 10000.0, "utilization_percent": 85.0, "remaining": 1500.0}],
 "under_budget_categories": [], "no_budget_categories": [{"category": "health", "spent": 1200.0}],
 "total_budget_utilization": 92.5, "budget_health_score": 54, "has_budgets": True, "recommendations": ["..."]}
```
Audit message: `"Budget Advisor: Analyzed 2 budget categories. Health score: 54"` (per-budget scores: entertainment 130 % → 20, food 85 % → 87.5; mean 53.75 → 54).

## 5. Relationship to the backend alerts

The advisor re-derives buckets from utilization numbers with the **same thresholds** as the backend (80 % / 100 %), but it does not read `BudgetAlert` rows; `has_alert` in the API is not used here.

## 6. Tests

`test_agent_03_04_budget_advisor_over_budget_and_score_range`, `test_analyze_budgets_over_warning_ok_and_score`, `test_budget_item_score_curve`, `test_nodes_never_mutate_their_input_state`.
