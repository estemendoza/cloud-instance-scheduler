import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.api import deps
from app.core.rate_limit import limiter
from app.models.user import Organization as OrganizationModel, User
from app.schemas.user import (
    OrganizationCreate,
    OrganizationUpdate,
    Organization as OrganizationSchema,
)

router = APIRouter()


@router.post(
    "/",
    response_model=OrganizationSchema,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/hour")
async def create_organization(
    request: Request,
    org_in: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization. Only allowed during bootstrap (no existing orgs)."""
    from sqlalchemy import func

    # Check if any organizations already exist
    org_count_result = await db.execute(select(func.count(OrganizationModel.id)))
    org_count = org_count_result.scalar()
    if org_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization creation is disabled. Contact system administrator.",
        )

    result = await db.execute(
        select(OrganizationModel).where(OrganizationModel.slug == org_in.slug)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists.",
        )

    db_org = OrganizationModel(name=org_in.name, slug=org_in.slug)
    db.add(db_org)
    await db.commit()
    await db.refresh(db_org)
    return db_org


@router.get("/", response_model=List[OrganizationSchema])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
):
    """List all organizations."""
    result = await db.execute(select(OrganizationModel))
    return result.scalars().all()


@router.get("/{org_id}", response_model=OrganizationSchema)
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get an organization by ID."""
    result = await db.execute(
        select(OrganizationModel).where(OrganizationModel.id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Organization not found")
    return org


@router.put("/{org_id}", response_model=OrganizationSchema)
async def update_organization(
    org_id: uuid.UUID,
    org_update: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.require_role("admin")),
):
    """Update organization (admin only, own org)."""
    if org_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update other organizations")

    result = await db.execute(
        select(OrganizationModel).where(OrganizationModel.id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Organization not found")

    # Check slug uniqueness if changing
    if org_update.slug and org_update.slug != org.slug:
        slug_check = await db.execute(
            select(OrganizationModel).where(OrganizationModel.slug == org_update.slug)
        )
        if slug_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Slug already in use")

    if org_update.name is not None:
        org.name = org_update.name
    if org_update.slug is not None:
        org.slug = org_update.slug

    await db.commit()
    await db.refresh(org)
    return org
