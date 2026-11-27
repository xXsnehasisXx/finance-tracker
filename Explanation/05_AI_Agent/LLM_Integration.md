# LLM Integration (Agent)

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). How the Phase 3 agent obtains and uses its language model. General Gemini setup is in [Gemini_Integration](../04_RAG/Gemini_Integration.md); architecture in [Agent_Architecture](Agent_Architecture.md).

## 1. Selection and configuration

```python
def default_llm():
    from common.llm import MissingApiKeyError, chat_model_name, get_chat_model
    try:
        return get_chat_model(temperature=0)
    except MissingApiKeyError:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=chat_model_name(), google_api_key="missing-key", max_retries=0, timeout=5)
```

| Aspect | Value |
|---|---|
| Model | `GEMINI_MODEL` env (default `gemini-3.5-flash-lite`) |
| Temperature | 0 (repeatable tool choices) |
| Retries / timeout | 2 retries / 60 s with a key; **0 retries / 5 s** with the placeholder key |
| Without `GOOGLE_API_KEY` | builds a model with a placeholder key so the executor, tool list and prompt are inspectable offline (tests, structure checks); real calls will fail fast and `run_agent` reports a "not configured" message |
| Injection | `build_agent(llm=...)` accepts any LangChain chat model (tests use `ScriptedChatModel`) |

The same `default_llm()` is reused by the MCP chat executor (`ai/mcp_server/chat_interface.py`).

## 2. Function (tool) calling

`create_tool_calling_agent(llm, tools, prompt)` requires a chat model that implements `bind_tools`. Each `@tool` is converted to a Gemini function declaration (name, description from the docstring, JSON-schema parameters from the signature). The model answers with structured `tool_calls`; the executor executes them. Because tools take simple string arguments, validation of argument *content* is done inside the tool (see [Agent_Tools_and_Functions](Agent_Tools_and_Functions.md)). With Gemini 3 models, `langchain-google-genai` 3.1.0 is required to preserve "thought signatures" across tool-call turns.

## 3. Output handling

Gemini 3 may return content blocks; `run_agent` normalises:

```python
output = result.get("output", "")
if not isinstance(output, str):
    output = message_text(output) if not isinstance(output, list) else "".join(b.get("text","") for b in output if isinstance(b, dict))
```

so the UI always receives a string.

## 4. Failure handling

| Condition | Result |
|---|---|
| `GOOGLE_API_KEY` empty and the call fails | `NO_KEY_MESSAGE` — "The AI assistant is not configured: GOOGLE_API_KEY is not set. Add it to .env to use live Gemini features." |
| Any other exception from the LLM/network/executor | `FAILURE_MESSAGE` — "Sorry, I couldn't complete that request just now. Please try again." |
| Both | return value includes `"error": "<ExceptionName>"` and `"intermediate_steps": []`; the exception *type* (not message) is logged as `agent_query_failed` |

## 5. Context-window management

* Tool outputs > 2000 characters are summarised (`agent/summarizer.py`) by another call to the same model (temperature 0) using `PromptTemplate | llm | message_text`. If that call fails or returns empty, a deterministic truncation to 1,500 characters plus ` … [truncated: summary unavailable]` is used (`test_ctx_02b_summarizer_falls_back_when_llm_unavailable`).
* Chat history is passed in full; no trimming (limitation).

## 6. Observability

`@traceable_if_enabled(name="finance_agent_query", project_name="AI-Readiness-POC-02-P3")` on `run_agent`. LangSmith is only active when `LANGCHAIN_TRACING_V2=true` **and** a LangSmith key exists; otherwise `configure_tracing()` switches tracing off and prints a one-line JSON notice to stderr. Local logging/spans are always on (JSON logs to stdout; spans printed only if `OTEL_CONSOLE=true`).

## 7. Data safety rules enforced around the LLM

* The model receives only tool outputs for the signed-in user.
* It cannot write data (no write tools).
* The prompt tells it to treat tool outputs as data, not instructions (guards against text in e.g. a transaction description trying to hijack the agent). This is a prompt-level mitigation, not a technical sandbox.
