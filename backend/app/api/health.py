from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from app.operations.database import database_ready

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", tags=["health"])
def ready(request: Request):
    available = database_ready(request.app.state.settings)
    return JSONResponse(
        {"status": "ready" if available else "not_ready"},
        status_code=200 if available else 503,
    )
