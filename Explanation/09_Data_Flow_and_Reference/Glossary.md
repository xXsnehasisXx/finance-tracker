# Glossary

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Terms as used in this project.

## Finance domain

| Term | Meaning here |
|---|---|
| **Account** | A user's money container: `savings`, `checking` or `credit`. Owned by a user |
| **Asset account** | `savings` or `checking`; `balance` = funds held (never below zero) |
| **Credit account** | credit card; `balance` = **amount owed** |
| **Transaction** | One recorded movement on an account: `debit` (expense / money out) or `credit` (income / money in) with category, description, date. Cannot be edited or deleted individually |
| **Category** | Enum: food, transport, utilities, entertainment, health, salary, other. `salary` is income-only and cannot have a budget |
| **Transfer** | Two linked transactions (`is_transfer=true`, same `transfer_group`) moving money between the user's accounts, e.g. paying a card. Excluded from income, expenses, spending and budgets |
| **Budget** | Monthly spending limit for a category, unique per user/category/month/year; cannot be edited |
| **Utilization** | `spent / monthly_limit × 100` |
| **Alert** | Persisted `BudgetAlert`: `warning_80` (≥ 80 %) or `exceeded` (≥ 100 %), once each per budget, created when a debit is recorded |
| **Net balance** | `total_assets − total_liabilities` on the dashboard |
| **Savings rate** | `(income − expenses) / income × 100`; 0 if no income |
| **Paise** | 1/100 rupee; money is stored as integer paise |
| **50/30/20 rule** | Guideline: 50 % needs, 30 % wants, 20 % savings (Savings Optimizer uses a simplified category mapping) |
| **Health score** | 0–100: 50 % budget health + 50 % savings component (savings rate ÷ 30 % target, capped at 100) |

## Backend / web

| Term | Meaning |
|---|---|
| **FastAPI** | Python ASGI web framework used for the REST API |
| **Pydantic** | Data-validation library; defines request/response schemas |
| **SQLAlchemy / ORM** | Maps Python classes to SQL tables; `Session` = unit of work |
| **Dependency injection (`Depends`)** | FastAPI mechanism supplying `get_db`, `get_current_user`, `get_today` |
| **JWT** | JSON Web Token; signed `header.payload.signature` string carrying `sub` (user id) and `exp` |
| **Bearer token** | `Authorization: Bearer <JWT>` header |
| **bcrypt** | Salted, slow password hash |
| **CORS** | Browser rule restricting cross-origin requests; configured by `CORS_ORIGINS` |
| **structlog** | Structured (JSON) logging library |
| **OpenTelemetry span** | A timed unit of work in a trace |
| **WAL** | SQLite Write-Ahead Logging mode (set for file databases) |
| **Cascade** | ORM rule deleting children with the parent (account → transactions, budget → alerts) |
| **Idempotent / atomic** | atomic = all-or-nothing DB transaction |

## Frontend

| Term | Meaning |
|---|---|
| **Vite** | Dev server and bundler |
| **JSX** | JavaScript syntax extension for React markup |
| **Context** | React mechanism for app-wide state (`AuthContext`, `ToastContext`) |
| **Hook** | React function such as `useState`, `useEffect`; custom: `useAsync`, `useForm` |
| **Protected route** | Route wrapper that redirects unauthenticated users to `/login` |
| **Recharts** | Chart library (bar and pie charts) |
| **SPA** | Single-page application |

## AI

| Term | Meaning |
|---|---|
| **LLM** | Large language model (Gemini) |
| **Embedding** | Vector representation of text capturing meaning |
| **Vector database (ChromaDB)** | Stores embeddings and finds nearest neighbours |
| **Chunk** | A 512-character (50 overlap) piece of the manual |
| **RAG** | Retrieval-Augmented Generation: retrieve relevant text, put it in the prompt, generate a grounded answer |
| **Top-k** | Number of chunks retrieved (4) |
| **LCEL** | LangChain Expression Language: pipelines written as `prompt \| llm \| parser` |
| **Tool (function calling)** | Function the LLM may request to run, described by name/description/schema |
| **Agent** | Loop that lets an LLM call tools until it can answer (`AgentExecutor`) |
| **Scratchpad** | Tool calls and results accumulated during an agent run |
| **MCP** | Model Context Protocol: standard for exposing tools to AI clients over JSON-RPC |
| **FastMCP** | Python library for building MCP servers (`@mcp.tool()`) |
| **stdio transport** | MCP over a subprocess's stdin/stdout |
| **Confirmation gate** | Mechanism letting the LLM only propose writes; a human confirmation executes them |
| **Pending action** | The single proposed write waiting for confirmation |
| **LangGraph** | Library for graph-based multi-step workflows (`StateGraph`) |
| **State** | Shared dictionary passed between graph nodes (`FinancialHealthState`) |
| **Conditional edge** | Edge whose target is chosen by a routing function |
| **Narrative guard** | Check that LLM prose contains only numbers present in the computed facts |
| **LangSmith** | Optional hosted tracing for LangChain runs |
| **Streamlit** | Python framework for the chat UIs |
| **Thought signature** | Gemini 3 metadata that must be preserved across tool-call turns |
| **Mock tier / live tier** | Offline tests with fake LLMs vs. tests needing real keys (skipped, never counted as pass, when keys absent) |

## Project

| Term | Meaning |
|---|---|
| **POC-02** | The specification this project implements (Personal Finance Tracker & Analytics) |
| **Phases 1–5** | Full-stack app → RAG → agent → MCP + chat → LangGraph report |
| **`extras/`** | Read-only reference specs and test specs |
| **TC-API-08** | Spec test for the dashboard that assumes the date 2026-06-18; the Phase 1 tests run with a frozen clock |
