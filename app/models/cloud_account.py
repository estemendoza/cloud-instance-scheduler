from datetime import datetime, timezone
from typing import Optional, List
import uuid

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CloudAccount(Base):
    """Cloud provider account credentials."""
    __tablename__ = "cloud_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    name: Mapped[str] = mapped_column(String, nullable=False)
    provider_type: Mapped[str] = mapped_column(
        String, nullable=False)  # 'aws', 'azure', 'gcp'

    # Encrypted JSON containing provider-specific credentials
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Selected regions to scan (null = all regions)
    selected_regions: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)

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
        "Organization", back_populates="cloud_accounts")
    resources: Mapped[list["Resource"]] = relationship(
        "Resource", back_populates="cloud_account", cascade="all, delete-orphan")
