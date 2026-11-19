"""Engine creation, session dependency and table initialisation."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from knowtrace.core.settings import get_settings


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _is_memory(url: str) -> bool:
    return url in ("sqlite://", "sqlite:///:memory:")


def _on_sqlite_connect(dbapi_conn: Any, _record: Any) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def make_engine(url: str, *, echo: bool = False) -> Engine:
    """Create an engine. SQLite gets foreign-key enforcement; file DBs also get WAL."""
    if not _is_sqlite(url):
        return create_engine(url, echo=echo)

    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    if _is_memory(url):
        kwargs["poolclass"] = StaticPool  # one shared connection, so tables persist in-test
    else:
        db_path = url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, echo=echo, **kwargs)
    event.listen(engine, "connect", _on_sqlite_connect)
    if not _is_memory(url):

        def _wal(dbapi_conn: Any, _record: Any) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        event.listen(engine, "connect", _wal)
    return engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    s = get_settings()
    return make_engine(s.database_url, echo=s.app_env == "development" and s.log_level == "DEBUG")


def init_db(engine: Engine | None = None) -> None:
    """Create all tables (dev/test). No migrations: content is reseeded on schema change."""
    import knowtrace.models  # noqa: F401  (registers every table on SQLModel.metadata)

    SQLModel.metadata.create_all(engine or get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    with Session(get_engine()) as session:
        yield session
