from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, require_role
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogEntry

router = APIRouter()


@router.get("/", response_model=List[AuditLogEntry])
async def list_audit_logs(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """List audit log entries for the current organization (admin only)."""
    query = select(AuditLog).where(
        AuditLog.organization_id == current_user.organization_id
    )

    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)

    query = query.order_by(AuditLog.timestamp.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()
