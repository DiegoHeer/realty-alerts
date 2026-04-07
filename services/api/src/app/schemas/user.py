from sqlmodel import SQLModel


class UserRead(SQLModel):
    email: str | None
    timezone: str


class UserUpdate(SQLModel):
    timezone: str | None = None
