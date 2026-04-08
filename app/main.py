from __future__ import annotations

from contextlib import asynccontextmanager

import json as _json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


class _MillisecondJSONEncoder(_json.JSONEncoder):
    """Truncate datetime microseconds → milliseconds for iOS ISO8601 compatibility."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%dT%H:%M:%S.") + f"{obj.microsecond // 1000:03d}Z"
        return super().default(obj)

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.container import build_container
from app.core.exceptions import DomainError


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Build the in-memory container (services/repos still in-memory during migration)
        app.state.settings = settings
        app.state.container = build_container(settings)
        yield
        # Dispose the SQLAlchemy async engine on shutdown
        try:
            from app.database.session import engine
            await engine.dispose()
        except Exception:
            pass

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # -----------------------------------------------------------------------
    # Exception handlers
    # -----------------------------------------------------------------------

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.detail,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_generic_error(request: Request, exc: Exception) -> JSONResponse:
        if settings.env == "development":
            import traceback
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_server_error",
                        "message": str(exc),
                        "trace": traceback.format_exc(),
                    }
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred.",
                }
            },
        )

    # -----------------------------------------------------------------------
    # Root endpoint
    # -----------------------------------------------------------------------

    @app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "docs": "/docs",
            "api": settings.api_v1_prefix,
        }

    media_root = Path(settings.media_root)
    try:
        media_root.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        media_root = Path("/tmp/matcha-backend-media")
        media_root.mkdir(parents=True, exist_ok=True)
        settings.media_root = str(media_root)
    app.mount("/media", StaticFiles(directory=media_root), name="media")

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
