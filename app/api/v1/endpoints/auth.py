from typing import List
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.api import deps
from app.core.rate_limit import limiter
from app.models.apikey import APIKey
from app.models.user import User
from app.schemas.apikey import (
    APIKeyCreate, APIKeyCreated, APIKeyBootstrap, APIKeyShow,
    DEFAULT_KEY_EXPIRY_DAYS,
)
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserInfo,
    TokenResponse,
    RefreshRequest,
    RefreshResponse,
    MfaRequiredResponse,
)
from app.core.security import (
    generate_api_key, get_api_key_hash, verify_password,
)
from app.core.jwt import (
    create_access_token, create_refresh_token,
    create_mfa_token, decode_token,
)
from app.services.audit import write_audit_log

router = APIRouter()


async def _verify_user_credentials(
    db: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Verify user credentials and return user if valid."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is disabled")

    return user


# ─── JWT Authentication Endpoints ──────────────────────────────


@router.post("/token")
@limiter.limit("10/minute")
async def login_for_tokens(
    request: Request,
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email and password.
    Returns JWT tokens, or MFA challenge if MFA is enabled.
    """
    try:
        user = await _verify_user_credentials(
            db, credentials.email, credentials.password
        )
    except HTTPException:
        await write_audit_log(
            db, "auth.login_failed", request=request,
            details={"email": credentials.email},
            description=f"Failed login attempt for {credentials.email}",
        )
        raise

    # If MFA is enabled, return a challenge instead of tokens
    if user.mfa_enabled:
        mfa_token = create_mfa_token(
            str(user.id), str(user.organization_id)
        )
        await write_audit_log(
            db, "auth.mfa_required", request=request,
            user_id=user.id, organization_id=user.organization_id,
            description=f"MFA challenge issued for {user.email}",
        )
        return MfaRequiredResponse(mfa_token=mfa_token)

    access_token = create_access_token(
        str(user.id), str(user.organization_id)
    )
    refresh_token = create_refresh_token(str(user.id))

    await write_audit_log(
        db, "auth.login", request=request,
        user_id=user.id, organization_id=user.organization_id,
        description=f"User {user.email} logged in",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            organization_id=user.organization_id,
        ),
    )


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("20/minute")
async def refresh_access_token(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for a new access token."""
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    new_access_token = create_access_token(
        str(user.id), str(user.organization_id)
    )
    return RefreshResponse(access_token=new_access_token)


@router.post("/bootstrap", response_model=TokenResponse)
@limiter.limit("5/hour")
async def bootstrap_auth(
    request: Request,
    bootstrap_in: APIKeyBootstrap,
    db: AsyncSession = Depends(get_db),
):
    """
    Bootstrap authentication without existing credentials.
    Returns JWT tokens for the first user in an org with no API keys.
    One-time bootstrap path: only succeeds when the target org has exactly
    one user with zero API keys.
    """
    user_result = await db.execute(
        select(User).where(User.id == bootstrap_in.user_id)
    )
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=404, detail="User not found"
        )

    # Org must have exactly one user
    org_user_count = await db.execute(
        select(func.count(User.id)).where(
            User.organization_id
            == target_user.organization_id
        )
    )
    if org_user_count.scalar() != 1:
        raise HTTPException(
            status_code=403,
            detail=(
                "Bootstrap requires the organization"
                " to have exactly one user."
            ),
        )

    # That user must have zero existing API keys
    key_count = await db.execute(
        select(func.count(APIKey.id)).where(
            APIKey.user_id == target_user.id
        )
    )
    if key_count.scalar() != 0:
        raise HTTPException(
            status_code=403,
            detail=(
                "Bootstrap requires the user to have"
                " no existing API keys."
            ),
        )

    access_token = create_access_token(
        str(target_user.id),
        str(target_user.organization_id),
    )
    refresh_token = create_refresh_token(str(target_user.id))

    await write_audit_log(
        db, "auth.bootstrap", request=request,
        user_id=target_user.id,
        organization_id=target_user.organization_id,
        description=f"Bootstrap auth for {target_user.email}",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo(
            id=target_user.id,
            email=target_user.email,
            full_name=target_user.full_name,
            role=target_user.role,
            organization_id=target_user.organization_id,
        ),
    )


