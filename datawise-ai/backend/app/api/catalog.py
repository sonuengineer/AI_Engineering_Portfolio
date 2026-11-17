from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.services.catalog import build_catalog

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/catalog")
def catalog(user: CurrentUser) -> dict[str, Any]:
    return build_catalog(get_settings().analytics_reader_database_url)
