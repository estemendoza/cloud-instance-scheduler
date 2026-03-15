from pydantic import BaseModel, computed_field
from typing import Optional
from datetime import datetime, timezone
import uuid

DEFAULT_KEY_EXPIRY_DAYS = 90


class APIKeyBase(BaseModel):
    name: str
    expires_at: Optional[datetime] = None


class APIKeyCreate(APIKeyBase):
    pass  # Only name and expires_at needed; user_id comes from current_user


class APIKeyShow(APIKeyBase):
    id: uuid.UUID
    prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None

    @computed_field
    @property
    def days_until_expiry(self) -> Optional[int]:
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    @computed_field
    @property
    def expires_soon(self) -> bool:
        if not self.expires_at:
            return False
        delta = self.expires_at - datetime.now(timezone.utc)
        return 0 <= delta.days <= 7

    class Config:
        from_attributes = True

# Returned only once upon creation


class APIKeyCreated(APIKeyShow):
    key: str  # The plain text key


class APIKeyBootstrap(BaseModel):
    user_id: uuid.UUID
