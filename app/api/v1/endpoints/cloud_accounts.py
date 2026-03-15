import asyncio
import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.api.deps import get_db, get_current_active_user, require_role
from app.models.user import User
from app.models.cloud_account import CloudAccount as CloudAccountModel
from app.schemas import cloud_account as schemas
from app.services.encryption import encrypt_credentials, decrypt_credentials
from app.services.discovery import DiscoveryService
from app.providers import get_provider, build_credentials, get_non_secret_keys
from app.services.audit import write_audit_log

logger = logging.getLogger(__name__)


def get_credential_hints(
    account: CloudAccountModel,
) -> Optional[Dict[str, str]]:
    """Extract non-secret credential fields for edit form pre-population."""
    try:
        creds = decrypt_credentials(account.credentials_encrypted)
        allowed = get_non_secret_keys(account.provider_type)
        return {k: v for k, v in creds.items() if k in allowed}
    except Exception:
        logger.warning(
            "Failed to decrypt credentials for account %s",
            account.id,
        )
        return None


def enrich_account(account: CloudAccountModel) -> CloudAccountModel:
    """Add credential_hints to an account for API response."""
    account.credential_hints = get_credential_hints(account)
    return account


router = APIRouter()


@router.post("/", response_model=schemas.CloudAccount,
             status_code=status.HTTP_201_CREATED)
async def create_cloud_account(
    account: schemas.CloudAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Create a new cloud account."""
    # Validate credentials by attempting to create provider
    try:
        credentials = build_credentials(account.provider_type, account.credentials)
        provider = get_provider(account.provider_type, credentials)
        validation_result = await asyncio.to_thread(provider.validate_credentials)
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid credentials: {validation_result.error_message}"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Encrypt credentials
    encrypted_creds = encrypt_credentials(account.credentials)

    # Create cloud account
    db_account = CloudAccountModel(
        organization_id=current_user.organization_id,
        name=account.name,
        provider_type=account.provider_type,
        credentials_encrypted=encrypted_creds,
        is_active=account.is_active,
        selected_regions=account.selected_regions
    )

    db.add(db_account)
    await db.commit()
    await db.refresh(db_account)

    await write_audit_log(
        db, "cloud_account.create",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="cloud_account", resource_id=str(db_account.id),
        description=f"Cloud account '{account.name}' ({account.provider_type}) created",
    )

    return enrich_account(db_account)


@router.get("/", response_model=List[schemas.CloudAccount])
async def list_cloud_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all cloud accounts for the current organization."""
    result = await db.execute(
        select(CloudAccountModel).where(
            CloudAccountModel.organization_id == current_user.organization_id
        )
    )
    accounts = result.scalars().all()
    return [enrich_account(a) for a in accounts]


@router.get("/{account_id}", response_model=schemas.CloudAccount)
async def get_cloud_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific cloud account."""
    result = await db.execute(
        select(CloudAccountModel).where(
            CloudAccountModel.id == account_id,
            CloudAccountModel.organization_id == current_user.organization_id
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Cloud account not found")

    return enrich_account(account)


@router.put("/{account_id}", response_model=schemas.CloudAccount)
async def update_cloud_account(
    account_id: uuid.UUID,
    account_update: schemas.CloudAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Update a cloud account."""
    result = await db.execute(
        select(CloudAccountModel).where(
            CloudAccountModel.id == account_id,
            CloudAccountModel.organization_id == current_user.organization_id
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Cloud account not found")

    # Update fields
    if account_update.name is not None:
        account.name = account_update.name
    if account_update.is_active is not None:
        account.is_active = account_update.is_active
    # Update selected_regions (can be set to null to scan all regions)
    if 'selected_regions' in account_update.model_dump(exclude_unset=True):
        account.selected_regions = account_update.selected_regions
    # Only update credentials if provided and not empty
    # (allows editing name/is_active without re-entering credentials)
    if account_update.credentials:
        # Check if credentials dict has any non-empty values
        non_empty_creds = {
            k: v for k, v in account_update.credentials.items()
            if v is not None and str(v).strip()
        }

        if non_empty_creds:
            # If any credentials are provided, ALL required fields must be provided
            # (we can't merge with existing encrypted credentials)
            try:
                credentials = build_credentials(
                    account.provider_type, account_update.credentials)
                provider = get_provider(account.provider_type, credentials)
                validation_result = await asyncio.to_thread(
                    provider.validate_credentials
                )
                if not validation_result.is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "Invalid credentials: "
                            f"{validation_result.error_message}"
                        ),
                    )
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "To update credentials, all required"
                        " fields must be provided"
                        " (credentials cannot be"
                        " partially updated)"
                    ),
                )

            account.credentials_encrypted = encrypt_credentials(
                account_update.credentials)

    creds_changed = bool(
        account_update.credentials
        and any(
            v is not None and str(v).strip()
            for v in account_update.credentials.values()
        )
    )
    await db.commit()
    await db.refresh(account)

    await write_audit_log(
        db, "cloud_account.update",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="cloud_account", resource_id=str(account_id),
        details={"credentials_changed": creds_changed},
        description=f"Cloud account '{account.name}' updated",
    )

    return enrich_account(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloud_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Delete a cloud account."""
    result = await db.execute(
        select(CloudAccountModel).where(
            CloudAccountModel.id == account_id,
            CloudAccountModel.organization_id == current_user.organization_id
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Cloud account not found")

    account_name = account.name
    await db.delete(account)
    await db.commit()

    await write_audit_log(
        db, "cloud_account.delete",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="cloud_account", resource_id=str(account_id),
        description=f"Cloud account '{account_name}' deleted",
    )


@router.post("/{account_id}/sync", response_model=schemas.SyncResult)
async def sync_cloud_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Manually trigger resource sync for a cloud account."""
    result = await db.execute(
        select(CloudAccountModel).where(
            CloudAccountModel.id == account_id,
            CloudAccountModel.organization_id == current_user.organization_id
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Cloud account not found")

    discovery_service = DiscoveryService(db)
    sync_result = await discovery_service.sync_resources(account_id)

    return sync_result
