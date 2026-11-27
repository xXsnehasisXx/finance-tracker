# Agent Tools and Functions

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Source: [`ai/agent/tools.py`](../../ai/agent/tools.py). Execution flow: [Tool_Execution_Flow](Tool_Execution_Flow.md). There are **7 tools**: six read the REST API, one queries the RAG chain. **None can modify data.**

## 1. Shared infrastructure

### `ToolContext`
```python
@dataclass
class ToolContext:
    base_url: str | None; token: str | None
    rag_chain: Any = None; summarizer_llm: Any = None
    today: Callable[[], datetime.date] = datetime.date.today
```
`make_tools(get_context)` returns tools bound to *one* context (one user). `client()` builds `FinanceApiClient(ctx.base_url, ctx.token)` per call. Module-level `TOOLS`/named tools use `env_context()` (`API_BASE_URL`, `API_JWT_TOKEN`) for tests/CLI; real per-user agents use `make_tools(...)` through `build_agent`.

### The `guarded(name)` decorator (applied under `@tool`)
For every call: start timer + OpenTelemetry span `agent.tool_call` (`tool.name`); run the body; **catch any exception** → `"Could not complete <name>: an unexpected error occurred (<ExceptionType>)."` and log `tool_failed`; pass output through `_summarize_if_long` (> 2000 chars → LLM summary, fallback truncation to 1,500 chars + `[truncated: summary unavailable]`); set `tool.output_length`; log `tool_executed` (tool, output_length, duration_ms). Therefore **tools never raise**: an exception would break the agent loop, so failures are returned as readable strings the LLM can relay.

### Helpers
| Helper | Behaviour |
|---|---|
| `_parse_hint(text, today)` | lower-cases the text; `category` = first of `food, transport, utilities, entertainment, health, salary, other` found as a whole word; period = `YYYY-M(M)` matched by `\b(\d{4})-(\d{1,2})\b` if month in 1–12, else today's year/month |
| `_inr(v)` | `₹{float:,.2f}` |
| `_title(s)` | replace `_` with space, title-case |
| `_default_rag_chain()` | builds `build_rag_chain()` once and caches in `_rag_cache` |

How `@tool` builds the schema: LangChain derives the tool name from the function name, the **description from the docstring**, and the argument schema from the function signature. Most tools take a single optional free-text `input: str = ""`.

## 2. Tool reference

### 2.1 `get_budget_status`
| | |
|---|---|
| **Purpose** | budgets vs spending: over/under budget, utilization |
| **Input** | `input: str = ""` — optional category word and/or `YYYY-MM` (e.g. `"food 2026-06"`); default current month |
| **Calls** | `GET /budgets?month=M&year=Y` |
| **Processing** | filter by parsed category client-side; per budget compute flag: `pct >= 100` → `OVER BUDGET`, `>= 80` → `warning (80% reached)`, else `on track`; show remaining or "over the limit"; append `- alert triggered` if `has_alert` |
| **Output** | multi-line text; none-found messages: `No budget is configured for food in June 2026.` / `No budgets are configured for <period>. Set monthly budgets in the Budgets section.` |
| **Errors** | `Could not retrieve budget data: <api error>` |

Example output (illustrative):
```
Budget status for June 2026:
- Food: spent ₹8,500.00 of ₹10,000.00 (85.0% used), ₹1,500.00 remaining - warning (80% reached) - alert triggered
```

### 2.2 `get_dashboard_summary`
| | |
|---|---|
| **Purpose** | balance, income, expenses, net cash flow, savings rate, top categories, alert count |
| **Input** | `input: str = ""` — optional `YYYY-MM` |
| **Calls** | `GET /dashboard?month&year` |
| **Output** | 9 labelled lines: net balance (assets minus credit owed), total assets, credit owed, income, expenses, net cash flow, savings rate (1 dp), top categories (name + amount, or "no spending recorded"), alerts this month |
| **Errors** | `Could not retrieve dashboard data: …` |

### 2.3 `get_accounts`
| | |
|---|---|
| **Purpose** | list accounts / find an account id |
| **Input** | `input: str = ""` (ignored) |
| **Calls** | `GET /accounts` |
| **Output** | `- id 3: HDFC Savings (savings) - balance ₹…` (credit accounts say `owed`); empty → "You have no accounts yet. Create one in the Accounts section." |

