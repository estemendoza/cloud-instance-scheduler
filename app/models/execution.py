from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Execution(Base):
    """Audit log of actions taken by the scheduler."""
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)

    # Action taken: START or STOP
    action: Mapped[str] = mapped_column(String, nullable=False)

    # State information
    desired_state: Mapped[str] = mapped_column(String, nullable=False)
    actual_state_before: Mapped[str] = mapped_column(String, nullable=False)

    # Execution result
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="completed")  # pending, completed, failed
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="executions")
    resource: Mapped["Resource"] = relationship("Resource", back_populates="executions")
