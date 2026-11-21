from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api.support import Clock, make_client, write_seed


@pytest.fixture
def seed_dir(tmp_path: Path) -> Path:
    return write_seed(tmp_path / "seed")


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(seed_dir: Path, clock: Clock) -> Iterator[TestClient]:
    with make_client(seed_dir, clock=clock) as c:
        yield c


@pytest.fixture
def empty_client() -> Iterator[TestClient]:
    with make_client(None) as c:
        yield c
