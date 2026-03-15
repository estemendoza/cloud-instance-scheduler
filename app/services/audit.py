import logging
from typing import Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def write_audit_log(
    db: AsyncSession,
    event_type: str,
    *,
    request: Optional[Request] = None,
    user_id: Optional[UUID] = None,
    organization_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    status_code: Optional[int] = None,
    details: Optional[dict] = None,
    description: Optional[str] = None,
) -> None:
    """Write an audit log entry.

    This is fire-and-forget — failures are logged but never bubble up
    to callers so that audit logging can never break normal operations.
    """
    try:
        ip_address = None
        user_agent = None
        endpoint = None
        http_method = None

        if request is not None:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            endpoint = str(request.url.path)
            http_method = request.method

        entry = AuditLog(
            event_type=event_type,
            user_id=user_id,
            organization_id=organization_id,
            ip_address=ip_address,
            user_agent=user_agent,
            endpoint=endpoint,
            http_method=http_method,
            status_code=status_code,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            description=description,
        )
        db.add(entry)
        await db.commit()
    except Exception:
        logger.exception("Failed to write audit log entry: %s", event_type)
