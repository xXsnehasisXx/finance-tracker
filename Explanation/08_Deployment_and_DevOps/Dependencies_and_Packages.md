# Dependencies and Packages

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Sources: [`requirements.txt`](../../requirements.txt), [`requirements.lock`](../../requirements.lock), [`docs/DEPENDENCY_DEVIATIONS.md`](../../docs/DEPENDENCY_DEVIATIONS.md), [`frontend/package.json`](../../frontend/package.json). What each technology does is in [Technology_Stack](../01_Project_Architecture/Technology_Stack.md); this file explains the pinning strategy and deviations.

## 1. Files

| File | Role |
|---|---|
| `requirements.txt` | direct dependencies with comments `package==final  # spec pin -> reason` |
| `requirements.lock` | full transitive freeze (161 pins) verified from the project `.venv`; **install from this** |
| `frontend/package.json` + `package-lock.json` | npm dependencies (5 runtime-ish + vite) |
| `docs/DEPENDENCY_DEVIATIONS.md` | table of every pin that differs from the POC and why |
| `scripts/verify/*.py` | evidence scripts for the compatibility matrix |

## 2. Why pins differ from the POC

The POC `extras/` pin 2024-era versions. The project mandates **Python 3.13.1**, for which several of those pins cannot install or run (no wheels, `numpy<2` caps, `langchain-core` caps). Pins were upgraded *minimally*:

| Package | POC pin | Final | Reason (from the deviation doc / requirements comments) |
|---|---|---|---|
| langchain | 0.2.6 | 1.0.8 | needs `numpy<2` (no Py3.13 wheels); `langchain-google-genai ≥ 3` needs core 1.x |
| langchain-classic | in langchain | 1.0.8 | `AgentExecutor`, `create_tool_calling_agent`, summarize chain moved here |
| langchain-community | implied | 0.4.2 | `Chroma`, `TextLoader` |
| langchain-google-genai | 1.0.6 | 3.1.0 | 1.0.6 needs `langchain-core<0.3`; 2.x lacks Gemini 3 thought signatures; 3.0.3 drops signatures on function-call-only turns |
| google-ai-generativelanguage | 0.6.4 | 0.12.0 | `Part.thought_signature` exists only from 0.7.0 |
| langgraph | 0.1.17 | 1.0.10 | langchain-core cap |
| langgraph-prebuilt | — | 1.0.8 | 1.0.13 breaks `import langchain.agents` (needs langgraph ≥ 1.2) |
| langsmith | 0.1.77 | 0.14.17 | incompatible with langchain-core 1.x |
| chromadb | 0.5.3 | 0.5.7 | first release without the `numpy<2` cap |
| chroma-hnswlib | 0.7.3 | 0.7.6 | no wheel; compiled from source |
| posthog | — | 5.4.0 | chromadb 0.5.7 telemetry breaks with posthog ≥ 6 |
| numpy | <2 | 2.5.4 | only 2.x has Py3.13 wheels |
| fastmcp / streamlit / opentelemetry-sdk / otlp-grpc / python-dotenv | 0.4.1 / 1.36.0 / 1.24.0 / 1.24.0 / 1.0.1 | same | kept; verified |
| mcp | — | 1.30.0 | transitive of fastmcp 0.4.1 (resolver choice, `>=1,<2`) |

Other deviations: Gemini model ids (see [Gemini_Integration](../04_RAG/Gemini_Integration.md)); `opentelemetry-instrumentation-fastapi` is installed transitively but unusable (`pkg_resources`), so spans are manual.

## 3. Supporting packages added beyond the POC (purpose)

| Package | Purpose |
|---|---|
| PyJWT, bcrypt | JWT tokens and password hashing (POC requires JWT auth) |
| python-multipart | OAuth2 form login |
| email-validator | Pydantic `EmailStr` |
| structlog | structured logging (POC requirement) |
| httpx | FastAPI TestClient + AI-layer HTTP client |
| requests | declared as used by "the POC tool/test code" |
| pytest-cov | coverage (POC test spec) |
| react-router-dom (frontend) | page navigation |
| recharts (frontend) | charts — named by the POC |

The project instructions allow minimal supporting dependencies if their purpose is documented; this table is that record.

## 4. Notable transitive dependencies in the lock

`starlette 1.10.0` (FastAPI), `pydantic-core`, `langchain-core 1.8.0`, `langchain-text-splitters 1.1.3`, `langgraph-checkpoint 4.3.1`, `grpcio` + `google-api-core` (Gemini), `onnxruntime`, `kubernetes`, `PyPika`, `chroma-hnswlib` (ChromaDB), `pandas`, `pyarrow`, `altair`, `pydeck` (Streamlit), `opentelemetry-*` 1.24.0 / 0.45b0. (Presence taken from the lock file.)

## 5. Frontend packages

```json
"dependencies": { "@vitejs/plugin-react": "^6.3.0", "react": "^18.3.1", "react-dom": "^18.3.1",
                  "react-router-dom": "^6.30.6", "recharts": "^2.15.4", "vite": "^8.3.8" }
```
No `devDependencies`, no test runner, no linter/formatter config. Caret ranges are resolved by `package-lock.json`.

## 6. Updating dependencies safely

1. Change the pin in `requirements.txt` (with a reason comment).
2. Create a scratch venv, install, run `pip check`, `scripts/verify/verify_stack.py`, `verify_migration.py`, `verify_mcp.py`, then `pytest tests -q`.
3. Regenerate `requirements.lock` from the verified `.venv`.
4. Update `docs/DEPENDENCY_DEVIATIONS.md`.

Watch-outs: the `langchain-google-genai` / `langgraph-prebuilt` / `chromadb` + `posthog` pins are interlocked (see table); `fastmcp 0.4.1` ↔ `mcp 1.x`.
