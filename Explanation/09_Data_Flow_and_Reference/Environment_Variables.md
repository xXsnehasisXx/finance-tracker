# Environment Variables

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Compiled from `os.getenv`/`os.environ` usage in `backend/`, `ai/`, `scripts/`, `tests/conftest.py`, the committed template [`.env.example`](../../.env.example) and `frontend/` (`import.meta.env`). **Only names, defaults and meanings are listed — no values from `.env` were read or copied.**

## 1. Backend

| Variable | Default | Required | Used in | Meaning |
|---|---|---|---|---|
| `SECRET_KEY` | — | **yes** | `core/config.py` → `core/security.py` | HS256 JWT signing key; generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`; startup fails if empty |
| `DATABASE_URL` | `sqlite:///./finance_tracker.db` | no | `core/config.py`, `database/__init__.py` | SQLAlchemy URL (relative path = relative to CWD) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | no | `core/config.py` | JWT lifetime |
| `CORS_ORIGINS` | `http://localhost:3000` | no | `app/main.py` | comma-separated allowed origins |
| `APP_ENV` | `development` | no | `core/config.py` | `test` disables OTel console default |
| `POC_ID` | `POC-02` | no | logging (backend + AI) | log field |
| `ASSOCIATE_ID` | `unknown` | no | logging | log field |
| `PHASE` | `1` | no | backend logging | log field (AI modules bind their own phase) |
| `OTEL_CONSOLE` | `true` unless `APP_ENV=test` (backend); `false` (AI layer) | no | `core/telemetry.py`, `ai/common/observability.py` | print spans to console |
| `PORT` | `8000` | no | `backend/run.py` | uvicorn port |

## 2. AI layer

| Variable | Default | Used in | Meaning |
|---|---|---|---|
| `GOOGLE_API_KEY` | — | `ai/common/llm.py`, agent/chat error paths | Gemini key; required only for live AI features; never logged |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | `ai/common/llm.py` | chat model id (retired ids `gemini-3.6-flash`, `gemini-2.0-flash` are replaced by the default with a warning) |
| `EMBEDDING_MODEL` | `models/gemini-embedding-001` | `ai/common/llm.py` | embedding model id (retired `text-embedding-004` variants replaced); **re-run ingestion after changing** |
| `GEMINI_FALLBACK_MODEL` | empty | `scripts/verify/verify_gemini_compat.py` only | optional second chat model for that verification script |
| `API_BASE_URL` | `http://localhost:8000/api/v1` | `ai/common/api_client.py`, agent, MCP, report | backend URL the AI layer calls |
| `API_JWT_TOKEN` | — | `agent/agent.py`, `tools.py`, `mcp_server/*`, `multi_agent/*` | token used by tests/CLI/standalone MCP server; interactive apps pass each signed-in user's own token instead |
| `MCP_SESSION_ID` | — | `mcp_app.py` | set by `McpToolClient` for the server subprocess; appears in logs/spans |
| `CHROMA_DIR` | `<repo>/chroma_db` | `rag/ingest.py`, `rag/rag_chain.py` | Chroma persistence directory |
| `MANUAL_PATH` | `ai/rag/user_manual.md` | `rag/ingest.py` | manual to ingest |
| `ANONYMIZED_TELEMETRY` | `False` (set by `observability.py` via `setdefault`) | Chroma | disable Chroma telemetry |

## 3. LangSmith (optional tracing)

| Variable | Meaning |
|---|---|
| `LANGCHAIN_TRACING_V2` (or `LANGSMITH_TRACING`) | `true` requests tracing; forced to `false` automatically if no key is set |
| `LANGCHAIN_API_KEY` (or `LANGSMITH_API_KEY`) | LangSmith key |
| `LANGCHAIN_PROJECT` | present in `.env.example` (`AI-Readiness-POC-02-P2`); the code passes explicit `project_name` per feature (`…-P2`, `-P3`, `-P4`, `-P5`) |

## 4. TLS (only behind corporate interception)

`SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `GRPC_DEFAULT_SSL_ROOTS_FILE_PATH` — commented out in `.env.example`; set by `scripts/dev_env.sh` when a CA bundle exists; passed through to the MCP subprocess by `McpToolClient`. Leave unset otherwise.

## 5. Frontend (Vite, build-time)

| Variable | Default | Used in | Meaning |
|---|---|---|---|
| `VITE_API_BASE_URL` | `/api/v1` | `services/api.js` | API base path/URL |
| `VITE_FAQ_URL` | `http://localhost:8501` | `pages/Assistant.jsx` | link to the RAG/agent Streamlit app |
| `VITE_ASSISTANT_URL` | `http://localhost:8502` | `pages/Assistant.jsx` | link to the MCP chat/report app |
| `VITE_BACKEND_URL` | `http://127.0.0.1:8000` | `vite.config.js` (Node, dev proxy target) | dev proxy target |

`VITE_*` values are embedded in the built bundle — never put secrets in them.

## 6. Test-only (set by `conftest.py`)

`APP_ENV=test` (default), `SECRET_KEY` (test-only value, default), `DATABASE_URL=sqlite://` (forced), `LANGCHAIN_TRACING_V2=false`, `LANGSMITH_TRACING=false`, `ANONYMIZED_TELEMETRY=False`. Live tests receive `GOOGLE_API_KEY`, `LANGCHAIN_API_KEY`, `LANGSMITH_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL` from the real environment/`.env` **only** for tests marked `live_gemini`/`live_langsmith`. `scripts/verify/*` read a `SCRATCH` variable for temp locations.

## 7. `.env.example` keys (template)

`APP_ENV, POC_ID, ASSOCIATE_ID, DATABASE_URL, SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, CORS_ORIGINS, API_BASE_URL, GOOGLE_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODEL, EMBEDDING_MODEL, API_JWT_TOKEN, LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT, ANONYMIZED_TELEMETRY` (+ commented TLS variables). Variables read by code but **not** in the template: `PHASE`, `OTEL_CONSOLE`, `PORT`, `CHROMA_DIR`, `MANUAL_PATH`, `MCP_SESSION_ID`, `LANGSMITH_*`.

## 8. Secret vs non-secret

Secrets: `SECRET_KEY`, `GOOGLE_API_KEY`, `LANGCHAIN_API_KEY`/`LANGSMITH_API_KEY`, `API_JWT_TOKEN`. Everything else is configuration. See [Security_and_Configuration](../08_Deployment_and_DevOps/Security_and_Configuration.md) for handling guidance.
