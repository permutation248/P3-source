"""SQLAlchemy 2.0 database setup for Anonymous-Prover."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Optional

import sqlalchemy.exc
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

_engine_cache: dict[str, Engine] = {}


def get_db_url(explicit_url: Optional[str] = None) -> str:
    """Resolve the database URL.

    Priority:
        1. *explicit_url* argument
        2. ``ANONYMOUS_PROVER_DB_URL`` environment variable
        3. Default SQLite path ``sqlite:///data/anonymous_prover.db``
    """
    if explicit_url is not None:
        return explicit_url
    return os.environ.get(
        "ANONYMOUS_PROVER_DB_URL",
        "sqlite:///data/anonymous_prover.db",
    )


def create_db_engine(db_url: Optional[str] = None) -> Engine:
    """Create (or return a cached) SQLAlchemy engine."""
    url = get_db_url(db_url)
    if url not in _engine_cache:
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine_cache[url] = create_engine(
            url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
    return _engine_cache[url]


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a ``sessionmaker`` bound to *engine*."""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db(engine: Engine) -> None:
    """Create all tables defined via ``Base.metadata``."""
    Base.metadata.create_all(bind=engine)
    _ensure_schema_columns(engine)


def _ensure_schema_columns(engine: Engine) -> None:
    """Best-effort lightweight schema migration for additive columns."""
    inspector = inspect(engine)
    try:
        experiment_cols = {c["name"] for c in inspector.get_columns("experiments")}
    except (sqlalchemy.exc.NoSuchTableError, sqlalchemy.exc.OperationalError):
        return

    try:
        task_cols = {c["name"] for c in inspector.get_columns("task_results")}
    except (sqlalchemy.exc.NoSuchTableError, sqlalchemy.exc.OperationalError):
        task_cols = set()

    statements: list[str] = []
    if "tasks_mode" not in experiment_cols:
        statements.append("ALTER TABLE experiments ADD COLUMN tasks_mode VARCHAR")
    if "custom_prompt" not in experiment_cols:
        statements.append("ALTER TABLE experiments ADD COLUMN custom_prompt TEXT")
    if task_cols and "input_tokens" not in task_cols:
        statements.append("ALTER TABLE task_results ADD COLUMN input_tokens INTEGER")
    if task_cols and "output_tokens" not in task_cols:
        statements.append("ALTER TABLE task_results ADD COLUMN output_tokens INTEGER")
    if task_cols and "cost_source" not in task_cols:
        statements.append("ALTER TABLE task_results ADD COLUMN cost_source VARCHAR")

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def get_session(engine: Engine) -> Generator[Session, None, None]:
    """Yield a transactional database session, closing it on exit."""
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
