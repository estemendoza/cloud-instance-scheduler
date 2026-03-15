from datetime import datetime, timezone
from typing import Optional, Dict
import uuid

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Policy(Base):
    """Scheduling policy defining when resources should be running."""
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # IANA timezone name (e.g., "America/New_York")
    timezone: Mapped[str] = mapped_column(String, nullable=False)

    # "weekly" or "cron"
    schedule_type: Mapped[str] = mapped_column(
        String, nullable=False, default="weekly", server_default="weekly")

    # Schedule in JSON format. Shape depends on schedule_type:
    # weekly: {"monday": [{"start": "09:00", "end": "18:00"}], ...}
    # cron:   {"start": "0 9 * * 1-5", "stop": "0 18 * * 1-5"}
    schedule: Mapped[Dict] = mapped_column(JSONB, nullable=False)

    # Resource selector in JSON format:
    # {"tags": {"env": "production", "team": "backend"}}
    # OR
    # {"resource_ids": ["uuid1", "uuid2"]}
    resource_selector: Mapped[Dict] = mapped_column(JSONB, nullable=False)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="policies")
