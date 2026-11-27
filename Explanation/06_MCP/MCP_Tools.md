# MCP Tools

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Source: [`ai/mcp_server/mcp_app.py`](../../ai/mcp_server/mcp_app.py). **Real tool count: 7** = the 6 tools required by the POC (`add_transaction`, `get_transactions`, `get_budget_status`, `get_dashboard_summary`, `set_budget`, `get_account_summary`) **plus `get_accounts`** (added because a write needs an account id). Verified by the list in `mcp_app.main()`, by `chat_interface.SPEC_TOOL_NAMES` (6 names) with `test_int_01_exactly_six_spec_mcp_tools` (asserts the module-level `MCP_TOOLS` list has exactly the six spec tools), and by `test_protocol_tool_discovery_and_schemas` (a real stdio session asserts the server exposes exactly the 7 names, with schemas).

All tools return a `dict`, never raise, and use the identity in the server environment. Each call is wrapped by `_tool()` (span `mcp.tool_invoke`, log `mcp_tool_invoked`).

| # | Tool | Kind | REST call | Confirmation in chat? |
|---|---|---|---|---|
| 1 | `add_transaction` | **write** | `POST /transactions` | **yes** |
| 2 | `get_transactions` | read | `GET /transactions` | no |
| 3 | `get_budget_status` | read | `GET /budgets` | no |
| 4 | `get_dashboard_summary` | read | `GET /dashboard` | no |
| 5 | `set_budget` | **write** | `POST /budgets` | **yes** |
| 6 | `get_account_summary` | read | `GET /accounts/{id}/summary` | no |
| 7 | `get_accounts` | read | `GET /accounts` | no |

---

## 1. `add_transaction`
```python
add_transaction(account_id: int, amount: float, transaction_type: str, category: str,
                description: str, transaction_date: str, merchant: str = "") -> dict
```
* **Purpose:** record an expense (`debit`) or income (`credit`).
* **Validation:** `validate_transaction_args` (see [MCP_Server §5](MCP_Server.md)). Invalid → `{"error": "<reason>"}` (no HTTP call).
* **Implementation:** builds `{"account_id","amount","type": transaction_type,"category","description": stripped,"transaction_date"}` (+ `"merchant"` if non-blank) and `POST /transactions`.
* **Returns:** the created transaction JSON (`id, account_id, amount, type, category, description, merchant, transaction_date, is_transfer, transfer_group, created_at`) or `{"error": …}` (e.g. `Insufficient balance`, `Account not found`, `Access denied…`).
* **Use case:** "Add a ₹500 grocery expense for today" — via the chat gate (the model only proposes).
* Log fields: `amount`, `category`.

## 2. `get_transactions`
```python
get_transactions(account_id: int = 0, category: str = "", date_from: str = "", date_to: str = "",
                 transaction_type: str = "", page: int = 1) -> dict
```
* **Purpose:** one page (20 per page — the backend default) of transactions with optional filters.
* **Validation:** `date_from`/`date_to` ISO if non-empty; `category ∈ CATEGORIES` if non-empty; `transaction_type ∈ {debit, credit}` if non-empty.
* **Implementation:** `GET /transactions` with `account_id=account_id or None`, empty strings dropped by `FinanceApiClient.request` (it removes `None` and `""`), `type=transaction_type`, `page`.
* **Returns:** the `TransactionPage` JSON `{items, total, page, page_size, pages}` or `{"error": …}`.
* **Use case:** "Show my recent transactions", and the **read-back verification** after a confirmed write.

## 3. `get_budget_status`
```python
get_budget_status(month: int = 0, year: int = 0) -> dict
```
* **Purpose:** all budgets with `spent`, `remaining`, `utilization_percent`, `has_alert`, `alerts`.
* **Implementation:** `GET /budgets` with `month`/`year` only when non-zero. **Default = all months** (unlike the Phase 3 agent tool, which defaults to the current month).
* **Returns:** `{"budgets": [ … BudgetOut … ]}` or `{"error": …}`.
* **Use case:** "How much of my food budget have I used?"; read-back after `set_budget`.

## 4. `get_dashboard_summary`
```python
get_dashboard_summary(month: int = 0, year: int = 0) -> dict
```
* **Purpose:** the dashboard: net balance, assets, liabilities, income, expenses, net cash flow, savings rate, top-3 categories, alert count, recent transactions, budget utilization.
* **Implementation:** `GET /dashboard` (`month`/`year` omitted when 0 → current month).
* **Returns:** `DashboardOut` JSON or `{"error": …}`.

## 5. `set_budget`
```python
set_budget(category: str, monthly_limit: float, month: int, year: int) -> dict
```
* **Purpose:** create a monthly category budget.
* **Validation:** `validate_budget_args` (salary excluded; limit > 0; month 1–12; year 2000–2100).
* **Implementation:** `POST /budgets` with the four fields.
* **Returns:** created budget (with live `spent/remaining/…`) or `{"error": …}` — notably the 409 `Conflict: A budget for this category, month and year already exists`.
* **Use case:** "Set a food budget of ₹10000 for this month" (through the gate).

## 6. `get_account_summary`
```python
get_account_summary(account_id: int) -> dict
```
* **Validation:** positive integer.
* **Implementation:** `GET /accounts/{account_id}/summary`.
* **Returns:** `AccountSummary` JSON (balance, total credits/debits, spending by category, 6-month trend) or `{"error": …}` (403 → "Access denied: that resource does not belong to your account.").

## 7. `get_accounts`
```python
get_accounts() -> dict
```
* **Purpose:** list accounts (id, name, type, balance; credit balance = amount owed) so the model can find `account_id`.
* **Implementation:** `GET /accounts`.
* **Returns:** `{"accounts": [ … AccountOut … ]}` or `{"error": …}`.
* **Extra use:** the chat layer calls it (a) to check the account exists and has enough balance before *proposing* a debit, and (b) to display the new balance after a confirmed write.

---

## Schemas visible through `tools/list`

`McpToolClient.list_tools()` returns `[{"name", "description", "input_schema"}]` where `description` is the tool docstring and `input_schema` is the JSON Schema derived from the signature (e.g. `add_transaction` requires `account_id, amount, transaction_type, category, description, transaction_date`; `merchant` is optional with default `""`). Descriptions explicitly list the allowed categories and date format so any LLM client can use them correctly.

## Parameter conventions to remember

* `0` / `""` mean "not provided" for optional filters.
* Months are 1–12, years four-digit.
* Money is a JSON number (float) at the MCP boundary; the backend re-parses it as `Decimal` (max 2 decimals).
* The two *write* tools are the only ones that change financial data; the chat layer never lets the LLM invoke them directly ([Confirmation_and_Execution_Flow](Confirmation_and_Execution_Flow.md)).
