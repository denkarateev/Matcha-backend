from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.container import AppContainer
from app.core.dependencies import get_container

router = APIRouter(tags=["health"])


@router.get("/health")
def health(container: AppContainer = Depends(get_container)) -> dict[str, object]:
    return {
        "status": "ok",
        "environment": container.settings.env,
        "timezone": container.settings.business_timezone,
        "services": {
            "api": "up",
            "storage": "in-memory",
            "queue": "stubbed",
            "cache": "stubbed",
        },
    }
