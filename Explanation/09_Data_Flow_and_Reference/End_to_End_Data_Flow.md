# End-to-End Data Flow

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Follows the data from first entry to AI-generated insight, showing how the phases connect. Per-request detail: [Request_Response_Lifecycle](Request_Response_Lifecycle.md).

## 1. One diagram, all phases

```mermaid
flowchart TB
    subgraph Entry["Data entry (Phase 1)"]
        UI["React forms"] --> API["FastAPI /api/v1"]
        CHAT["MCP chat: confirmed writes"] --> API
        SEED["scripts/seed_demo.py"] --> API
    end
    API --> SVC["services: rules, atomic DB transactions"]
    SVC --> DB[("SQLite<br/>users, accounts, transactions, budgets, budget_alerts")]

    subgraph Read["Read models (Phase 1)"]
        DB --> DASH["dashboard / analytics / summaries / budget status"]
    end
    DASH --> UI2["React pages and Recharts"]

    subgraph AI["AI layer (Phases 2-5) - REST only, caller's JWT"]
        MAN["user_manual.md"] --> ING["ingest.py"] --> CH[("ChromaDB")]
        CH --> RAG["RagChain"]
        DASH --> AG["Agent tools (read)"]
        RAG --> AG
        DASH --> MCPS["MCP server tools"]
        DASH --> LG["LangGraph pipeline"]
    end
    RAG --> A1["FAQ answers + sources"]
    AG --> A2["Live-data answers + tool trace"]
    MCPS --> A3["Chat answers; proposals -> confirm -> write"]
    LG --> A4["Markdown health report"]
    A3 --> CHAT
```

The loop closes at the MCP chat: the *only* AI path that can change data does so by calling the same REST endpoints (`POST /transactions`, `POST /budgets`) after a human confirmation, so every AI-created record passes the same validation as one created in the UI.

## 2. Scenario A — a debit crosses a budget threshold

1. User sets a food budget ₹10,000 for June (`POST /budgets` → `budgets` row; `spent=0`, no alerts).
2. User records an expense of ₹8,500 on a savings account (`POST /transactions`):
   * `UPDATE accounts` guarded balance change; `INSERT transactions`;
   * `check_and_create_alerts`: spent 8,500 ≥ 80 % × 10,000 → insert `budget_alerts(warning_80)`;
   * commit.
3. Frontend reloads lists; `GET /budgets` now returns `utilization_percent = 85.0`, `has_alert = true`; `GET /dashboard` returns `budget_alerts_count = 1`; the Budgets page shows an orange bar and a ⚠️ alert; the Dashboard shows the banner "1 budget alert this period".
4. Later, another debit takes spent ≥ 10,000 → `exceeded` alert added (the warning is not duplicated).
5. Phase 3 agent asked "Am I over budget on food?" → `get_budget_status` → `GET /budgets` → text "… OVER BUDGET - alert triggered".
6. Phase 5 report → Budget Advisor lists food under *over budget*, recommends "raise the limit or cut spending", the health score drops.

## 3. Scenario B — "Add a ₹500 grocery expense for today" in the MCP chat

```mermaid
sequenceDiagram
    participant U as User
    participant ST as Streamlit chat
    participant LLM as Gemini
    participant P as proposal tool
    participant MC as McpToolClient / MCP server
    participant BE as FastAPI
    U->>ST: message
    ST->>LLM: prompt + date + chat history
    LLM->>P: add_transaction(account_id, 500, debit, food, ...)
    P->>MC: get_accounts (verify account, balance)
    MC->>BE: GET /accounts
    P-->>LLM: PENDING_CONFIRMATION summary
    LLM-->>ST: "I'll record ... please confirm"
    ST-->>U: text + Confirm / Cancel buttons
    U->>ST: Confirm
    ST->>MC: add_transaction (deterministic, not via LLM)
    MC->>BE: POST /transactions
    BE-->>MC: 201 + created row
    ST->>MC: get_transactions (read-back) + get_accounts (new balance)
    ST-->>U: "Recorded expense #id ... New balance ..."
```
Details: [Confirmation_and_Execution_Flow](../06_MCP/Confirmation_and_Execution_Flow.md).

## 4. Scenario C — "How do I set a budget?" (RAG)

Manual → (offline) chunks + embeddings → ChromaDB; online: question embedding → top-4 chunks → grounded prompt → Gemini → answer + section sources. No financial data involved. Details: [RAG_Architecture](../04_RAG/RAG_Architecture.md).

## 5. Scenario D — Financial health report

```mermaid
flowchart LR
    U["User picks month/year"] --> G["generate_financial_report(token)"]
    G --> TA["Analyzer: /users/me, /transactions pages, /dashboard, /budgets, previous month"]
    TA --> BA["Budget Advisor"] --> SO["Savings Optimizer"] --> RG["Report Generator"]
    RG --> OUT["8-section Markdown + score"]
    OUT --> DL["Streamlit view / CLI file / download"]
```
Details: [Graph_State_and_Workflow](../07_LangGraph_Multi_Agent/Graph_State_and_Workflow.md).

## 6. Where each datum lives and who may touch it

| Data | Store | Writers | Readers |
|---|---|---|---|
| Users/credentials | `users` | backend (`register`, `PATCH /users/me`) | backend |
| Accounts/balances | `accounts` | backend services only (guarded updates) | React, agent, MCP, report (via REST) |
| Transactions | `transactions` | backend `create_transaction`/`create_transfer` (UI, or MCP after confirmation) | same |
| Budgets/alerts | `budgets`, `budget_alerts` | backend (`create_budget`, alert service) | same |
| Manual embeddings | ChromaDB | `ingest.py` | `RagChain` |
| JWT | browser `localStorage`; Streamlit `session_state`; MCP subprocess env | issued by `/auth/login` | sent as Bearer |
| Chat history / pending action | Streamlit `session_state` | Streamlit | Streamlit / agent prompt |
| Report | in-memory state → Markdown | LangGraph run | UI/CLI |

## 7. Consistency guarantees

* **Single source of truth:** only the backend writes finance data; every consumer reads through REST, so UI, chat, agent and report agree.
* **Atomicity:** balance + transaction + alert rows commit together or not at all.
* **Same definitions everywhere:** the report's totals come from `/dashboard`, so they match the UI (the analyzer explicitly prefers dashboard totals for income/expenses).
* **Eventual freshness:** nothing is cached server-side; the SPA refetches after each mutation; chat/agent fetch on every question.
