import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id = ContextVar("request_id", default=None)
EVENTS = {
    "http_request",
    "unexpected_error",
    "database_error",
    "readiness_failed",
    "startup_ready",
    "startup_not_ready",
    "shutdown_complete",
}
SERVER_MESSAGES = {
    "Waiting for application startup.",
    "Application startup complete.",
    "Waiting for application shutdown.",
    "Application shutdown complete.",
    "Shutting down",
}


class SafeJSONFormatter(logging.Formatter):
    """Allowlist fields, never format arbitrary messages/args or exception values."""

    def format(self, record):
        event = getattr(record, "event", None)
        data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": event
            if isinstance(event, str) and event in EVENTS
            else "server_event",
            "request_id": getattr(record, "request_id", None) or request_id.get(),
        }
        if isinstance(record.msg, str) and record.msg in SERVER_MESSAGES:
            data["message"] = record.msg
        for field in ("method", "route", "status", "duration_ms", "exception_type"):
            if hasattr(record, field):
                data[field] = getattr(record, field)
        if record.exc_info:
            data["exception_type"] = record.exc_info[0].__name__
        return json.dumps(data, separators=(",", ":"))


def log_event(event, *, level=logging.INFO, **fields):
    logging.getLogger("pawtel").log(level, event, extra={"event": event, **fields})


def configure_logging():
    logger = logging.getLogger("pawtel")
    if not any(
        getattr(handler, "pawtel_handler", False) for handler in logger.handlers
    ):
        handler = logging.StreamHandler()
        handler.pawtel_handler = True
        handler.setFormatter(SafeJSONFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
