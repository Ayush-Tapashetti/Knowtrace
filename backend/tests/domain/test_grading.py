from __future__ import annotations

import pytest

from knowtrace.domain.enums import ItemKind
from knowtrace.domain.errors import InvalidAnswerError, QMatrixError
from knowtrace.domain.grading import grade_answer, parse_number
from knowtrace.domain.types import ItemSpec
from tests.domain.fixture import mcq


def numeric(answer: str, **kw: float) -> ItemSpec:
    return ItemSpec("n", ItemKind.NUMERIC, answer, **kw)  # type: ignore[arg-type]


def test_mcq_exact_match_and_wrong_choice() -> None:
    item = mcq("q")
    assert grade_answer(item, "a") is True
    assert grade_answer(item, " b ") is False  # whitespace tolerated, wrong choice
    with pytest.raises(InvalidAnswerError):
        grade_answer(item, "z")  # unknown choice id is malformed, not merely wrong


@pytest.mark.parametrize(
    ("given", "ok"), [("0.75", True), ("3/4", True), ("6/8", True), ("-0.75", False), ("0.7", False)]
)
def test_numeric_exact_across_decimal_and_fraction(given: str, ok: bool) -> None:
    assert grade_answer(numeric("3/4"), given) is ok


def test_numeric_tolerances_are_inclusive_and_either_suffices() -> None:
    assert grade_answer(numeric("10", tolerance_abs=0.5), "10.5") is True
    assert grade_answer(numeric("10", tolerance_abs=0.5), "10.51") is False
    assert grade_answer(numeric("100", tolerance_rel=0.01), "101") is True
    assert grade_answer(numeric("100", tolerance_rel=0.01), "102") is False
    assert grade_answer(numeric("100", tolerance_abs=0.1, tolerance_rel=0.05), "104") is True  # rel passes


@pytest.mark.parametrize("bad", ["", "abc", "1e9999999", "1/0", "nan", "inf", "1,5", "--1", "1" * 40])
def test_malformed_numbers_raise(bad: str) -> None:
    with pytest.raises(InvalidAnswerError):
        grade_answer(numeric("1"), bad)


def test_unparseable_item_answer_is_a_content_error() -> None:
    with pytest.raises(QMatrixError):
        grade_answer(numeric("oops"), "1")


def test_parse_number_is_exact() -> None:
    assert parse_number("0.1") + parse_number("0.2") == parse_number("0.3")  # no float drift
