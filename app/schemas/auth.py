from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    key: str
    user: "UserInfo"


class UserInfo(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str]
    role: str
    organization_id: uuid.UUID

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response for JWT-based authentication."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserInfo"


class RefreshRequest(BaseModel):
    """Request to refresh an access token."""
    refresh_token: str


class RefreshResponse(BaseModel):
    """Response containing a new access token."""
    access_token: str
    token_type: str = "bearer"


class MfaRequiredResponse(BaseModel):
    """Returned when MFA verification is needed to complete login."""
    mfa_required: bool = True
    mfa_token: str


class MfaValidateRequest(BaseModel):
    """Submit MFA code to complete login."""
    mfa_token: str
    code: str


class MfaSetupResponse(BaseModel):
    """Response when initiating MFA setup."""
    secret: str
    provisioning_uri: str


class MfaVerifyRequest(BaseModel):
    """Verify a TOTP code during MFA setup."""
    code: str


class MfaDisableRequest(BaseModel):
    """Disable MFA — requires password and current TOTP code."""
    password: str
    code: str


class MfaStatusResponse(BaseModel):
    """Current MFA status for the user."""
    enabled: bool


# Rebuild models to resolve forward references
LoginResponse.model_rebuild()
TokenResponse.model_rebuild()
