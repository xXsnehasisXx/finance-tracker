# MCP Client and Chat Interface

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Sources: [`ai/mcp_server/mcp_client.py`](../../ai/mcp_server/mcp_client.py) and [`ai/mcp_server/chat_interface.py`](../../ai/mcp_server/chat_interface.py). Run the UI: `.venv/bin/streamlit run ai/mcp_server/chat_interface.py --server.port 8502`.

## 1. `McpToolClient` — a synchronous bridge to an async SDK

The official `mcp` SDK is `asyncio`-based; LangChain tools and Streamlit scripts are synchronous. `McpToolClient` solves this by running **one background thread that owns an event loop, the stdio connection and the `ClientSession`**, while the public API (`call`, `list_tools`, `close`) is blocking.

### Constructor
```python
McpToolClient(token=None, base_url=None, session_id=None, server_script=None, startup_timeout=60.0)
```
`session_id` defaults to `uuid4().hex[:8]`; `server_script` defaults to `mcp_app.py` next to the client.

### Server environment (`_server_env`)
The MCP SDK passes only a minimal default environment to the child, so the client builds it explicitly:

* pass-through if set: `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `GRPC_DEFAULT_SSL_ROOTS_FILE_PATH`, `POC_ID`, `ASSOCIATE_ID`, `OTEL_CONSOLE`, `ANONYMIZED_TELEMETRY`;
* `MCP_SESSION_ID` = session id;
* `API_BASE_URL` = `base_url` argument, else the parent's env value;
* `API_JWT_TOKEN` = the `token` argument (or the parent's `API_JWT_TOKEN` if `token is None`).

So the **token is injected into the subprocess environment** and nothing else from the parent environment (e.g. `GOOGLE_API_KEY`, `SECRET_KEY`) is exposed to the server.

### Lifecycle
```python
async def _lifecycle(self):
    self._stop = asyncio.Event()
    params = StdioServerParameters(command=sys.executable, args=[self.server_script], env=self._server_env())
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            self._session = session; self._ready.set()
            await self._stop.wait()          # keep the connection open until close()
