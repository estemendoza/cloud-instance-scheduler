from datetime import datetime, timezone
from typing import Optional

from fastapi import Security, HTTPException, status, Depends
from fastapi.security import (
    APIKeyHeader,
    HTTPBearer,
    HTTPAuthorizationCredentials,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.apikey import APIKey
from app.models.user import User
from app.core.security import verify_api_key
from app.core.jwt import decode_token

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def _get_user_from_jwt(
    credentials: HTTPAuthorizationCredentials,
    db: AsyncSession,
) -> Optional[User]:
    """Validate JWT token and return user if valid."""
    if not credentials:
        return None

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _get_user_from_api_key(
    api_key: str,
    db: AsyncSession,
) -> Optional[User]:
    """Validate API key and return user if valid."""
    if not api_key or len(api_key) < 8:
        return None

    prefix = api_key[:8]
    result = await db.execute(select(APIKey).where(APIKey.prefix == prefix))
    potential_keys = result.scalars().all()

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    for db_key in potential_keys:
        if verify_api_key(api_key, db_key.key_hash):
            # Check expiration
            if (
                db_key.expires_at
                and db_key.expires_at.replace(tzinfo=None)
                < now_naive
            ):
                continue  # Expired

            # Return the user associated with the key
            user_result = await db.execute(
                select(User).where(User.id == db_key.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                return user

    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authenticate user via JWT Bearer token or API key.
    JWT is tried first, then falls back to API key.
    """
    # Try JWT first (Bearer token)
    user = await _get_user_from_jwt(credentials, db)
    if user:
        return user

    # Fall back to API key
    user = await _get_user_from_api_key(api_key, db)
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of raising.

    Returns None when no valid auth is provided.
    """
    try:
        # Try JWT first
        user = await _get_user_from_jwt(credentials, db)
        if user and user.is_active:
            return user

        # Fall back to API key
        user = await _get_user_from_api_key(api_key, db)
        if user and user.is_active:
            return user
    except Exception:
        pass
    return None


def require_role(*allowed_roles: str):
    """Dependency factory: checks current user's role against the allowed set."""
    async def _check_role(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user
    return _check_role
