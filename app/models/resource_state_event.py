from datetime import datetime, timezone
import uuid

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResourceStateEvent(Base):
    """Audit log of resource state transitions."""
    __tablename__ = "resource_state_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)

    previous_state: Mapped[str] = mapped_column(String, nullable=False)
    new_state: Mapped[str] = mapped_column(String, nullable=False)
    # "discovery" or "reconciliation"
    source: Mapped[str] = mapped_column(String, nullable=False)

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    resource: Mapped["Resource"] = relationship(
        "Resource", back_populates="state_events")
