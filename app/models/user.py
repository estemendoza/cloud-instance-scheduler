from typing import List, Optional
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
import uuid


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, index=True)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="organization")
    cloud_accounts: Mapped[list["CloudAccount"]] = relationship(
        "CloudAccount", back_populates="organization", cascade="all, delete-orphan")
    resources: Mapped[list["Resource"]] = relationship(
        "Resource", back_populates="organization", cascade="all, delete-orphan")
    policies: Mapped[list["Policy"]] = relationship(
        "Policy", back_populates="organization", cascade="all, delete-orphan")
    overrides: Mapped[list["Override"]] = relationship(
        "Override", back_populates="organization", cascade="all, delete-orphan")
    executions: Mapped[list["Execution"]] = relationship(
        "Execution", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(
        String, default="viewer")  # admin, operator, viewer
    is_active: Mapped[bool] = mapped_column(default=True)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(default=False)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    organization: Mapped["Organization"] = relationship(back_populates="users")

    api_keys: Mapped[List["APIKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")
