import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from utils import utcnow


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    auth_id: uuid.UUID | None = Field(default=None, unique=True, index=True)
    email: str | None = None
    timezone: str = "Europe/Amsterdam"
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))


class PushToken(SQLModel, table=True):
    __tablename__ = "push_tokens"

    id: int | None = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user_profiles.id", index=True)
    expo_push_token: str
    device_name: str | None = None
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
