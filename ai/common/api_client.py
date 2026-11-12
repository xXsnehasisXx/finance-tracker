"""HTTP client for the Finance REST API used by the AI components.

The AI layer never touches the database: every read/write goes through the validated REST routes with the caller's own
bearer token, so authorization and business rules are enforced by the backend. Errors become readable messages.
"""
import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv

from common.observability import get_logger, span

load_dotenv()
logger = get_logger("api_client")

DEFAULT_BASE_URL = "http://localhost:8000/api/v1"


@dataclass
class ApiResult:
    ok: bool
    data: Any = None
    status: int | None = None
    error: str = ""


def default_base_url() -> str:
    return os.getenv("API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except Exception:  # noqa: BLE001
        return response.text[:200]
    if isinstance(detail, list):
        return "; ".join(f"{'.'.join(str(p) for p in e.get('loc', []) if p != 'body')}: {e.get('msg')}" for e in detail)
    return str(detail)


class FinanceApiClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or default_base_url()).rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def login(self, email: str, password: str) -> ApiResult:
        return self.request("POST", "/auth/login", data={"username": email, "password": password}, auth=False)

    def request(self, method: str, path: str, params: dict | None = None, json: dict | None = None, data: dict | None = None, auth: bool = True) -> ApiResult:
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        with span("api.call", **{"api.endpoint": path, "api.method": method}) as sp:
            try:
                resp = httpx.request(method, f"{self.base_url}{path}", params=clean, json=json, data=data,
                                     headers=self._headers() if auth else {}, timeout=self.timeout)
            except httpx.TimeoutException:
                logger.error("api_call_failed", path=path, error_type="timeout")
                return ApiResult(False, error="The Finance API request timed out. Please try again later.")
            except httpx.HTTPError as exc:
                logger.error("api_call_failed", path=path, error_type=type(exc).__name__)
                return ApiResult(False, error="Finance API service unavailable. Please make sure the backend is running.")
            sp.set_attribute("api.status_code", resp.status_code)

        if resp.status_code == 204:
            return ApiResult(True, None, 204)
        if resp.is_success:
            return ApiResult(True, resp.json(), resp.status_code)
        message = {
            401: "Not authenticated: your session is missing or expired. Please sign in again.",
            403: "Access denied: that resource does not belong to your account.",
            404: f"Not found: {_detail(resp)}",
            409: f"Conflict: {_detail(resp)}",
            422: f"Invalid request: {_detail(resp)}",
            400: _detail(resp),
        }.get(resp.status_code, f"The Finance API returned an error (HTTP {resp.status_code}).")
        if resp.status_code >= 500:
            logger.error("api_call_failed", path=path, error_type=f"http_{resp.status_code}")
        return ApiResult(False, status=resp.status_code, error=message)

    def get(self, path: str, **params) -> ApiResult:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: dict) -> ApiResult:
        return self.request("POST", path, json=body)
