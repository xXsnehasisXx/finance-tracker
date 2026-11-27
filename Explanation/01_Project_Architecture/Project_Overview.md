# Project Overview

> Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). This file answers: *what is this project, who is it for, what does it do, and how is the repository laid out?*

## 1. What the project is

**POC-02 — Personal Finance Tracker & Analytics** is a banking-domain proof of concept that grows in five phases from a classic full-stack CRUD application into an AI-assisted financial advisor. The source of truth for the scope is the POC specification (`docs/overview.pdf`, mirrored as Markdown/PDF files in [`extras/`](../../extras)). Progress and test claims made by the developer live in [`PROJECT_PROGRESS.md`](../../PROJECT_PROGRESS.md).

| Phase | What it adds | Main code |
|---|---|---|
| 1 | Full-stack finance app: auth, accounts, transactions, transfers, budgets, alerts, dashboard, analytics | `backend/app/`, `frontend/src/` |
| 2 | RAG chatbot answering questions from the app's user manual | `ai/rag/` |
| 3 | Tool-calling agent that reads live financial data through the REST API and consults the RAG chain | `ai/agent/` |
| 4 | MCP server (FastMCP) + Streamlit chat with a confirmation gate for money-changing actions | `ai/mcp_server/` |
| 5 | LangGraph multi-agent "financial health report" | `ai/multi_agent/` |

## 2. Problems the application solves

1. **Where did my money go?** Every debit/credit is recorded against an account and a category, then aggregated into a dashboard, per-category spending and income-vs-expense trends.
2. **Am I overspending?** Monthly per-category budgets raise a persisted alert at 80 % and again at 100 % utilization.
3. **What is my real net position?** Credit-card accounts are modelled as *amount owed*, so the dashboard's net balance is assets minus liabilities, and card repayments (transfers) are never miscounted as income or expense.
4. **How do I use the app?** A RAG chatbot answers "how do I…?" questions strictly from the user manual.
5. **Can I just ask in plain language?** A tool-calling agent and an MCP-based chat can read data and *propose* writes ("Add a ₹500 grocery expense") that only execute after explicit confirmation.
6. **How healthy are my finances overall?** A four-agent LangGraph pipeline produces an 8-section Markdown report with a 0–100 health score.

## 3. Feature inventory (all verified in source)

| Area | Features | Where documented |
|---|---|---|
| Auth | Register, login (OAuth2 password form → JWT), `GET/PATCH /users/me`, bcrypt hashing | [Authentication_and_JWT](../02_Backend/Authentication_and_JWT.md) |
| Accounts | Create, list, get, **rename only** (`PATCH`), delete (cascades transactions), per-account summary | [API_Endpoints](../02_Backend/API_Endpoints.md) |
| Transactions | Create, list (filters + pagination), get by id, atomic two-leg transfers. **No edit, no delete.** | [Business_Logic](../02_Backend/Business_Logic.md) |
| Budgets | Create, list, get, delete. **No edit.** One per user/category/month/year. Alerts `warning_80` / `exceeded` | [Business_Logic](../02_Backend/Business_Logic.md) |
| Dashboard/analytics | Dashboard, spending-by-category, income-vs-expense | [Business_Logic](../02_Backend/Business_Logic.md) |
| Frontend | 7 protected pages, Recharts charts, toasts, modals, responsive layout | [React_Architecture](../03_Frontend/React_Architecture.md) |
| RAG | Chunk → embed → ChromaDB → top-4 retrieval → Gemini | [RAG_Architecture](../04_RAG/RAG_Architecture.md) |
| Agent | 7 LangChain tools (6 REST + 1 RAG), per-user token | [Agent_Architecture](../05_AI_Agent/Agent_Architecture.md) |
| MCP | 7 FastMCP tools over stdio, confirmation gate, Streamlit chat | [MCP_Architecture](../06_MCP/MCP_Architecture.md) |
| LangGraph | 4 nodes, 1 conditional edge, deterministic maths + grounded narrative | [LangGraph_Architecture](../07_LangGraph_Multi_Agent/LangGraph_Architecture.md) |

