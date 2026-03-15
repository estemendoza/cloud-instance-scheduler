from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import String, DateTime, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InstancePricing(Base):
    """Pricing information for cloud instance types."""
    __tablename__ = "instance_pricing"

    # Composite primary key: provider + region + instance_type
    provider_type: Mapped[str] = mapped_column(String, primary_key=True)
    region: Mapped[str] = mapped_column(String, primary_key=True)
    instance_type: Mapped[str] = mapped_column(String, primary_key=True)

    # Hourly rate in USD
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False)

    __table_args__ = (
        Index('ix_pricing_provider_region', 'provider_type', 'region'),
    )
