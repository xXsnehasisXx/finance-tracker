"""Synchronous client for the Phase 4 MCP server over the real MCP protocol (stdio, JSON-RPC via the `mcp` SDK).

One persistent server subprocess per signed-in user/session. The SDK is async; a background thread owns the event loop
and the session, and `call()` is a plain blocking function that LangChain tools / Streamlit can use.
"""
import asyncio
import atexit
import json
import os
import sys
import threading
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from common.observability import get_logger, span  # noqa: E402

logger = get_logger("mcp_client", 4)

SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_app.py")
# Environment variables the server subprocess may inherit (the MCP SDK passes only a minimal default environment).
_PASSTHROUGH = ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH", "POC_ID", "ASSOCIATE_ID", "OTEL_CONSOLE", "ANONYMIZED_TELEMETRY")


class McpClientError(RuntimeError):
    pass


class McpToolClient:
    def __init__(self, token: str | None = None, base_url: str | None = None, session_id: str | None = None,
                 server_script: str | None = None, startup_timeout: float = 60.0):
        self.token = token
        self.base_url = base_url
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.server_script = server_script or SERVER_SCRIPT
        self.startup_timeout = startup_timeout
        self._loop = None
        self._thread = None
        self._session = None
        self._stop = None
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------ lifecycle
    def _server_env(self) -> dict:
        env = {k: os.environ[k] for k in _PASSTHROUGH if k in os.environ}
        env["MCP_SESSION_ID"] = self.session_id
        if self.base_url:
            env["API_BASE_URL"] = self.base_url
        elif os.getenv("API_BASE_URL"):
            env["API_BASE_URL"] = os.environ["API_BASE_URL"]
        token = self.token if self.token is not None else os.getenv("API_JWT_TOKEN", "")
        if token:
            env["API_JWT_TOKEN"] = token
        return env

    async def _lifecycle(self):
        self._stop = asyncio.Event()
        try:
            params = StdioServerParameters(command=sys.executable, args=[self.server_script], env=self._server_env())
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._ready.set()
                    await self._stop.wait()
        except Exception as exc:  # noqa: BLE001
            self._error = exc
        finally:
            self._session = None
            self._ready.set()

    def start(self) -> "McpToolClient":
        with self._lock:
            if self._thread is not None:
                return self
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=lambda: self._loop.run_until_complete(self._lifecycle()), name=f"mcp-{self.session_id}", daemon=True)
            self._thread.start()
            atexit.register(self.close)
        if not self._ready.wait(self.startup_timeout) or self._session is None:
            self.close()
            raise McpClientError(f"MCP server did not start: {self._error or 'timeout'}")
        logger.info("mcp_client_started", session_id=self.session_id, operation="mcp_connect", status="success")
        return self

    def close(self) -> None:
        with self._lock:
            thread, loop, stop = self._thread, self._loop, self._stop
            self._thread = None
        if thread is None:
            return
        if loop is not None and stop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(stop.set)
        thread.join(timeout=10)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------ requests
    def _run(self, coro, timeout: float):
        if self._session is None:
            raise McpClientError("MCP session is not running")
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def list_tools(self) -> list[dict]:
        self.start()
        tools = self._run(self._session.list_tools(), 30).tools
        return [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema} for t in tools]

    def call(self, name: str, arguments: dict | None = None, timeout: float = 60.0) -> dict:
        """Calls an MCP tool and returns its result as a dict ({"error": ...} on failure). Never raises for tool errors."""
        self.start()
        with span("mcp.call", **{"mcp.tool_name": name, "mcp.session_id": self.session_id}):
            try:
                result = self._run(self._session.call_tool(name, arguments or {}), timeout)
            except Exception as exc:  # noqa: BLE001
                logger.error("mcp_call_failed", tool=name, session_id=self.session_id, error_type=type(exc).__name__)
                return {"error": f"MCP call to {name} failed ({type(exc).__name__})."}
        text = result.content[0].text if result.content else ""
        if result.isError:
            return {"error": text or f"{name} failed"}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {"result": text}
        return data if isinstance(data, dict) else {"result": data}
