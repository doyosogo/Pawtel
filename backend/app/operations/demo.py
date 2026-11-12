"""Small aggregate demo budgets. No IP trust, distributed-limit or bot-proof claim."""

import re
from collections import deque
from time import monotonic

from app.api.errors import error_response


class DemoWriteBudget:
    def __init__(self, app, enabled):
        self.app = app
        self.enabled = enabled
        self.auth_inflight = 0
        self.windows = {key: deque() for key in ("auth", "checkout", "media")}

    async def __call__(self, scope, receive, send):
        if self.enabled and scope["type"] == "http" and scope["method"] == "POST":
            path = scope["path"]
            group = (
                "auth"
                if path
                in {
                    "/api/v1/auth/login",
                    "/api/v1/auth/register",
                    "/api/v1/auth/verify-email",
                }
                else "checkout"
                if re.fullmatch(
                    r"/api/v1/bookings/[\da-fA-F-]{36}/checkout-session", path
                )
                else "media"
                if re.fullmatch(r"/api/v1/host/listings/[\da-fA-F-]{36}/images", path)
                else None
            )
            if group:
                window = self.windows[group]
                now = monotonic()
                while window and window[0] <= now - 60:
                    window.popleft()
                limit = 6 if group == "media" else 10
                # No await between checking and appending: one ASGI event loop/process.
                if len(window) >= limit:
                    response = error_response(
                        429,
                        "demo_rate_limited",
                        "Demo request limit reached. Try again in a minute.",
                    )
                    response.headers["Retry-After"] = "60"
                    response.headers["Cache-Control"] = "no-store"
                    return await response(scope, receive, send)
                window.append(now)
                if group == "auth":
                    if self.auth_inflight >= 2:
                        response = error_response(
                            429,
                            "demo_rate_limited",
                            "Demo sign-in is busy. Try again shortly.",
                        )
                        response.headers["Retry-After"] = "60"
                        return await response(scope, receive, send)
                    self.auth_inflight += 1
                    try:
                        return await self.app(scope, receive, send)
                    finally:
                        self.auth_inflight -= 1
        return await self.app(scope, receive, send)
