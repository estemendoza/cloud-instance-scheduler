from typing import List
from fastapi import APIRouter

from app.providers import get_all_provider_metadata

router = APIRouter()


@router.get("/metadata")
async def get_provider_metadata() -> List[dict]:
    """Return metadata for all registered cloud providers.

    Used by the frontend to dynamically render provider selection,
    credential forms, and region pickers. No auth required — this
    is public configuration data.
    """
    return get_all_provider_metadata()
