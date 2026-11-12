import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import setup_tracing, span
from app.database import init_db
from app.routers import accounts, auth, budgets, dashboard, transactions

configure_logging()
setup_tracing()
logger = get_logger("http")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logger.info("app_started", operation="startup", status="success")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Personal Finance Tracker & Analytics (POC-02)", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        with span("http.request", **{"http.method": request.method, "http.route": request.url.path}) as sp:
            try:
                response = await call_next(request)
            except Exception:
                logger.error("unhandled_exception", method=request.method, path=request.url.path, exc_info=True)
                raise
            sp.set_attribute("http.status_code", response.status_code)
        logger.info(
            "http_request", operation="http_request", method=request.method, path=request.url.path,
            status_code=response.status_code, duration_ms=int((time.perf_counter() - start) * 1000),
            status="success" if response.status_code < 400 else "failure",
        )
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    api = "/api/v1"
    for module in (auth, accounts, transactions, budgets, dashboard):
        app.include_router(module.router, prefix=api)

    @app.get(f"{api}/health", tags=["ops"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
