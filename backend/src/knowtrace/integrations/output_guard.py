"""Validation of model output. A reply that fails any check is treated as a failure, never shown."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection

from pydantic import BaseModel, Field, ValidationError

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*(?:/\d+)?")
_BAD_MARKUP = re.compile(r"https?://|www\.|```|\]\(")


class RephraseOutput(BaseModel):
    """The only shape accepted from the model."""

    model_config = {"extra": "forbid"}
    text: str = Field(min_length=1, max_length=4000)


def parse_output(raw: str) -> str | None:
    """Strict JSON parse into `RephraseOutput`; None on any structural problem."""
    try:
        return RephraseOutput.model_validate_json(raw).text.strip() or None
    except ValidationError:
        return None


def _spans(text: str, name: str) -> list[tuple[int, int]]:
    pattern = rf"(?<!\w){re.escape(name)}(?!\w)"
    return [m.span() for m in re.finditer(pattern, text, flags=re.IGNORECASE)]


def _uncovered_mentions(text: str, name: str, allowed_names: Collection[str]) -> int:
    """Mentions of `name` that do not sit entirely inside a mention of an allowed name.

    This is what lets the foreign concept "Fractions" pass inside the allowed "Adding fractions",
    while "Equivalent fractions" is still caught when only "Fractions" is allowed.
    """
    covers = [sp for allowed in allowed_names for sp in _spans(text, allowed)]
    return sum(not any(c0 <= s0 and s1 <= c1 for c0, c1 in covers) for s0, s1 in _spans(text, name))


def check_output(
    original: str,
    output: str,
    *,
    allowed_names: Collection[str],
    other_names: Collection[str],
    min_ratio: float = 0.4,
    max_ratio: float = 2.0,
) -> str | None:
    """None if the rewrite is acceptable, else a short reason code.

    Checks: length ratio, no links/code fences, the multiset of numbers is unchanged (a model must
    not alter or invent maths), and no concept outside the lesson is named more often than in the
    original text.
    """
    if not original.strip():
        return "empty_original"
    ratio = len(output) / len(original)
    if not min_ratio <= ratio <= max_ratio:
        return "length_ratio"
    if _BAD_MARKUP.search(output):
        return "markup"
    if Counter(_NUMBER.findall(original)) != Counter(_NUMBER.findall(output)):
        return "numbers_changed"
    for name in other_names:
        if _uncovered_mentions(output, name, allowed_names) > _uncovered_mentions(
            original, name, allowed_names
        ):
            return "foreign_concept"
    return None