## 4. Repository layout

```
finance-tracker/
├── backend/
│   ├── run.py                    # uvicorn launcher (127.0.0.1:$PORT, default 8000)
│   └── app/
│       ├── main.py               # create_app(): CORS, request middleware, handlers, routers
│       ├── core/                 # config, deps (auth), security (JWT/bcrypt), money, logging, telemetry, clock, exceptions
│       ├── database/__init__.py  # engine, SessionLocal, get_db, init_db
│       ├── models/               # User, Account, Transaction, Budget, BudgetAlert
│       ├── schemas/__init__.py   # all Pydantic request/response models
│       ├── services/             # business rules (auth, account, transaction, budget, budget_alert, dashboard, queries)
│       └── routers/              # auth, accounts, transactions, budgets, dashboard
├── frontend/                     # React 18 + Vite (JSX only)
│   └── src/ pages · components · components/charts · contexts · hooks · layouts · services · utils · styles
├── ai/
│   ├── common/                   # llm.py (Gemini factories), api_client.py (REST client), observability.py
│   ├── rag/                      # user_manual.md, ingest.py, rag_chain.py, chatbot.py (Streamlit :8501)
│   ├── agent/                    # agent.py, tools.py, prompts.py, summarizer.py
│   ├── mcp_server/               # mcp_app.py (server), mcp_client.py, chat_interface.py (Streamlit :8502)
│   └── multi_agent/              # state.py, agents.py, calculations.py, graph.py, report_runner.py
├── tests/                        # phase1 … phase5, testsupport (fakes)
├── scripts/                      # seed_demo.py, verify/*, dev_env.sh, make_ca_bundle.sh
├── docs/DEPENDENCY_DEVIATIONS.md # why pins differ from the POC
├── extras/                       # POC specification + test specs (reference only; never modified)
├── requirements.txt / .lock      # direct pins / full freeze (Python 3.13.1)
├── pytest.ini, conftest.py       # test config, frozen spec clock, mock/live tiers
└── chroma_db/, *.db              # runtime data (listed in .gitignore, but see Security_and_Configuration: some are already tracked)
```

## 5. Design principles that explain most decisions

1. **The AI layer never touches the database.** Everything (agent tools, MCP tools, LangGraph agents) goes through the REST API with the *caller's own bearer token*. Authorization and business rules therefore live in exactly one place (the backend). See [System_Architecture](System_Architecture.md).
2. **Money is never a float inside the backend.** Amounts are `Decimal`, persisted as integer paise (`Money` type). See [Database_and_SQLAlchemy](../02_Backend/Database_and_SQLAlchemy.md).
3. **LLMs never compute figures.** The Phase 5 report is calculated in Python; Gemini only adds short narrative text, which is discarded if it contains numbers not present in the data.
4. **Writes by AI need a human "yes".** The MCP chat can only *propose* writes; execution happens outside the model after an explicit confirmation.
5. **Everything optional degrades gracefully.** Without `GOOGLE_API_KEY` the app, offline tests and the report CLI still work.

## 6. Important facts / honesty notes

* **Python 3.13.1 only**; several package pins differ from the POC (see [Dependencies_and_Packages](../08_Deployment_and_DevOps/Dependencies_and_Packages.md)).
* The POC names *Gemini 2.0 Flash*, which the project docs state was shut down. The code default is `gemini-3.5-flash-lite` (chat) and `models/gemini-embedding-001` (embeddings), defined once in [`ai/common/llm.py`](../../ai/common/llm.py). Live Gemini behaviour is **not verified in this repository's environment** (see [Testing section of the master doc](../Finance%20Tracker.md#20-testing-architecture-and-important-limitations)).
* There is **no Docker, Nginx, systemd or EC2 configuration** in the repository. See [Production_Deployment](../08_Deployment_and_DevOps/Production_Deployment.md).
* The frontend uses the native `fetch` API (no Axios) and hand-written CSS (no Material UI).
