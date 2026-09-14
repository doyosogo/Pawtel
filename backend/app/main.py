from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router
from app.core.config import get_settings
from app.db.session import dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        dispose_engine()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