### 2.4 `get_account_summary`
| | |
|---|---|
| **Purpose** | one account's balance, total credits/debits, category spending, 6-month trend |
| **Input** | `account_id: str` — digits only (the prompt says to call `get_accounts` first if unknown) |
| **Validation** | non-digit → `Could not retrieve account summary: '<x>' is not a valid account id.` (no API call) |
| **Calls** | `GET /accounts/{id}/summary` |
| **Errors** | 404 → `Account <id> not found. Please verify the account ID.`; other → `Could not retrieve account summary for account <id>: <error>` (a 403 for another user's account becomes "Access denied: that resource does not belong to your account.") |
| **Output** | balance, total credits, total debits, spending by category (bulleted), monthly trend `YYYY-MM: ₹spend` |

### 2.5 `get_transactions`
| | |
|---|---|
| **Purpose** | list/filter transactions |
| **Input** | `input: str` — JSON object text, e.g. `{"account_id": 1, "category": "food", "date_from": "2026-06-01", "date_to": "2026-06-30", "type": "debit"}`; a bare category word is also accepted |
| **Validation** | text starting with `{` must be valid JSON object (`Could not read the filters: input must be valid JSON such as {"category": "food"}.` / `…must be a JSON object.`); only keys `account_id, category, date_from, date_to, type` with truthy values are forwarded (unknown keys ignored — `test_exec_transactions_ignores_unknown_filter_keys`) |
| **Calls** | `GET /transactions?page_size=20&<filters>` (the backend validates enums/dates → 422 message returned) |
| **Output** | `Found N transaction(s); showing the K most recent:` then up to 10 lines of the form `- date \| Debit/Credit \| ₹amount \| Category \| description[:60] (merchant) [transfer]`, and `... and N-10 more.`; empty → "No transactions found matching the specified filters." |

### 2.6 `get_spending_by_category`
| | |
|---|---|
| **Purpose** | where the money goes in a month (debits only, transfers excluded) |
| **Input** | `input: str = ""` — optional `YYYY-MM` |
| **Calls** | `GET /analytics/spending-by-category?month&year` |
| **Output** | `Spending by category for June 2026 (total ₹…):` + one line per category; empty → `No spending recorded for <period>.` |

### 2.7 `search_finance_policy` (RAG tool)
| | |
|---|---|
| **Purpose** | answer "how does the app work / budgets / alerts / categories / best practice" from the user manual |
| **Input** | `question: str` |
| **Implementation** | `chain = ctx.rag_chain or _default_rag_chain()`; `ask_question(question, chain)`; appends `(Sources: <sorted unique section names>)` |
| **Errors** | `MissingApiKeyError` → "The knowledge base is unavailable because GOOGLE_API_KEY is not set."; `RuntimeError` (empty index/embedding mismatch) → "The knowledge base is unavailable: <message>"; LLM failures are handled inside `ask_question` |
| **Notes** | this tool makes its **own** LLM call (the RAG generation) inside the agent's tool step |

## 3. Validation and error handling summary

| Layer | What it does |
|---|---|
| Tool body | light input checks (digit id, JSON filters, whitelisted keys) |
| `FinanceApiClient` | maps HTTP/connection errors to readable strings (401 session expired, 403 access denied, 404/409/422 with detail, timeout, backend unavailable) |
| Backend | the real validation and authorization |
| `guarded` | never-raise guarantee + summarisation |
| System prompt | tells the model to report errors plainly instead of guessing |

## 4. Tests

`tests/phase3/test_agent_mock.py` (mock tier) covers: tool names/descriptions (`test_tool_01…04`), values coming from the API (`test_exec_*`), unreachable API/timeouts/missing token messages, RAG tool behaviour with and without a key, per-user isolation (`test_auth_*`), read-only behaviour, never-raise, prompt contents, summarisation (`test_ctx_*`), end-to-end scripted runs (`test_e2e_*`), logging/spans, and the Streamlit agent mode (`test_streamlit_*`).
