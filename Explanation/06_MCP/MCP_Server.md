# MCP Server

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Source: [`ai/mcp_server/mcp_app.py`](../../ai/mcp_server/mcp_app.py) (207 lines). Tool reference: [MCP_Tools](MCP_Tools.md).

## 1. Initialisation

```python
from fastmcp import FastMCP
PHASE = 4
logger = get_logger("mcp_app", PHASE)
mcp = FastMCP("Finance Tracker MCP Server")
```

Tools are plain Python functions registered with `@mcp.tool()`. FastMCP inspects each function's name, docstring and type hints to produce the MCP tool name, description and JSON input schema. The decorator returns the original function, so every tool is also an importable, directly-callable function (used by unit tests and by `chat_interface` for shared validators).

## 2. Running and transport

```python
def main():
    configure_logging(PHASE, stream=sys.stderr)      # stdout is the MCP protocol channel
    logger.info("mcp_server_started", tools=[...7 names...], operation="startup", status="success")
    mcp.run()                                        # FastMCP.run(transport="stdio") default
```

* Command: `.venv/bin/python ai/mcp_server/mcp_app.py` (needs `API_JWT_TOKEN`; optional `API_BASE_URL`, `MCP_SESSION_ID`).
* **Transport: stdio only** (JSON-RPC over stdin/stdout). The server is normally *spawned by `McpToolClient`*, not started by hand. Running it by hand just waits for protocol messages on stdin.
* All logs are JSON to **stderr** (`PrintLoggerFactory(file=sys.stderr)`) so they cannot corrupt the protocol stream.

## 3. Identity and configuration (environment of the server process)

| Variable | Used for |
|---|---|
| `API_JWT_TOKEN` | bearer token sent to the REST API — the **only** source of user identity |
| `API_BASE_URL` | backend base URL (default in `FinanceApiClient`: `http://localhost:8000/api/v1`) |
| `MCP_SESSION_ID` | attached to spans/logs (`mcp.session_id`) for correlation |
| `POC_ID`, `ASSOCIATE_ID`, `OTEL_CONSOLE`, `ANONYMIZED_TELEMETRY` | passed through by the client for log fields |

`_client()` creates a new `FinanceApiClient(os.getenv("API_BASE_URL"), os.getenv("API_JWT_TOKEN") or None)` on every tool call; the token is never accepted as a tool argument and never logged.

## 4. The `_tool` runner (cross-cutting behaviour)

```python
def _tool(name, fn, **log_fields):
    with span("mcp.tool_invoke", **{"mcp.tool_name": name, "mcp.session_id": session_id}) as sp:
        try:    result = fn()
        except Exception as exc:
            logger.error("mcp_tool_failed", tool=name, session_id=session_id, error_type=type(exc).__name__)
            result = {"error": f"Unexpected error in {name} ({type(exc).__name__})."}
        ok = "error" not in result
        sp.set_attribute("mcp.success", ok)
    logger.info("mcp_tool_invoked", tool=name, session_id=session_id, success=ok, duration_ms=..., operation="mcp_tool",
                status="success" if ok else "failure", **log_fields)
    return result
```

Guarantees: every call gets a span + one structured log line; unexpected exceptions become `{"error": …}`; `log_fields` carry non-sensitive context only (amount/category/account_id — never tokens). `_result(res)` converts an `ApiResult` to `res.data` or `{"error": res.error}`.

## 5. Input validators (shared with the chat layer)

| Function | Checks (returns error text or `None`) |
|---|---|
| `validate_transaction_args(account_id, amount, transaction_type, category, description, transaction_date)` | `account_id` positive int (not bool); `amount` number > 0 (not bool); `transaction_type ∈ {debit, credit}`; `category ∈ CATEGORIES`; non-blank description; `transaction_date` ISO `YYYY-MM-DD` (via `date.fromisoformat`) |
| `validate_budget_args(category, monthly_limit, month, year)` | `category ∈ BUDGET_CATEGORIES` (all except `salary`); `monthly_limit` > 0; `month` int 1–12; `year` int 2000–2100 |
| `_check_date(value, field)` | ISO date check, message `"<field> must be a date in YYYY-MM-DD format (got '…')."` |

Constants: `CATEGORIES = (food, transport, utilities, entertainment, health, salary, other)`, `BUDGET_CATEGORIES` = same minus `salary`, `TRANSACTION_TYPES = (debit, credit)`.

These are *convenience* validations for clear messages; the backend repeats and extends them.

## 6. Error model

| Source | Returned to the client |
|---|---|
| Local validation failure | `{"error": "<specific message>"}` |
| Backend 4xx/5xx or connectivity | `{"error": "<mapped message>"}` from `FinanceApiClient` (e.g. "Finance API service unavailable. Please make sure the backend is running.", "Not authenticated: your session is missing or expired…", "Conflict: …") |
| Unexpected Python exception | `{"error": "Unexpected error in <tool> (<Type>)."}` |
| Success | the backend JSON (`dict`), or a wrapper dict (`{"budgets": [...]}`, `{"accounts": [...]}`) |

## 7. Testing

`tests/phase4/test_mcp_server.py`: function-level tests (`test_mcp_03…08`), backend rules still apply through the tool, identity from environment, logging without token, and **real protocol tests** that spawn the server over stdio against a real HTTP backend subprocess (`test_protocol_tool_discovery_and_schemas`, `…invocation_returns_real_backend_data`, `…write_then_read_back`, `…error_handling`, `…multiple_and_concurrent_calls`, `…users_are_isolated_by_server_process`, `…bad_token_and_unreachable_backend_are_reported`, `…client_lifecycle`). Verification script: `scripts/verify/verify_mcp.py` with fixture server `scripts/verify/mcp_server_fixture.py`.
