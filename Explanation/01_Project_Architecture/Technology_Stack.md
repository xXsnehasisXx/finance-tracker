# Technology Stack

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Versions are taken from [`requirements.txt`](../../requirements.txt), [`frontend/package.json`](../../frontend/package.json) and [`docs/DEPENDENCY_DEVIATIONS.md`](../../docs/DEPENDENCY_DEVIATIONS.md). Only technologies actually present are listed. See also [Dependencies_and_Packages](../08_Deployment_and_DevOps/Dependencies_and_Packages.md) for the install/pin story.

**Runtime vs development:** "Runtime" = needed for the application to run; "Dev/Test" = only for tests/verification. Note: in `frontend/package.json` Vite and `@vitejs/plugin-react` are listed under `dependencies` (not `devDependencies`) even though they are build-time tools.

## 1. Frontend

| Technology | Version | What it is / why used | Where | Kind |
|---|---|---|---|---|
| **JavaScript (ES modules)** | ES2020+ | Mandated by the POC (JSX only, no TypeScript). `"type": "module"` | all of `frontend/src` | Runtime |
| **React** | ^18.3.1 | Component-based UI; state via hooks and context | `main.jsx`, `App.jsx`, pages, components | Runtime |
| **react-dom** | ^18.3.1 | Mounts React with `createRoot` | `main.jsx` | Runtime |
| **react-router-dom** | ^6.30.6 | Client-side routing: `BrowserRouter`, `Routes`, `NavLink`, `Outlet`, `Navigate` | `main.jsx`, `App.jsx`, `AppLayout.jsx` | Runtime (supporting package) |
| **Recharts** | ^2.15.4 | SVG charts (`PieChart`, `BarChart`), the POC-named chart library | `components/charts/*` | Runtime |
| **Vite** | ^8.3.8 | Dev server with HMR, production bundler, `/api` dev proxy | `vite.config.js` | Build (declared in `dependencies`) |
| **@vitejs/plugin-react** | ^6.3.0 | JSX transform / fast refresh for Vite | `vite.config.js` | Build |
| **Fetch API** | browser | Native HTTP client wrapped by `services/api.js`. **Axios is not used.** | `services/api.js` | Runtime |
| **Plain CSS** | — | One stylesheet with CSS variables and media queries. **Material UI is not used.** | `styles/index.css` | Runtime |

## 2. Backend

| Technology | Version | What / why | Where | Kind |
|---|---|---|---|---|
| **Python** | 3.13.1 (mandated, `.venv`) | Single interpreter for all five phases | everywhere | Runtime |
| **FastAPI** | 0.141.1 | ASGI framework: routing, dependency injection, automatic validation, OpenAPI docs at `/docs` | `app/main.py`, `app/routers/*` | Runtime |
| **uvicorn[standard]** | 0.54.0 | ASGI server | `backend/run.py` | Runtime |
| **SQLAlchemy** | 2.1.8 | ORM with typed `Mapped[...]` declarative models, `Session`, Core `select/update` | `app/models`, `app/services`, `app/database` | Runtime |
| **SQLite** | stdlib | Single-file embedded DB mandated by the POC | `finance_tracker.db` | Runtime |
| **Pydantic** | 2.14.3 | Request/response schemas, validators, `Decimal` constraints | `app/schemas/__init__.py` | Runtime |
| **email-validator** | 2.3.0 | Needed by Pydantic's `EmailStr` | `UserCreate.email` | Runtime (supporting) |
| **python-multipart** | 0.0.33 | Parses the OAuth2 form body at `/auth/login` | `OAuth2PasswordRequestForm` | Runtime (supporting) |
| **PyJWT** | 2.15.1 | Create/verify HS256 JWTs | `app/core/security.py` | Runtime (supporting) |
| **bcrypt** | 5.0.0 | Password hashing | `app/core/security.py` | Runtime (supporting) |
| **structlog** | 26.1.0 | JSON structured logging | `app/core/logging.py`, `ai/common/observability.py` | Runtime |
| **python-dotenv** | 1.0.1 | Loads `.env` | `core/config.py`, `ai/*` | Runtime |
| **httpx** | 0.28.1 | FastAPI `TestClient` backend, and the AI layer's HTTP client | `ai/common/api_client.py`, tests | Runtime (AI) / Test |
| **requests** | 2.34.2 | Declared "used by the POC tool/test code" | — | Declared |
| **opentelemetry-sdk** / **otlp-grpc exporter** | 1.24.0 | Minimal tracing (SDK + console exporter). The OTLP exporter is required by ChromaDB; the app does not use it | `core/telemetry.py`, `common/observability.py` | Runtime |

