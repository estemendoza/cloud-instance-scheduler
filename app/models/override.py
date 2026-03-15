from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Override(Base):
    """Manual override for resource state with expiration."""
    __tablename__ = "overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)

    # Desired state: RUNNING or STOPPED
    desired_state: Mapped[str] = mapped_column(String, nullable=False)

    # Override expiration timestamp
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)

    # Optional reason for the override
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # User who created the override
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="overrides")
    resource: Mapped["Resource"] = relationship("Resource", back_populates="overrides")
    created_by: Mapped["User"] = relationship("User")
