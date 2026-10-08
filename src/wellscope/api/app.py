"""FastAPI application factory: API routes, the static web app, middleware and error envelopes."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from wellscope import __version__
from wellscope.api.ratelimit import RateLimiter
from wellscope.api.routes import router
from wellscope.api.security import RequestGuard
from wellscope.config import Settings
from wellscope.qa.service import QAService
from wellscope.retrieval.ports import ReportIndex

logger = logging.getLogger(__name__)
LLM_CONCURRENCY = 4
INTERNAL_ERROR = 500
UNPROCESSABLE = 422
ERROR_CODES = {
    400: "bad_request",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    422: "invalid_request",
    429: "rate_limited",
}
WILDCARD_HOSTS = frozenset({"0.0.0.0", "::"})  # noqa: S104 - compared against, not bound to


@dataclass(frozen=True)
class Services:
    """What the web app needs, built by the composition root (``wellscope.bootstrap``)."""

    qa: QAService
    index: ReportIndex
    model_configured: bool


@dataclass(frozen=True)
class AppState:
    """Per-application state shared by the routes."""

    settings: Settings
    services: Services
    limiter: RateLimiter
    llm_slots: asyncio.Semaphore


def create_app(settings: Settings, services: Services) -> FastAPI:
    """The WellScope web application."""
    # Windows can map .js to text/plain in its registry, which browsers refuse for modules.
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    app = FastAPI(
        title="WellScope",
        version=__version__,
        summary="Grounded questions and answers over daily drilling and geological well reports.",
    )
    app.state.wellscope = AppState(
        settings=settings,
        services=services,
        limiter=RateLimiter(settings.rate_limit_per_min),
        llm_slots=asyncio.Semaphore(LLM_CONCURRENCY),
    )
    # FastAPI types handlers as taking ``Exception``; these take the subclass they handle.
    app.add_exception_handler(RequestValidationError, _validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unexpected_error)
    app.include_router(router)
    app.mount("/", StaticFiles(directory=_web_root(), html=True), name="web")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts(settings))
    app.add_middleware(RequestGuard)
    return app


def _web_root() -> Path:
    return Path(str(files("wellscope") / "web"))


def _allowed_hosts(settings: Settings) -> list[str]:
    hosts = list(settings.allowed_hosts)
    if settings.host not in WILDCARD_HOSTS and settings.host not in hosts:
        hosts.append(settings.host)
    return hosts


def _error(
    request: Request, status: int, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    code = ERROR_CODES.get(status, "internal_error" if status >= INTERNAL_ERROR else "error")
    request_id = getattr(request.state, "request_id", "-")
    body = {"error": {"code": code, "message": message, "request_id": request_id}}
    return JSONResponse(body, status_code=status, headers=headers)


async def _validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    """422 naming the first invalid field; submitted values are never echoed back."""
    first = error.errors()[0] if error.errors() else {}
    where = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    message = f"{where}: {first.get('msg', 'invalid value')}" if where else "Invalid request."
    return _error(request, UNPROCESSABLE, message)


async def _http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    headers = dict(error.headers) if error.headers else None
    return _error(request, error.status_code, str(error.detail), headers)


async def _unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=error)
    return _error(request, INTERNAL_ERROR, "Unexpected error.")
