# PROJECT_PROGRESS.md — POC-02 Personal Finance Tracker & Analytics

Interpreter: **Python 3.13.1 only** (`.venv`). Plan of record: approved v6 (Matrix B).
Honesty rule: mocked tests and live (real Gemini) tests are reported separately; a skipped live test is **not** a pass.

## Status summary
| Phase | Scope | Status | Verified by |
|---|---|---|---|
| Foundation | venv, lock, verification scripts, scaffold | **Done** | `scripts/verify/*` green from repo `.venv`; `pip check` clean |
| 1 — Backend | auth, accounts, transactions, transfers, budgets, alerts, dashboard, analytics | **Done** | 71 tests, 97% coverage, all 20 spec TCs |
| 1 — Frontend | React + Vite (JSX), Recharts, responsive | **Done** | `npm run build`; headless-Chrome flow check (0 console errors, mobile layout OK) |
| 2 — RAG | LangChain + ChromaDB + Gemini, user manual | **Done (mock-verified)** | 26 mock tests; live 10 skipped |
| 3 — Agent | tool-calling agent + RAG tool + context summarizer | **Done (mock-verified)** | 40 mock tests; live 9 skipped |
| 4 — MCP + Streamlit | fastmcp server (real stdio protocol), chat with write-confirmation gate | **Done (mock-verified)** | 56 mock tests (incl. real MCP subprocess); live 7 skipped |
| 5 — LangGraph | 4-agent report (calculations in Python, optional grounded LLM narrative), CLI + Streamlit page | **Done (mock-verified)** | 40 mock tests; real-HTTP CLI smoke run OK; live 2 skipped |
| **Live Gemini / LangSmith** | `scripts/verify/verify_gemini_compat.py`, `pytest -m live_gemini` | **BLOCKED — no GOOGLE_API_KEY / LANGCHAIN_API_KEY** | **28 live tests SKIPPED — none verified** |

## Completed tasks
- Foundation: `.venv` from `requirements.lock`; verification scripts; scratch environments deleted.
- Phase 1: models (User, Account, Transaction, Budget, BudgetAlert), integer-paise Decimal money type, JWT/bcrypt, structlog JSON logs, minimal OpenTelemetry, injectable clock. Rules: account-type-aware balances (credit balance = amount owed), "Insufficient balance", atomic guarded balance updates, warning_80 / exceeded alerts once per budget, one budget per user/category/month, 403/404 cross-user isolation, transfers so card repayments are never income or expense. Frontend pages: login/register, dashboard, accounts, transactions, budgets, assistant.
- Phase 2: manual chunking + Chroma ingestion, retrieval chain, source citations, out-of-scope handling.
- Phase 3: tools over the REST API with the caller's token, RAG tool, conversation summarizer, Streamlit agent mode.
- Phase 4: MCP server (6 spec tools + `get_accounts`; identity from the server environment, never from tool arguments); chat layer where `add_transaction` / `set_budget` only create a pending action that runs after an exact "yes" or the Confirm button, then reads the result back.
- Phase 5: Transaction Analyzer, Budget Advisor, Savings Optimizer, Report Generator on LangGraph with conditional error routing; all numbers computed with Decimal; LLM text is accepted only if every number in it appears in the facts; works without an LLM; 8-section Markdown report; CLI `report_runner.py`; "Financial health report" page in the MCP Streamlit app (read-only).
- Pipeline fix found during testing: user-verification failure now sets `report_status="error"` so the graph goes straight to the report.
- Scripts: `seed_demo.py`, `make_ca_bundle.sh` (fingerprint allow-list, refuses without `--confirmed`), `dev_env.sh`, `ca_allowlist.txt`. README written.

## Tests executed and results (last full run: `pytest tests -q`, Python 3.13.1)
| Tier | Passed | Failed | Skipped |
|---|---|---|---|
| Mock / offline | **233** (P1 71, P2 26, P3 40, P4 56, P5 40) | 0 | 0 |
| LIVE Gemini / LangSmith | **0** | 0 | **28 (not verified)** |

Also run: real backend over HTTP → `seed_demo.py` → `report_runner.py --no-llm` produced a full 8-section report for the seeded user.

## TC-API-08 (acceptance-test limitation, Option A)
Runs with a clock frozen to 2026-06-18 by the repo-root `conftest.py`, only for `tests/phase1/`. Production keeps real current-month semantics (a test asserts no hardcoded spec date exists in `backend/`; a `real_clock` test proves the default period follows the system date). Executed outside this repository's pytest configuration on a date other than June 2026 it fails by design — needs the acceptance owner's approval.

## Known issues / deviations
- Gemini 2.0 Flash is shut down; model is configurable (`GEMINI_MODEL=gemini-3.6-flash`) and **unverified live**. Embedding model id (`models/text-embedding-004`) is also unverified live. See `docs/DEPENDENCY_DEVIATIONS.md`.
- Live checks outstanding: embeddings, single/multi-turn tool calling, thought-signature preservation, tool-error retry, RAG answers, agent tool selection, LangGraph narratives, LangSmith traces.
- TLS: the CA bundle has **not** been created. The two Wipro root fingerprints in `scripts/ca_allowlist.txt` still need confirmation against the IT-published list.
- Alerts are evaluated when a debit is recorded (per POC); creating a budget after the spending does not retro-fire alerts.
- Deleting an account deletes its transactions; the counterpart leg of a transfer on another account remains.
- OpenTelemetry is minimal (console exporter + manual spans); `opentelemetry-instrumentation-fastapi` is not used (`pkg_resources` incompatibility).

## Remaining work
1. User supplies `GOOGLE_API_KEY` (and optionally `LANGCHAIN_API_KEY`) → run `scripts/verify/verify_gemini_compat.py` and `pytest -m live_gemini -v`; fix whatever the live API reveals; only then claim live integration.
2. User confirms the Wipro root fingerprints → `scripts/make_ca_bundle.sh --confirmed` → `source scripts/dev_env.sh`.
3. Decision on the TC-API-08 limitation for the external acceptance run.
