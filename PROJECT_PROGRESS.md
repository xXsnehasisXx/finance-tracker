# PROJECT_PROGRESS.md — POC-02 Personal Finance Tracker & Analytics

Interpreter: **Python 3.13.1 only** (`.venv`). Plan of record: approved v6 (Matrix B).
Honesty rule: mocked tests and live (real Gemini) tests are reported separately; a skipped live test is **not** a pass.

## Status summary
| Phase | Scope | Status | Verified by |
|---|---|---|---|
| Foundation | venv, lock, verification scripts, scaffold | **Done** | `scripts/verify/*` green from repo `.venv`; `pip check` clean |
| 1 — Backend | auth, accounts, transactions, transfers, budgets, alerts, dashboard, analytics | **Done** | 71 tests, 97% coverage, all 20 spec TCs |
| 1 — Frontend | React + Vite (JSX), Recharts, responsive | **Done** | `npm run build`; headless-Chrome flow check (0 console errors, mobile layout OK) |
| 2 — RAG | LangChain + ChromaDB + Gemini, user manual | **Done (mock-verified)** | 31 mock tests; live 10 skipped |
| 3 — Agent | tool-calling agent + RAG tool + context summarizer | **Done (mock-verified)** | 40 mock tests; live 9 skipped |
| 4 — MCP + Streamlit | fastmcp server (real stdio protocol), chat with write-confirmation gate | **Done (mock-verified)** | 56 mock tests (incl. real MCP subprocess); live 7 skipped |
| 5 — LangGraph | 4-agent report (calculations in Python, optional grounded LLM narrative), CLI + Streamlit page | **Done (mock-verified)** | 55 mock tests; real-HTTP CLI smoke run OK; live 2 skipped |
| **Live Gemini / LangSmith** | `pytest -m "live_gemini or live_langsmith"`, `scripts/verify/verify_gemini_compat.py` | **Not executable from the office laptop** (corporate TLS interception blocks gRPC to Google; no keys in this environment). Demonstrated by the developer on a personal laptop; not re-run here | **28 live tests SKIPPED here — not counted as passed** |

## Completed tasks
- Foundation: `.venv` from `requirements.lock`; verification scripts; scratch environments deleted.
- Phase 1: models (User, Account, Transaction, Budget, BudgetAlert), integer-paise Decimal money type, JWT/bcrypt, structlog JSON logs, minimal OpenTelemetry, injectable clock. Rules: account-type-aware balances (credit balance = amount owed), "Insufficient balance", atomic guarded balance updates, warning_80 / exceeded alerts once per budget, one budget per user/category/month, 403/404 cross-user isolation, transfers so card repayments are never income or expense. Frontend pages: login/register, dashboard, accounts, transactions, budgets, assistant.
- Phase 2: manual chunking + Chroma ingestion, retrieval chain, source citations, out-of-scope handling.
- Phase 3: tools over the REST API with the caller's token, RAG tool, conversation summarizer, Streamlit agent mode.
- Phase 4: MCP server (6 spec tools + `get_accounts`; identity from the server environment, never from tool arguments); chat layer where `add_transaction` / `set_budget` only create a pending action that runs after an exact "yes" or the Confirm button, then reads the result back.
- Phase 5: Transaction Analyzer, Budget Advisor, Savings Optimizer, Report Generator on LangGraph with conditional error routing; all numbers computed with Decimal; LLM text is accepted only if every number in it appears in the facts; works without an LLM; 8-section Markdown report; CLI `report_runner.py`; "Financial health report" page in the MCP Streamlit app (read-only).
- Pipeline fix found during testing: user-verification failure now sets `report_status="error"` so the graph goes straight to the report.
- Scripts: `seed_demo.py`, `dev_env.sh`, `make_ca_bundle.sh` + `ca_allowlist.txt` (optional corporate-TLS helpers; **not used, not required, not run**). README written.
- Model correction: default chat model `gemini-3.5-flash-lite`, embedding model `models/gemini-embedding-001`, defined once in `ai/common/llm.py`; stale retired ids in `.env` are replaced with a warning; the Chroma index records its embedding model and refuses a mismatched one (re-run ingest). Verify scripts and `.env.example` updated.
- LangSmith: key accepted as `LANGCHAIN_API_KEY` (or `LANGSMITH_API_KEY`); tracing is switched off automatically when no key is set; projects `AI-Readiness-POC-02-P2..P5`; live trace tests now enable tracing explicitly (`tracing_context`) and poll LangSmith to retrieve the created run (P5 also checks the four agent child runs).
- Test harness fixes: live-test skipping now reads `.env` (before, a key in `.env` left live tests skipped); mock tests never see real keys; tier summary counts fixture errors as failures.
- Health score fix (Phase 5): the report showed e.g. "75/100" with "budget health 50 + savings rate 78.5%" and hid that the savings component is capped at 100 and that 50 was an invented default for "no budgets". The report now prints the exact formula and both components; without budgets the savings component alone counts. Regression tests recompute the displayed score from the displayed components.

## Tests executed and results (last full run: `pytest tests -q`, Python 3.13.1, office laptop)
| Tier | Passed | Failed | Skipped |
|---|---|---|---|
| Mock / offline | **253** (P1 71, P2 31, P3 40, P4 56, P5 55) | 0 | 0 |
| LIVE Gemini / LangSmith | **0** | 0 | **28 (not executed here)** |

Also run: `pip check` clean; `npm run build` OK; backend started on a fresh SQLite file (tables auto-created) → register / login / account / debit / dashboard over HTTP all correct; `seed_demo.py` → `report_runner.py --no-llm` produced the full 8-section report.
A live test run with an invalid key confirmed live tests are activated (not skipped) when a key exists; it then failed at the TLS handshake (`CERTIFICATE_VERIFY_FAILED`, corporate interception) — an environment limitation, not an application defect.

## TC-API-08 (acknowledged acceptance-test limitation, Option A)
Runs with a clock frozen to 2026-06-18 by the repo-root `conftest.py`, only for `tests/phase1/`. Production keeps real current-month semantics. Executed outside this repository's pytest configuration on a date other than June 2026 it fails by design. Accepted as documented; no further change planned.

## Known issues / deviations
- Gemini 2.0 Flash is shut down; `gemini-3.6-flash` is not available with the free-tier key; the working models are `gemini-3.5-flash-lite` / `models/gemini-embedding-001` (see `docs/DEPENDENCY_DEVIATIONS.md`). Live behaviour was demonstrated by the developer on a personal laptop and is not re-verified in this environment.
- Office-laptop network: Google gRPC calls fail TLS verification behind corporate interception. Environment-specific; certificate configuration is deliberately out of scope (verification stays enabled, no bundle created).
- Alerts are evaluated when a debit is recorded (per POC); creating a budget after the spending does not retro-fire alerts.
- Deleting an account deletes its transactions; the counterpart leg of a transfer on another account remains.
- OpenTelemetry is minimal (console exporter + manual spans); `opentelemetry-instrumentation-fastapi` is not used (`pkg_resources` incompatibility).

## Remaining work (manual)
1. Put the real keys in `.env` (see README "Configure credentials"), re-run `python ai/rag/ingest.py` once, then run `pytest -m "live_gemini or live_langsmith" -v` where the network allows it.
