"""Request guard middleware: security headers, request ids and a request size limit.

Implemented as plain ASGI so it also wraps streamed (server-sent event) responses.
"""

from __future__ import annotations

import json
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from wellscope.observability import request_id_var

MAX_BODY_BYTES = 16_384
PAYLOAD_TOO_LARGE = 413
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
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
                headers["X-Request-ID"] = request_id
                if scope["path"].startswith("/api/"):
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        rejection = self._reject(scope)
        if rejection is None:
            await self.app(scope, receive, send_with_headers)
            return
        status, code, message = rejection
        body = json.dumps({"error": {"code": code, "message": message, "request_id": request_id}})
        await send_with_headers(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body.encode()})

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
