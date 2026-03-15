from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.db.session import get_db
from app.models.user import Organization
from app.core.version import APP_VERSION

router = APIRouter()


class SystemStatus(BaseModel):
    bootstrapped: bool
    version: str


@router.get("/status", response_model=SystemStatus)
async def get_system_status(db: AsyncSession = Depends(get_db)):
    """
    Check if the system has been bootstrapped.
    Returns bootstrapped=true if at least one organization exists.
    """
    result = await db.execute(select(func.count(Organization.id)))
    org_count = result.scalar()

    return SystemStatus(bootstrapped=org_count > 0, version=APP_VERSION)
