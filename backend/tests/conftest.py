from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from knowtrace.core.db import init_db, make_engine


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = make_engine("sqlite://")
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test runs with outbound sockets blocked (local unix sockets stay open for asyncio)."""
    import socket

    real_connect = socket.socket.connect

    def guard(self: socket.socket, address: object) -> None:
        if self.family != socket.AF_UNIX:
            raise RuntimeError(f"Network access is blocked in tests (tried {address!r})")
        real_connect(self, address)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(
        socket.socket,
        "connect_ex",
        lambda self, address: (_ for _ in ()).throw(RuntimeError("Network access is blocked in tests")),
    )
