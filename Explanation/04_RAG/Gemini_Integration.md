# Gemini Integration

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Single integration point: [`ai/common/llm.py`](../../ai/common/llm.py). Used by RAG ([RAG_Chain_and_Prompting](RAG_Chain_and_Prompting.md)), the agent ([LLM_Integration](../05_AI_Agent/LLM_Integration.md)), the MCP chat and the LangGraph narratives.

## 1. Provider and library

Google Gemini via **`langchain-google-genai` 3.1.0**: `ChatGoogleGenerativeAI` (chat) and `GoogleGenerativeAIEmbeddings` (embeddings). Authentication: API key in env `GOOGLE_API_KEY` (never logged, never hard-coded). The project docs mention that Google's gRPC endpoints are used (`google-ai-generativelanguage 0.12.0`, `grpcio`).

## 2. Model selection — what the specification says vs. what the code does

| | POC specification | Code (`llm.py`) |
|---|---|---|
| Chat model | Gemini 2.0 Flash | env `GEMINI_MODEL`, default **`gemini-3.5-flash-lite`** |
| Embedding model | `text-embedding-004` | env `EMBEDDING_MODEL`, default **`models/gemini-embedding-001`** |

Per `docs/DEPENDENCY_DEVIATIONS.md` and `PROJECT_PROGRESS.md`, Gemini 2.0 Flash was shut down by Google and `text-embedding-004` returns 404 on the current API; the substitute defaults are described as "confirmed working with the project's Gemini key on the developer's personal laptop". **This documentation could not verify live Gemini behaviour** (no key/network path in this environment; all 28 live tests are skipped). Per the project rule, the POC/code discrepancy is reported here and the code's defaults are followed.

All model ids live in one place:

```python
DEFAULT_CHAT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
RETIRED_MODELS = {
  "GEMINI_MODEL": {"gemini-3.6-flash": DEFAULT_CHAT_MODEL, "gemini-2.0-flash": DEFAULT_CHAT_MODEL},
  "EMBEDDING_MODEL": {"models/text-embedding-004": DEFAULT_EMBEDDING_MODEL, "text-embedding-004": DEFAULT_EMBEDDING_MODEL},
}
```

`_model_from_env(var, default)` reads the env var (blank → default); if the value is in `RETIRED_MODELS[var]` it logs `retired_model_id_replaced` (variable, configured, using) and substitutes the default. A stale `.env` therefore cannot silently break the app (`test_stale_env_values_cannot_override_the_default`).

`GEMINI_FALLBACK_MODEL` appears in `.env.example` but is used **only** by `scripts/verify/verify_gemini_compat.py`; the application does not implement a runtime fallback model.

## 3. Factories

```python
def get_chat_model(temperature: float = 0.1):
    return ChatGoogleGenerativeAI(model=chat_model_name(), google_api_key=_api_key(),
                                  temperature=temperature, max_retries=2, timeout=60)

def get_embeddings():
    return GoogleGenerativeAIEmbeddings(model=embedding_model_name(), google_api_key=_api_key())
```

| Caller | Temperature | Why |
|---|---|---|
| RAG chain (`build_rag_chain`) | 0.1 | factual, mostly deterministic |
| Phase 3 agent / MCP chat (`default_llm`) | 0 | stable tool selection |
| Summariser (`summarize_text`) | 0 | faithful compression |
| LangGraph narratives (`_llm`) | 0.2 | slightly more natural prose, still guarded |

`max_retries=2, timeout=60`: bounded on purpose — the code comment notes the library default (6 retries with backoff) would hang for a long time on a bad model id.

`_api_key()` raises `MissingApiKeyError("GOOGLE_API_KEY is not set. Add it to .env to use live Gemini features.")` when the key is missing. Consumers handle it: the Streamlit apps show it; `agent.default_llm()` builds a dummy model so the agent structure remains inspectable offline (the key is only needed when the model is called); the LangGraph pipeline switches to deterministic mode.

## 4. Gemini 3 response format: `message_text`

Gemini 3 models can return `AIMessage.content` as a **list of blocks** (text, thinking, signature) instead of a string.

```python
def message_text(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str): return content
    parts = []
    for block in content or []:
        if isinstance(block, str): parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text": parts.append(block.get("text", ""))
    return "".join(parts)
```

Used in the RAG chain, summariser, agent output handling and narratives, so hidden "thinking" blocks never reach users. The agent/chat code additionally normalises list outputs.

## 5. Tool calling with Gemini 3

`langchain-google-genai` 3.1.0 is pinned because earlier releases lose Gemini 3 **thought signatures** on function-call turns (documented in `requirements.txt` and the deviations doc). This matters for the Phase 3/4 agents (`create_tool_calling_agent`) which depend on multi-step tool calls.

## 6. Error handling and observability

* Network/quota/model errors surface as exceptions from the library → caught at each entry point (`ask_question`, `run_agent`, `process_message`, `narrate`) and converted to friendly messages (or silently to deterministic mode for narratives).
* The "no key" case produces a specific configuration message (`NO_KEY_MESSAGE`) instead of a generic failure.
* Corporate TLS interception can break gRPC to Google (`CERTIFICATE_VERIFY_FAILED`); optional helpers `scripts/make_ca_bundle.sh`, `scripts/ca_allowlist.txt`, `scripts/dev_env.sh` exist, but verification is never disabled by the project and the helpers are documented as not used.
* Optional LangSmith tracing (env-driven) records LLM runs; see [Security_and_Configuration](../08_Deployment_and_DevOps/Security_and_Configuration.md).

## 7. Cost/latency considerations

Chat requests carry ≤ 4 chunks (RAG) or tool outputs capped around 2,000 characters before summarisation (agent), keeping prompts small. Agent loops are capped at 6 iterations. There is no response caching and no streaming (answers appear after generation completes).