# ─── Legacy API Key Login (backwards compat) ──────────────────


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    [DEPRECATED] Authenticate with email and password.
    Returns a new API key for the user.
    Use POST /auth/token for JWT-based authentication instead.
    """
    try:
        user = await _verify_user_credentials(
            db, credentials.email, credentials.password
        )
    except HTTPException:
        await write_audit_log(
            db, "auth.login_failed", request=request,
            details={"email": credentials.email},
            description=f"Failed login attempt for {credentials.email}",
        )
        raise

    # Generate a new API key for this login session
    raw_key = generate_api_key()
    key_hash = get_api_key_hash(raw_key)
    prefix = raw_key[:8]

    db_key = APIKey(
        key_hash=key_hash,
        prefix=prefix,
        name="login",
        user_id=user.id,
        expires_at=None,
    )
    db.add(db_key)
    await db.commit()

    return LoginResponse(
        key=raw_key,
        user=UserInfo(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            organization_id=user.organization_id,
        ),
    )


# ─── Legacy Bootstrap (backwards compat) ──────────────────────


@router.post("/keys/bootstrap", response_model=APIKeyCreated)
@limiter.limit("5/hour")
async def bootstrap_api_key(
    request: Request,
    bootstrap_in: APIKeyBootstrap,
    db: AsyncSession = Depends(get_db),
):
    """
    [DEPRECATED] Create an API key without authentication.
    Use POST /auth/bootstrap for JWT-based authentication instead.
    One-time bootstrap path: only succeeds when the target org has
    exactly one user with zero keys.
    """
    user_result = await db.execute(
        select(User).where(User.id == bootstrap_in.user_id)
    )
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=404, detail="User not found"
        )

    # Org must have exactly one user
    org_user_count = await db.execute(
        select(func.count(User.id)).where(
            User.organization_id
            == target_user.organization_id
        )
    )
    if org_user_count.scalar() != 1:
        raise HTTPException(
            status_code=403,
            detail=(
                "Bootstrap key creation requires the"
                " organization to have exactly one user."
            ),
        )

    # That user must have zero existing keys
    key_count = await db.execute(
        select(func.count(APIKey.id)).where(
            APIKey.user_id == target_user.id
        )
    )
    if key_count.scalar() != 0:
        raise HTTPException(
            status_code=403,
            detail=(
                "Bootstrap key creation requires the user"
                " to have no existing API keys."
            ),
        )

    raw_key = generate_api_key()
    key_hash = get_api_key_hash(raw_key)
    prefix = raw_key[:8]

    db_key = APIKey(
        key_hash=key_hash,
        prefix=prefix,
        name="bootstrap",
        user_id=target_user.id,
        expires_at=None,
    )
    db.add(db_key)
    await db.commit()
    await db.refresh(db_key)

    await write_audit_log(
        db, "api_key.bootstrap", request=request,
        user_id=target_user.id,
        organization_id=target_user.organization_id,
        resource_type="api_key", resource_id=str(db_key.id),
        description=f"Bootstrap API key created for {target_user.email}",
    )

    return APIKeyCreated(
        id=db_key.id,
        prefix=db_key.prefix,
        name=db_key.name,
        created_at=db_key.created_at,
        last_used_at=db_key.last_used_at,
        expires_at=db_key.expires_at,
        key=raw_key
    )


# ─── API Key Management ───────────────────────────────────────────────────────


@router.post("/keys", response_model=APIKeyCreated)
async def create_api_key(
    key_in: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Create a new API key for programmatic access.

    Keys expire after 90 days by default. Pass expires_at to override.
    """
    raw_key = generate_api_key()
    key_hash = get_api_key_hash(raw_key)
    prefix = raw_key[:8]

    expires_at = key_in.expires_at
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=DEFAULT_KEY_EXPIRY_DAYS
        )

    db_key = APIKey(
        key_hash=key_hash,
        prefix=prefix,
        name=key_in.name,
        user_id=current_user.id,
        expires_at=expires_at,
    )

    db.add(db_key)
    await db.commit()
    await db.refresh(db_key)

    await write_audit_log(
        db, "api_key.create",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="api_key", resource_id=str(db_key.id),
        description=f"API key '{key_in.name}' created",
    )

    return APIKeyCreated(
        id=db_key.id,
        prefix=db_key.prefix,
        name=db_key.name,
        created_at=db_key.created_at,
        last_used_at=db_key.last_used_at,
        expires_at=db_key.expires_at,
        key=raw_key
    )


@router.get("/keys", response_model=List[APIKeyShow])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List all API keys for the current user."""
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id)
    )
    return result.scalars().all()


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Delete an API key (user can only delete their own keys)."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.user_id == current_user.id
        )
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    key_name = key.name
    await db.delete(key)
    await db.commit()

    await write_audit_log(
        db, "api_key.delete",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="api_key", resource_id=str(key_id),
        description=f"API key '{key_name}' deleted",
    )
