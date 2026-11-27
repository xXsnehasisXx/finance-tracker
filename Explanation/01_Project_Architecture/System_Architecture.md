# System Architecture

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Previous: [Project_Overview](Project_Overview.md) · Next: [Technology_Stack](Technology_Stack.md).

## 1. Process model

The system is **not** one process. At runtime there are up to five cooperating processes:

| # | Process | Started by | Port | Purpose |
|---|---|---|---|---|
| 1 | FastAPI backend (uvicorn) | `python backend/run.py` | 8000 (`PORT`) | REST API, SQLite, all business rules |
| 2 | Vite dev server (or static `dist/`) | `npm run dev` | 3000 | React SPA; proxies `/api` to the backend |
| 3 | Streamlit "RAG chatbot + live-data agent" | `streamlit run ai/rag/chatbot.py --server.port 8501` | 8501 | Phase 2 + 3 UI |
| 4 | Streamlit "MCP chat + report page" | `streamlit run ai/mcp_server/chat_interface.py --server.port 8502` | 8502 | Phase 4 + 5 UI |
| 5 | FastMCP server (stdio subprocess) | spawned by `McpToolClient` inside process 4 | none (stdin/stdout) | MCP tools, one subprocess per signed-in chat session |

The CLI `ai/multi_agent/report_runner.py` is a sixth, short-lived entry point for Phase 5.

## 2. High-level architecture

```mermaid
flowchart LR
    subgraph Browser
        SPA["React SPA<br/>Vite, port 3000"]
        ST1["Streamlit FAQ + agent<br/>port 8501"]
        ST2["Streamlit MCP chat + report<br/>port 8502"]
    end

    subgraph AI["AI layer (ai/)"]
        RAG["RAG chain<br/>rag_chain.py"]
        AGENT["Tool-calling agent<br/>agent.py + tools.py"]
        MCPC["McpToolClient<br/>mcp_client.py"]
        MCPS["FastMCP server<br/>mcp_app.py (stdio subprocess)"]
        LG["LangGraph pipeline<br/>graph.py + agents.py"]
        API["FinanceApiClient<br/>common/api_client.py"]
    end

    subgraph Backend["FastAPI backend (backend/app)"]
        R["Routers"]
        S["Services (business rules)"]
        M["SQLAlchemy models"]
    end

    DB[("SQLite<br/>finance_tracker.db")]
    CH[("ChromaDB<br/>chroma_db/")]
    GEM["Google Gemini API<br/>chat + embeddings"]

    SPA -- "fetch /api/v1 + Bearer JWT" --> R
    ST1 --> RAG
    ST1 --> AGENT
    ST2 --> MCPC
    ST2 --> LG
    MCPC -- "JSON-RPC over stdio" --> MCPS
    AGENT --> API
    MCPS --> API
    LG --> API
    AGENT -- "search_finance_policy" --> RAG
    API -- "HTTP + user's Bearer JWT" --> R
    R --> S --> M --> DB
    RAG --> CH
    RAG --> GEM
    AGENT --> GEM
    ST2 --> GEM
    LG --> GEM
```

### The single most important architectural rule

`FinanceApiClient` ([`ai/common/api_client.py`](../../ai/common/api_client.py)) is the **only** way the AI layer reads or writes finance data. It issues HTTP calls with the signed-in user's bearer token. Consequences:

* the agent, MCP server and LangGraph nodes cannot see other users' data (the backend returns 403/404);
* business rules (insufficient balance, one-budget-per-month, alert creation) are enforced once, in the backend;
* no AI component imports SQLAlchemy models or opens the database. This is consistent with the project rule *"AI agents must not independently invent or modify financial records."*

## 3. Layering inside the backend

```mermaid
flowchart TB
    HTTP["HTTP request"] --> MW["Middleware<br/>CORS, request_context (x-request-id, logging, span)"]
    MW --> RT["routers/*.py<br/>parse params, declare response_model, Depends(...)"]
    RT --> DEP["core/deps.py<br/>get_current_user (JWT) + get_db"]
    RT --> SVC["services/*.py<br/>business rules, DB transactions"]
    SVC --> Q["services/queries.py<br/>ownership checks + aggregate queries"]
    SVC --> ORM["models/*.py<br/>SQLAlchemy 2.x declarative"]
    Q --> ORM
    ORM --> DB[("SQLite")]
    RT --> SCH["schemas/__init__.py<br/>Pydantic validation + serialization"]
    EXC["core/exceptions.py AppError"] -. "mapped to JSON by main.py" .-> MW
```

