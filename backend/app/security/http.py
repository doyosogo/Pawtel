import logging
import re

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.errors import error_response
from app.core.config import Settings

logger = logging.getLogger(__name__)


class AuthHTTPMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        if (
            request.url.path.startswith("/api/v1/")
            and not (
                request.method == "POST"
                and request.url.path == "/api/v1/webhooks/stripe"
            )
            and request.method
            not in {
                "GET",
                "HEAD",
                "OPTIONS",
            }
        ):
            origin = request.headers.get("origin")
            if origin is not None and origin not in self.settings.backend_cors_origins:
                return self.no_store(
                    error_response(
                        403, "untrusted_origin", "Request origin is not allowed."
                    )
                )
            if request.headers.get("x-pawtel-request") != "1":
                return self.no_store(
                    error_response(
                        403,
                        "request_header_required",
                        "X-PAWTEL-Request: 1 is required.",
                    )
                )
            if request.headers.get("content-type", "").split(";")[
                0
            ].strip().lower() != "application/json" and not (
                request.method == "POST"
                and re.fullmatch(
                    r"/api/v1/host/listings/[0-9a-fA-F-]{36}/images", request.url.path
                )
            ):
                return self.no_store(
                    error_response(415, "json_required", "Use application/json.")
                )
        try:
            response = await call_next(request)
        except Exception as error:
            # No exception text/traceback/body/credentials. Operational telemetry can
            # safely count exception types without retaining sensitive payloads.
            logger.error("Unhandled application error: %s", type(error).__name__)
            response = error_response(
                500, "internal_error", "The request could not be completed."
            )
        if request.url.path.startswith("/api/v1/"):
            self.no_store(response)
        return response

    @staticmethod
    def no_store(response: Response) -> Response:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response
