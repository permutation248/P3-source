"""Dependency injection for FastAPI."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

_session_factory: sessionmaker | None = None


def configure(db_url: str) -> None:
    """Initialise the shared session factory from a database URL."""
    from ..models.database import create_db_engine, create_session_factory

    global _session_factory
    engine = create_db_engine(db_url)
    _session_factory = create_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    if _session_factory is None:
        raise RuntimeError("Database not configured. Call configure() first.")
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()
