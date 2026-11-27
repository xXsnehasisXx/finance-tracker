# Savings Optimizer

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Node 3 of the [LangGraph pipeline](LangGraph_Architecture.md). Code: `agents.py::savings_optimizer`, `calculations.py::{savings_metrics, build_recommendations, rate_label}`.

## 1. Purpose

Measure how much the user saves and produce realistic, number-backed recommendations using the **50/30/20 framework** (needs / wants / savings) plus an emergency-fund check.

## 2. Inputs and outputs

| | |
|---|---|
| **Reads from state** | `spending_analysis`, `budget_analysis`, `dashboard_data`, `messages` |
| **Writes to state** | `savings_recommendations: list[str]` (max 8), `messages` (+1 line) |
| **LLM** | **none** — this node is fully deterministic (it does not call `narrate`) |
| **API / tools** | none |

Audit message: `"Savings Optimizer: Generated <N> recommendations. Current savings rate: <x.x>%"`.

## 3. `savings_metrics(spending, dashboard)`

| Key | Formula |
|---|---|
| `income` | `spending.total_income` (falls back to `dashboard.monthly_income`) |
| `expenses` | `spending.total_spent` (falls back to `dashboard.monthly_expenses`) |
| `saved` | `income − expenses` |
| `savings_rate` | `(income − expenses) / income × 100`, 2 dp; `0` if income ≤ 0 |
| `needs` | Σ category spend over **`NEEDS = (food, utilities, health, transport)`** |
| `wants` | Σ category spend over **`WANTS = (entertainment, other)`** |
| `needs_percent` / `wants_percent` | `needs/income×100`, `wants/income×100` |
| `savings_percent` | `saved/income×100` when income > 0 |
| `total_assets` | `dashboard.total_assets` (savings + checking balances) or `None` |
| `emergency_months` | `total_assets / expenses`, 1 dp (or `None` if no assets or expenses = 0) |

> The needs/wants mapping is a **documented simplification** (the report footnote says "Categories are grouped in a simplified way"): e.g. `food` is always a need, `other` always a want.

Targets: `TARGETS = {"needs": 50, "wants": 30, "savings": 20}`.

## 4. `build_recommendations` — rule list

Applied in order; the result is truncated to 8 entries.

1. **No income** → returns only: "No income was recorded for this month, so a savings rate cannot be calculated. Record your salary and other income to get savings advice."
2. **Savings statement:** "Your savings rate is R% (₹saved saved from ₹income of income), which is <label>. The 50/30/20 rule targets 20% or more." where label from `rate_label`: `> 30` excellent, `≥ 20` good, `≥ 10` moderate, else low.
3. If `rate < 20`: **stretch goal** "save an extra ₹(0.2×income − saved) per month to reach a 20% savings rate."
4. If `wants_percent > 30`: discretionary overspend = `wants − 0.3×income`.
5. **Trim suggestion:** the largest category among `WANTS` present → "Trimming <Cat> spending by 15% would save about ₹X per month (₹12X per year)."
6. Up to 2 over-budget categories from the Budget Advisor: "Bring <Cat> back within its budget: that alone recovers ₹overage."
7. If `needs_percent > 50`: "Essential spending (food, utilities, health, transport) is N% of income against a 50% guideline; review recurring bills for savings."
8. **Emergency fund:** if `emergency_months < 3` → target range `3×–6×` monthly expenses; else "within or above the 3 to 6 month guideline".

All amounts use `Decimal` and `inr()` formatting (`₹1,234.50`). `test_savings_metrics_and_recommendations_use_real_numbers` asserts the recommendation text contains the real computed figures.

## 5. How it interacts with other agents

* Consumes the Transaction Analyzer's `spending_by_category`/totals and the Budget Advisor's `over_budget_categories`.
* Its list is rendered in report section 5 and the first items feed section 7 (Action Items) via `calc.action_items`.
* Its `savings_rate` feeds the Report Generator's health score ([Report_Generator](Report_Generator.md)).
* The Report Generator recomputes `savings_metrics` itself (same function, same inputs) so the report never depends on a node-to-node copy of the metrics.

## 6. Example (illustrative)

Income ₹80,000, expenses ₹60,000 → saved ₹20,000, rate 25.0 % → "…which is good…" + no stretch goal. If expenses were ₹75,000 → rate 6.25 % → "low" + "Stretch goal: save an extra ₹11,000.00 per month…" (0.2×80,000 − 5,000).

## 7. Tests

`test_agent_05_06_savings_optimizer_recommendations_and_rate`, `test_savings_metrics_and_recommendations_use_real_numbers`, `test_savings_rate_and_period_helpers`, `test_money_helpers_are_decimal_safe`.
