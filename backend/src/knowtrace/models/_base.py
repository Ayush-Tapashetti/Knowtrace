"""Shared column helpers: UTC timestamps, probability CHECKs, enum columns, id factory."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column
from sqlalchemy import Enum as SAEnum
from sqlalchemy.engine import Dialect
from sqlalchemy.types import DateTime, TypeDecorator

# Probabilities are stored clamped away from 0 and 1 (Step 3: `Prob`).
PROB_EPS = 1e-6


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    """Runtime row ids are UUIDv4 strings (Step 3 ID strategy)."""
    return str(uuid4())


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC, returns timezone-aware UTC. Rejects naive datetimes on write."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime not allowed; pass a UTC-aware datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def prob_check(table: str, column: str, *, nullable: bool = False) -> CheckConstraint:
    """CHECK that a probability column lies in [PROB_EPS, 1 - PROB_EPS]."""
    expr = f"{column} >= {PROB_EPS:.6f} AND {column} <= {1 - PROB_EPS:.6f}"
    if nullable:
        expr = f"{column} IS NULL OR ({expr})"
    return CheckConstraint(expr, name=f"ck_{table}_{column}_prob")


def enum_col(enum_cls: type[Enum], *, nullable: bool = False) -> Column[Any]:
    """String-backed enum column with a DB-level CHECK (works on SQLite and Postgres)."""
    return Column(
        SAEnum(
            enum_cls,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=24,
        ),
        nullable=nullable,
    )
