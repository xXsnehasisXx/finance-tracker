# Dependency deviations from the POC (Python 3.13.1)

Python 3.13.1 is mandated. Pins in `extras/` (written for 2024 releases) that cannot run on it were upgraded **minimally**.
All other POC pins are kept. Evidence: `scripts/verify/*.py` (run from the project `.venv`).

| Package | POC pin | Final | Reason |
|---|---|---|---|
| langchain | 0.2.6 | 1.0.8 | requires `numpy<2`; no Python 3.13 wheels; langchain-google-genai>=3 needs core 1.x |
| langchain-classic | (in langchain) | 1.0.8 | langchain 1.x moved `AgentExecutor`, `create_tool_calling_agent`, summarize chain here |
| langchain-community | implied | 0.4.2 | `Chroma`, `TextLoader` used by POC code |
| langchain-google-genai | 1.0.6 | 3.1.0 | 1.0.6 needs `langchain-core<0.3`; 2.x lacks Gemini 3 thought signatures; 3.0.3 drops signatures on function-call-only turns |
| google-ai-generativelanguage | 0.6.4 | 0.12.0 | `Part.thought_signature` exists only from 0.7.0 |
| langgraph | 0.1.17 | 1.0.10 | langchain-core cap |
| langgraph-prebuilt | - | 1.0.8 | 1.0.13 breaks `import langchain.agents` (needs langgraph>=1.2) |
| langsmith | 0.1.77 | 0.14.17 | incompatible with langchain-core 1.x |
| chromadb | 0.5.3 | 0.5.7 | first release without the `numpy<2` cap |
| chroma-hnswlib | 0.7.3 | 0.7.6 | no wheel; compiles from source (Apple clang) |
| posthog | - | 5.4.0 | chromadb 0.5.7 telemetry breaks with posthog>=6 |
| numpy | <2 | 2.5.4 | only 2.x has Python 3.13 wheels |
| fastmcp / streamlit / opentelemetry-sdk / otlp-grpc / python-dotenv | 0.4.1 / 1.36.0 / 1.24.0 / 1.24.0 / 1.0.1 | same | kept; verified |
| mcp (MCP SDK) | - | 1.30.0 | transitive of fastmcp 0.4.1 |

## Other deviations
- **Gemini model:** POC says Gemini 2.0 Flash, which Google has shut down. `GEMINI_MODEL` (env, default `gemini-3.6-flash`) replaces it. Provider unchanged. External API lifecycle compatibility change. **Not yet verified live (no `GOOGLE_API_KEY`).**
- **OpenTelemetry:** `opentelemetry-instrumentation-fastapi` is installed transitively but unusable (`pkg_resources`); manual spans (SDK + console exporter) are used.
- **Added supporting packages:** PyJWT, bcrypt, python-multipart, email-validator, structlog, httpx, requests, pytest-cov (required by the POC specs).
- **Frontend supporting packages:** react-router-dom (navigation), recharts (POC-named).

## Live verification status
Live Gemini checks (`scripts/verify/verify_gemini_compat.py`) are **SKIPPED** until `GOOGLE_API_KEY` is provided.