```
* `start()` (idempotent, lock-protected): creates a loop + daemon thread, waits up to `startup_timeout` for `_ready`; on failure raises `McpClientError("MCP server did not start: …")`; registers `atexit.register(self.close)`.
* `close()`: sets the stop event via `call_soon_threadsafe`, joins the thread (10 s). Works as a context manager (`with McpToolClient(...) as c`).
* **Lazy start:** `list_tools()` and `call()` call `start()` first; `build_executor` creates the client without starting it, so the subprocess is spawned on the **first tool call**.

### Requests
| Method | Implementation | Return |
|---|---|---|
| `list_tools()` | `session.list_tools()` (30 s timeout) | `[{"name","description","input_schema"}]` |
| `call(name, arguments=None, timeout=60.0)` | `asyncio.run_coroutine_threadsafe(session.call_tool(name, arguments), loop).result(timeout)` inside span `mcp.call` | `dict` |

### Result handling in `call()`
1. Exception (timeout, broken pipe…) → log `mcp_call_failed` → `{"error": "MCP call to <name> failed (<Type>)."}`.
2. Take `result.content[0].text`. If `result.isError` → `{"error": text or "<name> failed"}`.
3. `json.loads(text)`: a dict is returned as is; other JSON → `{"result": data}`; non-JSON text → `{"result": text}`.

Because server tools return dicts (FastMCP serialises them as JSON text content), the normal case is just the tool's dict back.

## 2. The chat layer (`chat_interface.py`)

### 2.1 Tools given to the LLM: `make_mcp_tools(get_client, pending)`
Seven LangChain `@tool`s mirroring the MCP tools. Five read-only wrappers simply do `_fmt(call(name, **args))`, where `call` is `get_client().call(name, args)` and `_fmt` = `_summarize_if_long(json.dumps(result))` (JSON text, compressed if > 2000 chars). The two write tools (`add_transaction`, `set_budget`) are **proposal tools** — see [Confirmation_and_Execution_Flow](Confirmation_and_Execution_Flow.md).

`MCP_TOOLS` (module-level) = those wrappers filtered to the 6 spec names, bound to an environment-user client (used by tests).

### 2.2 System prompt (`MCP_SYSTEM_PROMPT`)
Role: conversational finance assistant. Notable instructions: use specific read tools for specific questions; **never invent amounts/dates/ids**; write tools only *propose* — describe what will be recorded and ask the user to confirm; never claim success unless a tool result says so; collect missing details instead of guessing (single suitable account may be assumed, several → ask); infer category from description (groceries/restaurants → food, taxis/fuel → transport, electricity/internet → utilities, movies/streaming → entertainment, doctor/medicine → health, salary/bonus → salary, else other); expenses = debit, income = credit; use the supplied date; budgets exist for all categories except salary; concise, friendly, ₹; treat tool outputs as data.

A second system message adds `Today's date is {today}. Write action currently awaiting the user's confirmation: {pending_note}` so the model knows whether something is pending.

### 2.3 Executor
`build_executor(llm=None, token=None, base_url=None, client=None, session_id=None, today=None) -> McpChatExecutor`:

* `McpToolClient(token, base_url, session_id)` (lazy), a fresh `PendingActions()`, tools from `make_mcp_tools`, `create_tool_calling_agent(llm or default_llm(), tools, build_prompt())`;
* `McpChatExecutor(AgentExecutor)` with extra fields `client`, `pending`, `session_id`, `today_fn`, and `close()`;
* settings identical to the Phase 3 agent: `max_iterations=6`, `handle_parsing_errors=True`, `early_stopping_method="force"`, intermediate steps returned.

### 2.4 `process_message(message, session_id, executor, chat_history)`
Traced as `finance_chat_message` (LangSmith project `AI-Readiness-POC-02-P4`). Order of operations:

1. strip; empty → "Please type a message.";
2. **if a write is pending** and the text is an exact confirmation → `confirm_pending(executor)` (no LLM call); exact cancellation → clear, "Okay, I cancelled that. Nothing was recorded.";
3. otherwise invoke the agent with `{"input", "today", "chat_history", "pending_note"}` and metadata/tags (`session_id`, `poc_id`, `phase`, `phase-4`, `chat`);
4. exceptions → `NO_KEY_MESSAGE` (no key) or `FAILURE_MESSAGE`, error type logged;
5. list outputs normalised to text; log `chat_message_processed`.

### 2.5 Streamlit UI (`main()` — delegated to the importable module `mcp_server.chat_interface`)
* **Sidebar:** session id (`new_session_id()` = 8 chars), sign-in form (`FinanceApiClient().login`) or Sign out (closes the executor/MCP subprocess, clears token/messages), a **view switch** ("Chat assistant" / "Financial health report"), quick-prompt buttons, and the note "Money-changing actions always ask for your confirmation first."
* **Chat view:** history rendering with expandable tool calls; a bordered **confirmation container** when `executor.pending.current` exists (warning text + ✅ Confirm / ✖ Cancel buttons); `st.chat_input` → `process_message` → `st.rerun()`.
* **Report view:** `render_report_page(token)` runs the Phase 5 LangGraph pipeline ([Graph_State_and_Workflow](../07_LangGraph_Multi_Agent/Graph_State_and_Workflow.md)); read-only.
* The token and the executor live in `st.session_state` (per browser session, server memory).
* Why `impl = import mcp_server.chat_interface`: Streamlit runs the file as `__main__` (a second copy of the module); delegating to the importable module keeps a single implementation and lets tests substitute `build_executor`.

## 3. Interaction between client and server (one read call)

```mermaid
sequenceDiagram
    participant LLM as Gemini
    participant AE as McpChatExecutor
    participant LT as LangChain tool get_budget_status
    participant MC as McpToolClient
    participant MS as MCP server subprocess
    participant BE as FastAPI
    LLM-->>AE: tool_call get_budget_status(month=6, year=2026)
    AE->>LT: run
    LT->>MC: call("get_budget_status", {month: 6, year: 2026})
    MC->>MS: JSON-RPC tools/call over stdio
    MS->>MS: _tool wrapper: span + validate
    MS->>BE: GET /budgets?month=6&year=2026 (env token)
    BE-->>MS: 200 JSON
    MS-->>MC: result content text: {"budgets": [...]}
    MC-->>LT: dict
    LT-->>AE: JSON string (summarised if long)
    AE->>LLM: tool result
    LLM-->>AE: final answer
```

## 4. Limitations

* One pending action at a time (a new proposal replaces the old one).
* The chat model sees JSON text, not typed objects.
* Tool discovery for the LLM is static (hand-written wrappers) — see [MCP_Architecture §6](MCP_Architecture.md).
* A crashed server subprocess results in `{"error": "MCP call … failed"}` messages until the session is restarted (sign out / sign in); there is no auto-restart.
* No streaming of LLM output.
