"""Answer grading. Exact rational arithmetic for numeric answers (no float surprises)."""

from __future__ import annotations

import re
from fractions import Fraction

from knowtrace.domain.enums import ItemKind
from knowtrace.domain.errors import InvalidAnswerError, QMatrixError
from knowtrace.domain.types import ItemSpec

# Plain decimals ("0.75", "-2") or simple fractions ("3/4"). No exponents: they can build huge ints.
_NUMBER = re.compile(r"[+-]?(?:\d{1,12}(?:\.\d{1,12})?|\d{1,12}/\d{1,12})")


def parse_number(text: str) -> Fraction:
    """Parse a decimal or `a/b` fraction exactly. Raises `ValueError` on anything else."""
    s = text.strip()
    if not _NUMBER.fullmatch(s):
        raise ValueError(f"not a number: {text!r}")
    try:
        return Fraction(s)
    except ZeroDivisionError as exc:
        raise ValueError("zero denominator") from exc


def grade_answer(item: ItemSpec, given: str) -> bool:
    """True iff `given` is correct.

    MCQ: exact choice-id match. NUMERIC: within `tolerance_abs` or `tolerance_rel` (either is
    enough); with neither tolerance the value must match exactly. A malformed answer (unknown
    choice id, unparseable number) raises `InvalidAnswerError` and must not be recorded.
    """
    if item.kind is ItemKind.MCQ:
        choice = given.strip()
        if choice not in item.choices:
            raise InvalidAnswerError(f"{choice!r} is not a choice of item {item.id!r}")
        return choice == item.answer

    try:
        value = parse_number(given)
    except ValueError as exc:
        raise InvalidAnswerError(f"cannot read a number from {given!r}") from exc
    try:
        target = parse_number(item.answer)
    except ValueError as exc:
        raise QMatrixError(f"item {item.id!r} has an unparseable numeric answer") from exc

    diff = abs(value - target)
    if diff == 0:
        return True
    if item.tolerance_abs is not None and diff <= Fraction(item.tolerance_abs):
        return True
    return item.tolerance_rel is not None and diff <= Fraction(item.tolerance_rel) * abs(target)
