from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import install_error_handlers
from app.api.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.host import router as host_router
from app.api.v1.pets import router as pets_router
from app.core.config import Settings, get_settings
from app.db.session import dispose_engine
from app.security.http import AuthHTTPMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    install_error_handlers(app)
    app.add_middleware(AuthHTTPMiddleware, settings=settings)
    # Outer CORS middleware also decorates safe error responses from inner layers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-PAWTEL-Request", "X-CSRF-Token"],
    )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(pets_router)
    app.include_router(host_router)
    app.include_router(discovery_router)
    return app


app = create_app()
