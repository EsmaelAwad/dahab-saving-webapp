from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, String
from datetime import datetime, date  , timezone


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column("username", String, unique=True))
    password: str  # ⚠️ Plaintext for now

class AuthorizedUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column("username", String, unique=True))


class Deposit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    amount: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    week_number: Optional[int] = None  # for backward compatibility
    week_date: Optional[date] = None  # instead of week_number
    