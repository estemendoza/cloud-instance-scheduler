from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.schemas import savings as schemas
from app.services.cost_calculator import CostCalculator

router = APIRouter()


@router.get("/organization", response_model=schemas.OrganizationSavings)
async def get_organization_savings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get total estimated savings for the organization."""
    cost_calculator = CostCalculator(db)
    savings = await cost_calculator.calculate_organization_savings(
        current_user.organization_id
    )
    return schemas.OrganizationSavings(**savings)


@router.get("/resources/{resource_id}", response_model=schemas.ResourceSavings)
async def get_resource_savings(
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get estimated savings for a specific resource."""
    cost_calculator = CostCalculator(db)
    savings = await cost_calculator.calculate_resource_savings(resource_id)

    # Return even if savings are 0 (with note explaining why)
    return schemas.ResourceSavings(**savings)
