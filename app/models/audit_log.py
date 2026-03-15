from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
import uuid


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String, index=True)
    # e.g. "auth.login", "auth.login_failed", "cloud_account.create",
    # "policy.update", "user.create", "api_key.delete", etc.

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    endpoint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    http_method: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(nullable=True)

    resource_type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # e.g. "cloud_account", "policy", "user"
    resource_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )

    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
