from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

# Organization Schemas


class OrganizationBase(BaseModel):
    name: str
    slug: str


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None


class Organization(OrganizationBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

# User Schemas


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "viewer"
    is_active: bool = True


class UserCreate(UserBase):
    password: str
    organization_id: uuid.UUID


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None  # admin, operator, viewer
    is_active: Optional[bool] = None


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class User(UserBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization: Optional[Organization] = None
    mfa_enabled: bool = False

    class Config:
        from_attributes = True
