import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profiles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    supabase_id: uuid.UUID = Field(unique=True, index=True)
    email: str | None = None
    timezone: str = "Europe/Amsterdam"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PushToken(SQLModel, table=True):
    __tablename__ = "push_tokens"

    id: int | None = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user_profiles.id")
    expo_push_token: str
    device_name: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
