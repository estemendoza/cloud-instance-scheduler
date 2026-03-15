from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone
import uuid

from app.api.deps import get_db, get_current_active_user, require_role
from app.models.user import User
from app.models.override import Override as OverrideModel
from app.models.resource import Resource as ResourceModel
from app.schemas import override as schemas
from app.services.audit import write_audit_log

router = APIRouter()


@router.post("/", response_model=schemas.Override, status_code=status.HTTP_201_CREATED)
async def create_override(
    override: schemas.OverrideCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "operator"))
):
    """Create a manual override for a resource."""
    # Verify resource exists and belongs to user's organization
    result = await db.execute(
        select(ResourceModel).where(
            ResourceModel.id == override.resource_id,
            ResourceModel.organization_id == current_user.organization_id
        )
    )
    resource = result.scalar_one_or_none()

    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Resource not found")

    # Create override
    db_override = OverrideModel(
        organization_id=current_user.organization_id,
        resource_id=override.resource_id,
        desired_state=override.desired_state,
        expires_at=override.expires_at,
        reason=override.reason,
        created_by_user_id=current_user.id
    )

    db.add(db_override)
    await db.commit()
    await db.refresh(db_override)

    await write_audit_log(
        db, "override.create",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="override", resource_id=str(db_override.id),
        details={
            "target_resource_id": str(override.resource_id),
            "desired_state": override.desired_state,
        },
        description=f"Override created: {override.desired_state} for resource {override.resource_id}",
    )

    return db_override


@router.get("/", response_model=List[schemas.Override])
async def list_active_overrides(
    resource_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all active (non-expired) overrides for the current organization."""
    query = select(OverrideModel).where(
        and_(
            OverrideModel.organization_id
            == current_user.organization_id,
            OverrideModel.expires_at
            > datetime.now(timezone.utc)
        )
    )
    if resource_id:
        query = query.where(
            OverrideModel.resource_id == resource_id
        )
    query = query.order_by(OverrideModel.created_at.desc())
    result = await db.execute(query)
    overrides = result.scalars().all()
    return overrides


@router.delete("/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_override(
    override_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "operator"))
):
    """Delete an override (cancel it early)."""
    result = await db.execute(
        select(OverrideModel).where(
            OverrideModel.id == override_id,
            OverrideModel.organization_id == current_user.organization_id
        )
    )
    override = result.scalar_one_or_none()

    if not override:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Override not found")

    await db.delete(override)
    await db.commit()

    await write_audit_log(
        db, "override.delete",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="override", resource_id=str(override_id),
        description=f"Override {override_id} cancelled",
    )
