"""Request guard middleware: security headers, request ids and a request size limit.

Implemented as plain ASGI so it also wraps streamed (server-sent event) responses.
"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from wellscope.observability import request_id_var

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 16_384
PAYLOAD_TOO_LARGE = 413
INTERNAL_ERROR = 500
LENGTH_REQUIRED = 411
BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    )
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class RequestGuard:
    """Gives each request an id, rejects oversized bodies and adds security headers."""

    def __init__(self, app: ASGIApp, max_body_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI entry point."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        try:
            await self._handle(scope, receive, send, request_id)
        finally:
            request_id_var.reset(token)

    async def _handle(self, scope: Scope, receive: Receive, send: Send, request_id: str) -> None:
        started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
                headers["X-Request-ID"] = request_id
                if scope["path"].startswith("/api/"):
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        rejection = self._reject(scope)
        if rejection is not None:
            await _send_error(send_with_headers, *rejection, request_id)
            return
        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            # Rendered here, not by the outer server-error middleware, so the response keeps
            # the security headers and the log line keeps the request id.
            logger.exception("unhandled error")
            if started:
                raise
            await _send_error(
                send_with_headers, INTERNAL_ERROR, "internal_error", "Unexpected error.", request_id
            )

    def _reject(self, scope: Scope) -> tuple[int, str, str] | None:
        if scope["method"] not in BODY_METHODS:
            return None
        length = Headers(scope=scope).get("content-length")
        if length is None:
            return LENGTH_REQUIRED, "length_required", "A Content-Length header is required."
        if not length.isdigit() or int(length) > self.max_body_bytes:
            limit = self.max_body_bytes
            return PAYLOAD_TOO_LARGE, "payload_too_large", f"Requests are limited to {limit} bytes."
        return None


async def _send_error(send: Send, status: int, code: str, message: str, request_id: str) -> None:
    """A JSON error envelope; the details stay in the log."""
    body = json.dumps({"error": {"code": code, "message": message, "request_id": request_id}})
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body.encode()})
