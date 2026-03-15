from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.api import deps
from app.core.rate_limit import limiter
from app.models.user import User, Organization
from app.schemas.user import (
    UserCreate, UserUpdate, User as UserSchema,
    ProfileUpdate, PasswordChange,
)
import uuid
from app.core.security import get_password_hash, verify_password
from app.services.audit import write_audit_log

router = APIRouter()


@router.post("/", response_model=UserSchema)
@limiter.limit("10/hour")
async def create_user(
    request: Request,
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(deps.get_optional_user),
):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    # Check if organization exists
    org_result = await db.execute(
        select(Organization).where(
            Organization.id == user_in.organization_id
        )
    )
    if not org_result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Organization not found.",
        )

    # RBAC bootstrap: first user in org is unauthenticated but must be admin.
    # Subsequent users require an authenticated admin of the same org.
    user_count_result = await db.execute(
        select(func.count(User.id)).where(
            User.organization_id == user_in.organization_id
        )
    )
    user_count = user_count_result.scalar()
    if user_count == 0:
        if user_in.role != "admin":
            raise HTTPException(
                status_code=400,
                detail="The first user in an organization must have role 'admin'.",
            )
    else:
        if (
            not current_user
            or current_user.role != "admin"
            or current_user.organization_id != user_in.organization_id
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Only an admin of the target organization"
                    " can create additional users."
                ),
            )

    db_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=user_in.is_active,
        organization_id=user_in.organization_id
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user, attribute_names=['organization'])

    is_bootstrap = user_count == 0
    await write_audit_log(
        db, "user.create", request=request,
        user_id=current_user.id if current_user else db_user.id,
        organization_id=db_user.organization_id,
        resource_type="user", resource_id=str(db_user.id),
        details={"role": user_in.role, "bootstrap": is_bootstrap},
        description=f"User '{db_user.email}' created with role '{user_in.role}'",
    )

    return db_user


@router.get("/me", response_model=UserSchema)
async def read_user_me(
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await db.refresh(current_user, attribute_names=['organization'])
    return current_user


@router.get("/", response_model=List[UserSchema])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.require_role("admin")),
):
    """List all users in the current organization (admin only)."""
    result = await db.execute(
        select(User).where(User.organization_id == current_user.organization_id)
    )
    users = result.scalars().all()
    for user in users:
        await db.refresh(user, attribute_names=['organization'])
    return users


# ─── Self-service Profile Endpoints ──────────────────────────
# These must be declared before /{user_id} so FastAPI doesn't
# treat "me" as a UUID path parameter.


@router.put("/me", response_model=UserSchema)
async def update_my_profile(
    profile: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Update own profile (full_name only)."""
    if profile.full_name is not None:
        current_user.full_name = profile.full_name

    await db.commit()
    await db.refresh(current_user, attribute_names=['organization'])

    await write_audit_log(
        db, "user.profile_update",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="user", resource_id=str(current_user.id),
        description=f"User '{current_user.email}' updated profile",
    )

    return current_user


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    body: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Change own password (requires current password)."""
    if not verify_password(body.current_password,
                           current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = get_password_hash(body.new_password)
    await db.commit()

    await write_audit_log(
        db, "user.password_change",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="user", resource_id=str(current_user.id),
        description=f"User '{current_user.email}' changed password",
    )


@router.put("/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: uuid.UUID,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.require_role("admin")),
):
    """Update a user (admin only, same org)."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_user.organization_id
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from demoting themselves if they're the only admin
    if user_update.role and user_update.role != "admin" and user.id == current_user.id:
        admin_count = await db.execute(
            select(func.count(User.id)).where(
                User.organization_id == current_user.organization_id,
                User.role == "admin"
            )
        )
        if admin_count.scalar() <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the only admin"
            )

    # Update fields
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.role is not None:
        user.role = user_update.role
    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    changes = {
        k: v for k, v in user_update.model_dump(exclude_unset=True).items()
    }
    await db.commit()
    await db.refresh(user, attribute_names=['organization'])

    await write_audit_log(
        db, "user.update",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="user", resource_id=str(user_id),
        details={"changes": changes},
        description=f"User '{user.email}' updated",
    )

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.require_role("admin")),
):
    """Delete a user (admin only, same org, cannot delete self)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_user.organization_id
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_email = user.email
    await db.delete(user)
    await db.commit()

    await write_audit_log(
        db, "user.delete",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="user", resource_id=str(user_id),
        description=f"User '{user_email}' deleted",
    )
