import logging
import re
from collections import deque
from time import perf_counter
from uuid import UUID, uuid4

from app.api.errors import error_response
from app.operations.logging import log_event, request_id

JSON_LIMIT = 64 * 1024
WEBHOOK_LIMIT = 1024 * 1024
IMAGE_LIMIT = 5 * 1024 * 1024
IMAGE_PATH = re.compile(r"/api/v1/host/listings/[0-9a-fA-F-]{36}/images")


def correlation(headers):
    values = [
        value.decode("latin1")
        for key, value in headers
        if key.lower() == b"x-request-id"
    ]
    try:
        value = values[0]
        if len(values) != 1 or str(UUID(value)) != value.lower():
            raise ValueError()
        return str(UUID(value))
    except IndexError, ValueError, AttributeError:
        return str(uuid4())


class OperationsMiddleware:
    def __init__(self, app, settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        ident = correlation(scope["headers"])
        scope.setdefault("state", {})["request_id"] = ident
        token = request_id.set(ident)
        started = perf_counter()
        status = 500
        response_started = False
        incoming = {key.lower(): value for key, value in scope["headers"]}
        origin = incoming.get(b"origin", b"").decode("latin1")

        async def response_send(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"x-request-id"
                ]
                headers.extend(
                    [
                        (b"x-request-id", ident.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                        (b"x-frame-options", b"DENY"),
                        (
                            b"permissions-policy",
                            b"camera=(), microphone=(), geolocation=()",
                        ),
                        (
                            b"content-security-policy",
                            b"frame-ancestors 'none'; base-uri 'self'; "
                            b"object-src 'none'",
                        ),
                    ]
                )
                if self.settings.app_env == "production":
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                # Early errors bypass inner CORS; preserve exact-origin policy.
                if origin in self.settings.backend_cors_origins and not any(
                    k.lower() == b"access-control-allow-origin" for k, v in headers
                ):
                    headers.extend(
                        [
                            (b"access-control-allow-origin", origin.encode()),
                            (b"access-control-allow-credentials", b"true"),
                            (b"access-control-expose-headers", b"X-Request-ID"),
                            (b"vary", b"Origin"),
                        ]
                    )
                message = {**message, "headers": headers}
            await send(message)

        async def reject(code, message):
            await error_response(413, code, message)(scope, receive, response_send)

        try:
            path = scope.get("path", "")
            limit = (
                IMAGE_LIMIT
                if scope["method"] == "POST" and IMAGE_PATH.fullmatch(path)
                else WEBHOOK_LIMIT
                if path == "/api/v1/webhooks/stripe"
                else JSON_LIMIT
            )
            try:
                length = int(incoming.get(b"content-length", b"0"))
            except ValueError:
                length = limit + 1
            if length < 0 or length > limit:
                return await reject("request_too_large", "Request body is too large.")
            chunks = deque()
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body = message.get("body", b"")
                size += len(body)
                if size > limit:
                    return await reject(
                        "request_too_large", "Request body is too large."
                    )
                chunks.append(message)
                if not message.get("more_body", False):
                    break

            async def replay():
                return chunks.popleft() if chunks else await receive()

            await self.app(scope, replay, response_send)
        except Exception as error:
            log_event(
                "unexpected_error",
                level=logging.ERROR,
                exception_type=type(error).__name__,
            )
            if response_started:
                raise
            await error_response(
                500, "internal_error", "The request could not be completed."
            )(scope, receive, response_send)
        finally:
            route = getattr(scope.get("route"), "path", "<unmatched>")
            log_event(
                "http_request",
                request_id=ident,
                method=(
                    scope["method"]
                    if scope["method"]
                    in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
                    else "OTHER"
                ),
                route=route,
                status=status,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            request_id.reset(token)
