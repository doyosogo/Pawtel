from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.errors import install_error_handlers
from app.api.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import (
    host_router as host_bookings_router,
)
from app.api.v1.bookings import (
    router as bookings_router,
)
from app.api.v1.discovery import router as discovery_router
from app.api.v1.host import router as host_router
from app.api.v1.media import router as media_router
from app.api.v1.payments import router as payments_router
from app.api.v1.pets import router as pets_router
from app.core.config import Settings, get_settings
from app.db.session import dispose_engine
from app.operations.database import database_ready
from app.operations.http import OperationsMiddleware
from app.operations.logging import configure_logging, log_event
from app.security.http import AuthHTTPMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    try:
        if app.state.settings.app_env == "production":
            if not await run_in_threadpool(database_ready, app.state.settings):
                raise RuntimeError("Schema not ready. Apply migrations before startup.")
        log_event("startup_ready")
        yield
    finally:
        dispose_engine()
        log_event("shutdown_complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        debug=False,
        docs_url=None if settings.app_env == "production" else "/docs",
        redoc_url=None if settings.app_env == "production" else "/redoc",
    )
    app.state.settings = settings
    install_error_handlers(app)
    app.add_middleware(AuthHTTPMiddleware, settings=settings)
    if settings.app_env == "production":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    # Outer CORS middleware also decorates safe error responses from inner layers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=[
            "Content-Type",
            "X-PAWTEL-Request",
            "X-CSRF-Token",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(OperationsMiddleware, settings=settings)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(pets_router)
    app.include_router(host_router)
    app.include_router(media_router)
    app.include_router(discovery_router)
    app.include_router(bookings_router)
    app.include_router(host_bookings_router)
    app.include_router(payments_router)
    return app


app = create_app()
