from datetime import datetime, timezone
from typing import Optional, Dict
import uuid

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Resource(Base):
    """Cached cloud resource (compute instance)."""
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    cloud_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False)

    # Provider-specific resource identifier
    provider_resource_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True)

    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    region: Mapped[str] = mapped_column(String, nullable=False)
    # For future: 'instance', 'database', etc.
    resource_type: Mapped[str] = mapped_column(
        String, default="instance", nullable=False)

    # Normalized state: RUNNING, STOPPED, UNKNOWN
    state: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Resource tags/labels from provider
    tags: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)

    # Instance metadata
    instance_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False)
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
        "Organization", back_populates="resources")
    cloud_account: Mapped["CloudAccount"] = relationship(
        "CloudAccount", back_populates="resources")
    overrides: Mapped[list["Override"]] = relationship(
        "Override", back_populates="resource", cascade="all, delete-orphan")
    executions: Mapped[list["Execution"]] = relationship(
        "Execution", back_populates="resource", cascade="all, delete-orphan")
    state_events: Mapped[list["ResourceStateEvent"]] = relationship(
        "ResourceStateEvent", back_populates="resource", cascade="all, delete-orphan")

    __table_args__ = (
        # Ensure uniqueness of provider resource IDs within an account
        Index('ix_resources_account_provider_id', 'cloud_account_id',
              'provider_resource_id', unique=True),
    )
