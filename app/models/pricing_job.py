import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PricingJobRun(Base):
    """Record of a pricing fetch job execution."""
    __tablename__ = "pricing_job_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        default=uuid.uuid4,
    )
    provider_type: Mapped[str] = mapped_column(
        String, nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending",
    )
    trigger: Mapped[str] = mapped_column(
        String, nullable=False, default="scheduled",
    )
    regions_requested: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
    )
    records_updated: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
    )