## 3. AI stack

| Technology | Version | What / why | Where |
|---|---|---|---|
| **LangChain (`langchain`)** | 1.0.8 | Prompt templates, runnables, tool abstraction (`@tool`) | `ai/*` |
| **langchain-classic** | 1.0.8 | In LangChain 1.x, `AgentExecutor` and `create_tool_calling_agent` live here | `agent/agent.py`, `mcp_server/chat_interface.py` |
| **langchain-community** | 0.4.2 | `Chroma` vector store wrapper and `TextLoader` | `rag/ingest.py`, `rag/rag_chain.py` |
| **langchain-google-genai** | 3.1.0 | `ChatGoogleGenerativeAI`, `GoogleGenerativeAIEmbeddings`; 3.1.0 keeps Gemini 3 "thought signatures" on tool-call turns | `common/llm.py` |
| **ChromaDB** | 0.5.7 | Local persistent vector DB | `rag/ingest.py`, `rag/rag_chain.py` |
| **Google Gemini** | model ids from env; defaults `gemini-3.5-flash-lite`, `models/gemini-embedding-001` | LLM + embeddings. The POC says "Gemini 2.0 Flash", reported as shut down; see deviations | `common/llm.py` |
| **LangGraph** | 1.0.10 (+ `langgraph-prebuilt` 1.0.8) | `StateGraph` for the multi-agent report | `multi_agent/graph.py` |
| **fastmcp** | 0.4.1 | High-level MCP server (`FastMCP`, `@mcp.tool()`) | `mcp_server/mcp_app.py` |
| **mcp** (MCP SDK) | 1.30.0 | MCP **client** (`ClientSession`, `stdio_client`) and server runtime used by fastmcp | `mcp_server/mcp_client.py` |
| **Streamlit** | 1.36.0 | Python-only chat UIs | `rag/chatbot.py`, `mcp_server/chat_interface.py` |
| **LangSmith** | 0.14.17 | Optional tracing via `@traceable` and env vars | `common/observability.py` |
| **numpy** | 2.5.4 | Only 2.x has Python 3.13 wheels | transitive |
| **posthog** | 5.4.0 | Pinned because ChromaDB 0.5.7 telemetry breaks with posthog ≥ 6 | transitive |

## 4. Test / verification

| Technology | Version | Where |
|---|---|---|
| **pytest** | 9.2.0 | `tests/`, `pytest.ini` |
| **pytest-cov** | 7.1.0 | coverage (`.coverage` present) |
| **FastAPI `TestClient`** (httpx) | — | `tests/conftest.py` |
| Fake LLM / embeddings | — | `tests/testsupport/fakes.py` (`ScriptedChatModel`, `HashEmbeddings`) |
| `scripts/verify/*.py` | — | offline dependency-compatibility gates |

## 5. Technologies NOT present (do not assume)

Docker, docker-compose, Nginx, systemd units, EC2/Terraform/CI configuration, Alembic migrations, Axios, Material UI, TypeScript, Redux, Celery, PostgreSQL. See [Production_Deployment](../08_Deployment_and_DevOps/Production_Deployment.md).

## 6. Why these choices (summary)

* **FastAPI + Pydantic**: validation and docs come "for free"; dependency injection makes `get_current_user`, `get_db` and `get_today` easy to override in tests.
* **SQLAlchemy 2.x + SQLite**: zero-ops persistence, but real constraints (unique, check, FK) and atomic guarded updates.
* **JWT (PyJWT) + bcrypt**: stateless bearer auth that both the SPA and AI components can reuse.
* **structlog**: the POC mandates structured JSON logs with fixed fields.
* **React + Vite**: fast dev loop; the `/api` proxy keeps the browser same-origin during development.
* **LangChain/LangGraph/ChromaDB/FastMCP/Streamlit**: named by the POC for Phases 2–5.
* **Decimal + integer paise**: avoids binary-float rounding for money.
