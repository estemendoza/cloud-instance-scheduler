import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import uuid

from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.resource import Resource as ResourceModel
from app.models.cloud_account import CloudAccount as CloudAccountModel
from app.schemas import resource as schemas

router = APIRouter()


@router.get("/", response_model=schemas.PaginatedResources)
async def list_resources(
    provider_type: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    cloud_account_id: Optional[uuid.UUID] = Query(None),
    region: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List resources with optional filters and pagination."""
    query = select(ResourceModel).where(
        ResourceModel.organization_id == current_user.organization_id
    )
    count_query = select(func.count(ResourceModel.id)).where(
        ResourceModel.organization_id == current_user.organization_id
    )

    # Apply filters to both queries
    if cloud_account_id:
        query = query.where(
            ResourceModel.cloud_account_id == cloud_account_id
        )
        count_query = count_query.where(
            ResourceModel.cloud_account_id == cloud_account_id
        )
    if state:
        query = query.where(ResourceModel.state == state)
        count_query = count_query.where(
            ResourceModel.state == state
        )
    if region:
        query = query.where(ResourceModel.region == region)
        count_query = count_query.where(
            ResourceModel.region == region
        )
    if provider_type:
        join_condition = (
            ResourceModel.cloud_account_id == CloudAccountModel.id
        )
        provider_filter = (
            CloudAccountModel.provider_type == provider_type
        )
        query = query.join(
            CloudAccountModel, join_condition
        ).where(provider_filter)
        count_query = count_query.join(
            CloudAccountModel, join_condition
        ).where(provider_filter)

    # Get total count
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.options(
        selectinload(ResourceModel.cloud_account)
    ).order_by(ResourceModel.name).offset(offset).limit(
        page_size
    )

    result = await db.execute(query)
    resources = result.scalars().all()

    items = []
    for r in resources:
        resource_data = schemas.Resource.model_validate(r)
        if r.cloud_account:
            resource_data.provider_type = r.cloud_account.provider_type
        items.append(resource_data)

    return schemas.PaginatedResources(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{resource_id}", response_model=schemas.Resource)
async def get_resource(
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific resource."""
    result = await db.execute(
        select(ResourceModel).options(
            selectinload(ResourceModel.cloud_account)
        ).where(
            ResourceModel.id == resource_id,
            ResourceModel.organization_id
            == current_user.organization_id
        )
    )
    resource = result.scalar_one_or_none()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )

    resource_data = schemas.Resource.model_validate(resource)
    if resource.cloud_account:
        resource_data.provider_type = (
            resource.cloud_account.provider_type
        )
    return resource_data
