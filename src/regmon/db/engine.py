"""Engine and session factory creation for SQLite and PostgreSQL.

A single :func:`create_database` entry point builds an engine appropriate for
the configured ``database_url`` (applying SQLite-specific connect args and an
in-memory-safe pool) and returns a :class:`Database` handle bundling the engine
with a configured session factory.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from regmon.db.base import Base
from regmon.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class Database:
    """Bundles a SQLAlchemy engine with its session factory."""

    engine: Engine
    session_factory: sessionmaker[Session]

    def create_all(self) -> None:
        """Create all tables registered on the ORM metadata."""
        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        """Drop all tables (intended for tests and teardown)."""
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Provide a transactional session scope that commits or rolls back."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        """Release all pooled connections."""
        self.engine.dispose()


def create_database(url: str, *, echo: bool = False) -> Database:
    """Create a :class:`Database` for ``url`` (SQLite or PostgreSQL).

    In-memory SQLite uses a :class:`StaticPool` so all sessions share the one
    connection (and thus the same schema/data); file-based SQLite gets
    ``check_same_thread=False`` for use across threads.
    """
    is_sqlite = url.startswith("sqlite")
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {"echo": echo, "future": True}

    if is_sqlite:
        connect_args["check_same_thread"] = False
        if ":memory:" in url or url in ("sqlite://", "sqlite:///:memory:"):
            engine_kwargs["poolclass"] = StaticPool

    engine = create_engine(url, connect_args=connect_args, **engine_kwargs)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    log.info("db.engine_created", dialect=engine.dialect.name)
    return Database(engine=engine, session_factory=session_factory)


__all__ = ["Database", "create_database"]
