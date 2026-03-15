import logging
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.api.deps import get_db, get_current_active_user, require_role
from app.models.user import User
from app.models.policy import Policy as PolicyModel
from app.models.resource import Resource as ResourceModel
from app.schemas import policy as schemas
from app.services.audit import write_audit_log

logger = logging.getLogger(__name__)
router = APIRouter()


async def trigger_policy_reconciliation(policy_id: str):
    """Background task to trigger reconciliation for a policy."""
    from app.db.session import AsyncSessionLocal
    from app.services.reconciliation import ReconciliationService

    logger.warning(
        "[Policy Update] Triggering immediate reconciliation"
        f" for policy {policy_id}...")
    async with AsyncSessionLocal() as db:
        service = ReconciliationService(db)
        try:
            stats = await service.trigger_for_policy(policy_id)
            logger.warning(
                "[Policy Update] Reconciliation complete: "
                f"{stats['processed']} resources, "
                f"{stats['actions_taken']} actions, "
                f"{stats['errors']} errors")
        except Exception as e:
            logger.error(f"[Policy Update] Error in reconciliation: {e}", exc_info=True)


@router.post("/", response_model=schemas.Policy, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy: schemas.PolicyCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Create a new scheduling policy."""
    db_policy = PolicyModel(
        organization_id=current_user.organization_id,
        name=policy.name,
        description=policy.description,
        timezone=policy.timezone,
        schedule_type=policy.schedule_type,
        schedule=policy.schedule,
        resource_selector=policy.resource_selector,
        is_enabled=policy.is_enabled
    )

    db.add(db_policy)
    await db.commit()
    await db.refresh(db_policy)

    await write_audit_log(
        db, "policy.create",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="policy", resource_id=str(db_policy.id),
        description=f"Policy '{policy.name}' created",
    )

    # Trigger immediate reconciliation in background
    background_tasks.add_task(trigger_policy_reconciliation, str(db_policy.id))

    return db_policy


@router.get("/", response_model=List[schemas.Policy])
async def list_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all policies for the current organization."""
    result = await db.execute(
        select(PolicyModel).where(
            PolicyModel.organization_id == current_user.organization_id
        ).order_by(PolicyModel.name)
    )
    policies = result.scalars().all()
    return policies


@router.get("/{policy_id}", response_model=schemas.Policy)
async def get_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific policy."""
    result = await db.execute(
        select(PolicyModel).where(
            PolicyModel.id == policy_id,
            PolicyModel.organization_id == current_user.organization_id
        )
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Policy not found")

    return policy


@router.put("/{policy_id}", response_model=schemas.Policy)
async def update_policy(
    policy_id: uuid.UUID,
    policy_update: schemas.PolicyUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Update a policy."""
    result = await db.execute(
        select(PolicyModel).where(
            PolicyModel.id == policy_id,
            PolicyModel.organization_id == current_user.organization_id
        )
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Policy not found")

    # Update fields
    if policy_update.name is not None:
        policy.name = policy_update.name
    if policy_update.description is not None:
        policy.description = policy_update.description
    if policy_update.timezone is not None:
        policy.timezone = policy_update.timezone
    if policy_update.schedule_type is not None:
        policy.schedule_type = policy_update.schedule_type
    if policy_update.schedule is not None:
        policy.schedule = policy_update.schedule
    if policy_update.resource_selector is not None:
        policy.resource_selector = policy_update.resource_selector
    if policy_update.is_enabled is not None:
        policy.is_enabled = policy_update.is_enabled

    await db.commit()
    await db.refresh(policy)

    await write_audit_log(
        db, "policy.update",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="policy", resource_id=str(policy_id),
        description=f"Policy '{policy.name}' updated",
    )

    # Trigger immediate reconciliation in background
    background_tasks.add_task(trigger_policy_reconciliation, str(policy_id))

    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Delete a policy."""
    result = await db.execute(
        select(PolicyModel).where(
            PolicyModel.id == policy_id,
            PolicyModel.organization_id == current_user.organization_id
        )
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Policy not found")

    policy_name = policy.name
    await db.delete(policy)
    await db.commit()

    await write_audit_log(
        db, "policy.delete",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="policy", resource_id=str(policy_id),
        description=f"Policy '{policy_name}' deleted",
    )


@router.get("/{policy_id}/preview", response_model=schemas.PolicyPreview)
async def preview_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Preview which resources would be affected by this policy."""
    result = await db.execute(
        select(PolicyModel).where(
            PolicyModel.id == policy_id,
            PolicyModel.organization_id == current_user.organization_id
        )
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Policy not found")

    # Get all resources for the organization
    resources_result = await db.execute(
        select(ResourceModel).where(
            ResourceModel.organization_id == current_user.organization_id
        )
    )
    all_resources = resources_result.scalars().all()

    # Filter resources that match the policy selector
    affected_resources = []
    selector = policy.resource_selector

    for resource in all_resources:
        # Check by resource IDs
        if "resource_ids" in selector:
            if str(resource.id) in selector["resource_ids"]:
                affected_resources.append(resource.id)

        # Check by tags
        elif "tags" in selector:
            required_tags = selector["tags"]
            resource_tags = resource.tags or {}

            # All required tags must match
            match = True
            for key, value in required_tags.items():
                if resource_tags.get(key) != value:
                    match = False
                    break

            if match:
                affected_resources.append(resource.id)

    return schemas.PolicyPreview(
        policy_id=policy.id,
        affected_resource_count=len(affected_resources),
        sample_resources=affected_resources[:10]  # First 10
    )
