"""Serve only the compiled SPA, after all API routes, on the same HTTPS origin."""

from pathlib import Path

from fastapi import Request
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse

from app.core.config import ROOT


def install_frontend(app, directory: Path | None = None):
    directory = (directory or ROOT / "frontend" / "dist").resolve()
    if not (directory / "index.html").is_file():
        raise RuntimeError("Frontend build missing. Run the deployment build first.")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str, request: Request):
        if path.split("/", 1)[0] in {
            "api",
            "health",
            "ready",
            "docs",
            "redoc",
            "openapi.json",
        }:
            raise HTTPException(404)
        candidate = (directory / path).resolve()
        if not candidate.is_relative_to(directory) or any(
            part.startswith(".") for part in Path(path).parts
        ):
            raise HTTPException(404)
        if candidate.is_file():
            cache = (
                "public, max-age=31536000, immutable"
                if path.startswith("assets/")
                else "no-cache"
            )
            return FileResponse(candidate, headers={"Cache-Control": cache})
        if path.startswith(("assets/", "media/")) or Path(path).suffix:
            raise HTTPException(404)
        return FileResponse(
            directory / "index.html", headers={"Cache-Control": "no-store"}
        )
