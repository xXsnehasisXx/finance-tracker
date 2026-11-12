# POC-02 — Personal Finance Tracker & Analytics

Five phases on **Python 3.13.1 only** (one shared `.venv`):

1. **Full-stack app** — React + Vite (JSX) frontend, FastAPI + SQLAlchemy + SQLite backend, JWT Bearer auth, structlog.
2. **RAG chatbot** — LangChain + ChromaDB + Gemini, grounded in `ai/rag/user_manual.md`.
3. **Tool-calling agent** — LangChain tools over the REST API + the RAG chain.
4. **MCP server + chat** — `fastmcp` server (6 spec tools + `get_accounts`) and a Streamlit chat with a confirmation gate for writes.
5. **LangGraph report** — Transaction Analyzer → Budget Advisor → Savings Optimizer → Report Generator.

Specification: `docs/overview.pdf` and `extras/`. Progress and test results: [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md).
Dependency choices (Matrix B, Gemini model substitution): [docs/DEPENDENCY_DEVIATIONS.md](docs/DEPENDENCY_DEVIATIONS.md).

## Setup

```bash
python3.13 --version                       # must print 3.13.1
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.lock   # exact verified versions (requirements.txt = top-level pins)
.venv/bin/pip check
cp .env.example .env                       # then edit: SECRET_KEY, GOOGLE_API_KEY, ...
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"   # value for SECRET_KEY
(cd frontend && npm install)
```

Secrets only come from the environment / `.env` (never committed). Load it with `set -a; source .env; set +a`.

## Run

| What | Command | URL |
|---|---|---|
| Backend API | `.venv/bin/python backend/run.py` | http://127.0.0.1:8000/docs |
| Frontend | `cd frontend && npm run dev` | http://localhost:3000 |
| Demo data (backend must be running) | `.venv/bin/python scripts/seed_demo.py` | login `demo@finance.com` / `DemoPass123` |
| Index the user manual (Phase 2) | `.venv/bin/python ai/rag/ingest.py` | |
| RAG chatbot + live-data agent | `.venv/bin/streamlit run ai/rag/chatbot.py --server.port 8501` | http://localhost:8501 |
| MCP chat (and report page) | `.venv/bin/streamlit run ai/mcp_server/chat_interface.py --server.port 8502` | http://localhost:8502 |
| MCP server alone (stdio) | `.venv/bin/python ai/mcp_server/mcp_app.py` (needs `API_JWT_TOKEN`) | |
| Report CLI (Phase 5) | `.venv/bin/python ai/multi_agent/report_runner.py --email demo@finance.com --password DemoPass123 [--month 10 --year 2026] [--no-llm] [--output report.md]` | |

The AI apps need the backend running. Without `GOOGLE_API_KEY` the report CLI still works (figures are calculated in Python;
Gemini only adds short commentary, which is discarded if it contains numbers not in the data).

## Tests

```bash
.venv/bin/python -m pytest tests -q                 # mock tier runs; live tier is skipped without keys
.venv/bin/python -m pytest tests/phase1 -q          # per phase: phase1 … phase5
.venv/bin/python -m pytest -m live_gemini -v        # LIVE Gemini tests (needs GOOGLE_API_KEY)
.venv/bin/python scripts/verify/verify_gemini_compat.py   # live Gemini compatibility script (needs GOOGLE_API_KEY)
```

The pytest summary prints **mock** and **live** results separately. A skipped live test is never counted as a pass.

TC-API-08 (spec dashboard test) assumes June 2026. The repo-root `conftest.py` freezes the clock to 2026-06-18 for
`tests/phase1/` only; production always uses the real current month.

## Corporate TLS interception (optional)

pip and the REST/MCP parts work without changes. gRPC (Gemini) may need the corporate root CA:
`scripts/ca_allowlist.txt` lists the allowed SHA-256 fingerprints; after confirming them with IT run
`scripts/make_ca_bundle.sh --confirmed` (creates `~/.config/finance-tracker/ca-bundle.pem`, outside the repo), then
`source scripts/dev_env.sh`. SSL verification is never disabled.

## Layout

```
backend/app/   core · database · models · schemas · services (business rules) · routers
frontend/src/  pages · components · charts · contexts · services
ai/            common · rag · agent · mcp_server · multi_agent
scripts/       seed_demo.py · verify/ (dependency + live gates) · make_ca_bundle.sh · dev_env.sh
tests/         phase1 … phase5 (+ live_* files) · testsupport (fake LLMs)
```