| Layer | Files | Responsibility |
|---|---|---|
| Entry/wiring | `backend/run.py`, `app/main.py` | create app, middleware, handlers, routers |
| Routers | `app/routers/*.py` | HTTP surface only; delegate to services |
| Schemas | `app/schemas/__init__.py` | request validation and response shaping |
| Services | `app/services/*.py` | business rules; own `commit`/`rollback` |
| Query helpers | `app/services/queries.py` | ownership checks, month ranges, aggregations |
| Models | `app/models/*.py` | tables, constraints, relationships |
| Core | `app/core/*.py` | settings, JWT/bcrypt, money type, logging, tracing, clock, exceptions |

Details: [Backend_Architecture](../02_Backend/Backend_Architecture.md).

## 4. Frontend architecture in one picture

```mermaid
flowchart TB
    main["main.jsx<br/>StrictMode, BrowserRouter"] --> TP["ToastProvider"] --> AP["AuthProvider"] --> App["App.jsx<br/>Routes + Protected"]
    App --> Layout["AppLayout (sidebar, topbar, Outlet)"]
    Layout --> Pages["Dashboard · Accounts · Transactions · Budgets · Analytics · Assistant · Profile"]
    Pages --> Hook["useAsync(loader, deps)"]
    Hook --> API["services/api.js<br/>request() using fetch"]
    API --> Backend[("/api/v1 FastAPI")]
    Pages --> Forms["components/forms.jsx<br/>useForm + validators"]
    Pages --> Charts["components/charts (lazy Recharts)"]
```

Details: [React_Architecture](../03_Frontend/React_Architecture.md).

## 5. Trust boundaries and identity propagation

```mermaid
sequenceDiagram
    participant U as User (browser)
    participant S as Streamlit app
    participant C as McpToolClient
    participant M as MCP server subprocess
    participant B as FastAPI backend
    U->>S: email + password (sign-in form)
    S->>B: POST /auth/login (via FinanceApiClient)
    B-->>S: access_token (JWT)
    S->>S: keep token only in st.session_state
    S->>C: McpToolClient(token=...)
    C->>M: spawn subprocess with env API_JWT_TOKEN, API_BASE_URL, MCP_SESSION_ID
    Note over M: identity = process environment,<br/>never a tool argument
    M->>B: HTTP + Authorization: Bearer token
    B-->>M: only that user's data
```

The token is placed in the **server subprocess environment**, so an LLM cannot choose another user by passing a different `user_id`/token as a tool argument. The Phase 3 agent achieves the same with a `ToolContext` holding the token, and Phase 5 verifies `GET /users/me` id equals the requested `user_id` (otherwise it refuses; see [Transaction_Analyzer](../07_LangGraph_Multi_Agent/Transaction_Analyzer.md)).

## 6. Data stores

| Store | Technology | Location (default) | Written by | Notes |
|---|---|---|---|---|
| Relational | SQLite via SQLAlchemy | `DATABASE_URL=sqlite:///./finance_tracker.db` (relative to the **working directory**) | backend only | WAL mode + `PRAGMA foreign_keys=ON` for file DBs. The repo contains `finance_tracker.db` at root and `backend/finance_tracker.db`, depending on where the backend was started |
| Vector | ChromaDB `PersistentClient` | `CHROMA_DIR` or `<repo>/chroma_db` | `ai/rag/ingest.py` | collection `finance_manual`; `chroma_db/` is in `.gitignore`, yet `chroma_db/chroma.sqlite3` is currently tracked by git |
| Browser | `localStorage` key `ft_token` | browser | `services/api.js` | JWT for the React SPA |
| Streamlit | `st.session_state` | server memory | Streamlit apps | token, messages, executor, pending action |

## 7. Cross-cutting concerns

* **Observability.** Backend and AI layer both use structlog JSON logs carrying `poc_id`, `phase`, `associate_id`; the backend adds `request_id`. Minimal OpenTelemetry spans (console exporter only). Optional LangSmith tracing via environment variables. See [Validation_and_Error_Handling](../02_Backend/Validation_and_Error_Handling.md) and [Security_and_Configuration](../08_Deployment_and_DevOps/Security_and_Configuration.md).
* **Time.** `app/core/clock.py` is the single source of "today" so tests can freeze it.
* **Configuration.** Environment variables / `.env` only; see [Environment_Variables](../09_Data_Flow_and_Reference/Environment_Variables.md).
