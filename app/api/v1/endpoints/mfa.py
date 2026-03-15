import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.api import deps
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import (
    MfaSetupResponse, MfaVerifyRequest, MfaDisableRequest,
    MfaStatusResponse, MfaValidateRequest,
    TokenResponse, UserInfo,
)
from app.core.security import verify_password
from app.core.jwt import (
    create_access_token, create_refresh_token, decode_token,
)
from app.services.encryption import encrypt_credentials, decrypt_credentials
from app.services.audit import write_audit_log

router = APIRouter()


def _encrypt_mfa_secret(secret: str) -> str:
    """Encrypt an MFA secret for storage."""
    return encrypt_credentials({"mfa_secret": secret})


def _decrypt_mfa_secret(encrypted: str) -> str:
    """Decrypt an MFA secret from storage."""
    data = decrypt_credentials(encrypted)
    return data["mfa_secret"]


@router.get("/mfa/status", response_model=MfaStatusResponse)
async def mfa_status(
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get MFA status for the current user."""
    return MfaStatusResponse(enabled=current_user.mfa_enabled)


@router.post("/mfa/setup", response_model=MfaSetupResponse)
async def mfa_setup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Generate TOTP secret and provisioning URI for MFA setup."""
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=400,
            detail="MFA is already enabled",
        )

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="CIS",
    )

    # Store encrypted secret but don't enable yet
    current_user.mfa_secret = _encrypt_mfa_secret(secret)
    await db.commit()

    return MfaSetupResponse(secret=secret, provisioning_uri=uri)


@router.post("/mfa/verify", response_model=MfaStatusResponse)
@limiter.limit("10/minute")
async def mfa_verify(
    request: Request,
    body: MfaVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Verify TOTP code to complete MFA setup."""
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=400,
            detail="MFA is already enabled",
        )

    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=400,
            detail="MFA setup has not been initiated",
        )

    secret = _decrypt_mfa_secret(current_user.mfa_secret)
    totp = pyotp.TOTP(secret)

    if not totp.verify(body.code):
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code",
        )

    current_user.mfa_enabled = True
    await db.commit()

    await write_audit_log(
        db, "user.mfa_enabled",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="user", resource_id=str(current_user.id),
        description=f"MFA enabled for {current_user.email}",
    )

    return MfaStatusResponse(enabled=True)


@router.post("/mfa/disable", response_model=MfaStatusResponse)
@limiter.limit("5/minute")
async def mfa_disable(
    request: Request,
    body: MfaDisableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Disable MFA (requires password and current TOTP code)."""
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=400,
            detail="MFA is not enabled",
        )

    if not verify_password(body.password,
                           current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Invalid password",
        )

    secret = _decrypt_mfa_secret(current_user.mfa_secret)
    totp = pyotp.TOTP(secret)
    if not totp.verify(body.code):
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code",
        )

    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    await db.commit()

    await write_audit_log(
        db, "user.mfa_disabled",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_type="user", resource_id=str(current_user.id),
        description=f"MFA disabled for {current_user.email}",
    )

    return MfaStatusResponse(enabled=False)


@router.post("/mfa/validate", response_model=TokenResponse)
@limiter.limit("10/minute")
async def mfa_validate(
    request: Request,
    body: MfaValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate MFA code during login to get full tokens."""
    payload = decode_token(body.mfa_token)
    if not payload or payload.get("type") != "mfa_pending":
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired MFA token",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive",
        )

    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(
            status_code=400,
            detail="MFA is not enabled for this user",
        )

    secret = _decrypt_mfa_secret(user.mfa_secret)
    totp = pyotp.TOTP(secret)
    if not totp.verify(body.code):
        await write_audit_log(
            db, "auth.mfa_failed", request=request,
            user_id=user.id,
            organization_id=user.organization_id,
            description=f"Failed MFA attempt for {user.email}",
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid verification code",
        )

    access_token = create_access_token(
        str(user.id), str(user.organization_id)
    )
    refresh_token = create_refresh_token(str(user.id))

    await write_audit_log(
        db, "auth.mfa_login", request=request,
        user_id=user.id,
        organization_id=user.organization_id,
        description=f"User {user.email} completed MFA login",
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
