"""SQLAlchemy declarative base and shared column types.

Defines the ORM :class:`Base` and a :class:`UTCDateTime` type that guarantees
timezone-aware UTC ``datetime`` values on the way in and out of the database.
This matters because SQLite stores naive datetimes; without normalization,
values would round-trip as naive and break comparisons against the tz-aware
``datetime`` objects used throughout the domain models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class UTCDateTime(TypeDecorator[datetime]):
    """A ``DateTime`` that stores UTC and always returns tz-aware UTC values."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


__all__ = ["Base", "UTCDateTime"]
