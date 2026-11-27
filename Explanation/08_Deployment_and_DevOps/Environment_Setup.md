# Environment Setup (Local Development)

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Sources: [`README.md`](../../README.md), [`requirements.txt`](../../requirements.txt), [`requirements.lock`](../../requirements.lock), [`.env.example`](../../.env.example), [`scripts/`](../../scripts). This is the **implemented** local setup. For hosting see [Production_Deployment](Production_Deployment.md).

## 1. Prerequisites

| Tool | Requirement |
|---|---|
| Python | **3.13.1 only** (README: `python3.13 --version` must print 3.13.1). One shared `.venv` for backend, AI apps and tests |
| Node.js + npm | needed for the frontend; no `engines` field in `package.json` (the machine used for this documentation had Node v24.22.2) |
| Google Gemini API key | optional; only for live AI features |
| LangSmith key | optional; tracing only |

## 2. Python environment

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.lock      # exact verified versions
.venv/bin/pip check                             # must be clean
```
`requirements.txt` documents the **direct** dependencies and why each pin deviates from the POC; `requirements.lock` (161 lines) is the full freeze actually verified. See [Dependencies_and_Packages](Dependencies_and_Packages.md).

## 3. Configuration

```bash
cp .env.example .env     # then edit
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"   # value for SECRET_KEY
```
Minimum to start the backend: **`SECRET_KEY`**. Everything else has defaults. Full variable list: [Environment_Variables](../09_Data_Flow_and_Reference/Environment_Variables.md). `.env` must never be committed or pasted anywhere (see [Security_and_Configuration](Security_and_Configuration.md) for a repository-state warning).

Load the file into your shell when needed: `set -a; source .env; set +a`. The Python code also calls `load_dotenv()`, and `.vscode/settings.json` sets `python.terminal.useEnvFile: true`.

## 4. Frontend dependencies

```bash
(cd frontend && npm install)
```
Installs from `frontend/package.json` / `package-lock.json` (react, react-dom, react-router-dom, recharts, vite, @vitejs/plugin-react).

## 5. Running every component

| Component | Command (from repo root) | URL / port |
|---|---|---|
| Backend API | `.venv/bin/python backend/run.py` | http://127.0.0.1:8000/docs (`PORT` to change) |
| Frontend (dev) | `cd frontend && npm run dev` | http://localhost:3000 (proxies `/api` → backend) |
| Demo data (backend must be running) | `.venv/bin/python scripts/seed_demo.py [--base-url …]` | creates `demo@finance.com` with 3 accounts, ~6 months of transactions, budgets (one near 80 %, one exceeded), a card purchase and a repayment transfer. The script prints the demo credentials |
| Index the manual (RAG) | `.venv/bin/python ai/rag/ingest.py` | writes `chroma_db/` |
| RAG chatbot + live-data agent | `.venv/bin/streamlit run ai/rag/chatbot.py --server.port 8501` | http://localhost:8501 |
| MCP chat + report page | `.venv/bin/streamlit run ai/mcp_server/chat_interface.py --server.port 8502` | http://localhost:8502 |
| MCP server alone (stdio) | `API_JWT_TOKEN=… .venv/bin/python ai/mcp_server/mcp_app.py` | waits for JSON-RPC on stdin |
| Report CLI | `.venv/bin/python ai/multi_agent/report_runner.py --email … --password … [--month M --year Y] [--no-llm] [--output report.md]` | stdout / file |
| Tests | `.venv/bin/python -m pytest tests -q` | see below |

Order for a full demo: start backend → (optional) seed → start frontend → run `ingest.py` → start the two Streamlit apps. The AI apps need the backend running (they call it over HTTP at `API_BASE_URL`, default `http://localhost:8000/api/v1`).

Start the backend **from a consistent working directory** or set an absolute `DATABASE_URL`, otherwise the default relative SQLite path creates a different file (the repo has both `./finance_tracker.db` and `backend/finance_tracker.db`).

## 6. Tests

```bash
.venv/bin/python -m pytest tests -q                       # mock/offline tier runs; live tier skipped without keys
.venv/bin/python -m pytest tests/phase1 -q                # per phase: phase1 … phase5
.venv/bin/python -m pytest -m "live_gemini or live_langsmith" -v   # needs GOOGLE_API_KEY / LANGCHAIN_API_KEY
```
`pytest.ini`: `pythonpath = backend ai`, `testpaths = tests`, markers `mock`, `live_gemini`, `live_langsmith`, `real_clock`. Details: [master doc §20](../Finance%20Tracker.md#20-testing-architecture-and-important-limitations).

## 7. Optional corporate-TLS helpers

If the network performs TLS interception, Gemini (gRPC) calls can fail with `CERTIFICATE_VERIFY_FAILED`. `scripts/make_ca_bundle.sh --confirmed` builds `~/.config/finance-tracker/ca-bundle.pem` from certifi roots plus **allow-listed** corporate roots (`scripts/ca_allowlist.txt`); `source scripts/dev_env.sh` exports `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `GRPC_DEFAULT_SSL_ROOTS_FILE_PATH` if the bundle exists. SSL verification is never disabled. The project docs state these helpers were **not used or run**.

## 8. Verification scripts (`scripts/verify/`)

| Script | Purpose |
|---|---|
| `verify_stack.py` | offline compatibility checks of the dependency matrix |
| `verify_migration.py` | LangChain 1.0 migration checks (legacy APIs exercised functionally) |
| `verify_chroma.py` | Chroma persistence (write/reopen) with deterministic embeddings |
| `verify_mcp.py` + `mcp_server_fixture.py` | real MCP stdio protocol check against a minimal FastMCP 0.4.1 server |
| `verify_gemini_compat.py` | offline checks + live Gemini calls (only with a key); exit code 3 = offline passed, live not verified |

## 9. Common problems

| Symptom | Cause / fix |
|---|---|
| `RuntimeError: SECRET_KEY is not set` | set it in `.env` or the environment |
| Browser shows "Cannot reach the server" | backend not running, or `VITE_BACKEND_URL` wrong |
| Chatbot: "knowledge base is empty" | run `ai/rag/ingest.py` |
| Chatbot: embedding model mismatch | re-run `ingest.py` after changing `EMBEDDING_MODEL` |
| Gemini TLS errors | network interception (section 7) |
| AI answers "not configured" | `GOOGLE_API_KEY` missing |
| Login works in SPA but not in Streamlit | Streamlit apps keep separate sessions — sign in again there |
