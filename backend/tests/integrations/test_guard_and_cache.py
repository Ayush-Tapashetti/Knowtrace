from __future__ import annotations

import pytest

from knowtrace.integrations.cache import TTLCache, cache_key
from knowtrace.integrations.output_guard import check_output, parse_output
from knowtrace.integrations.payload_mask import build_rephrase_payload

ORIG = "To add fractions with the same denominator, add the tops: 1/4 + 2/4 = 3/4."
ALLOWED = ["Fractions", "Adding fractions"]
OTHERS = ["Counting", "Ratios", "Equivalent fractions", "Mixed numbers"]


def check(out: str, **kw: float) -> str | None:
    return check_output(ORIG, out, allowed_names=ALLOWED, other_names=OTHERS, **kw)  # type: ignore[arg-type]


def test_parse_output_is_strict() -> None:
    assert parse_output('{"text": "  hello  "}') == "hello"
    for bad in (
        "hello",
        "",
        "{}",
        '{"text": ""}',
        '{"text": 5}',
        '{"text": "x", "extra": 1}',
        "[1]",
        '```json\n{"text":"x"}\n```',
    ):
        assert parse_output(bad) is None, bad
    assert parse_output('{"text": "' + "x" * 4001 + '"}') is None


def test_good_rewrite_passes() -> None:
    assert check("When two fractions share a denominator, just add the numerators: 1/4 + 2/4 = 3/4.") is None


@pytest.mark.parametrize(
    ("out", "reason"),
    [
        ("Add them: 1/4 + 2/4 = 3/4. " + "More words. " * 20, "length_ratio"),
        ("Add.", "length_ratio"),
        ("Add the tops, see https://evil.example for more: 1/4 + 2/4 = 3/4.", "markup"),
        ("Add the tops: 1/4 + 2/4 = 3/4. Read [this](x).", "markup"),
        ("To add fractions with the same denominator, add the tops: 1/4 + 2/4 = 4/4.", "numbers_changed"),
        (
            "To add fractions with the same denominator, add the tops: 1/4 + 2/4 = 3/4 or 0.75.",
            "numbers_changed",
        ),
        ("To add fractions with the same bottom, add the tops: 1/4 + 2/4.", "numbers_changed"),
        ("Using equivalent fractions, add the tops of 1/4 + 2/4 = 3/4.", "foreign_concept"),
        ("Think of ratios: add the tops, 1/4 + 2/4 = 3/4 exactly.", "foreign_concept"),
    ],
)
def test_bad_rewrites_are_rejected(out: str, reason: str) -> None:
    assert check(out) == reason


def test_allowed_name_may_contain_a_foreign_name_but_not_the_reverse() -> None:
    # "fractions" is foreign here, yet it only ever appears inside the allowed "Adding fractions"
    got = check_output(
        "Adding fractions: 1/2 + 1/2 = 1.",
        "Adding fractions is easy: 1/2 + 1/2 = 1.",
        allowed_names=["Adding fractions"],
        other_names=["Fractions"],
    )
    assert got is None
    # but "Equivalent fractions" is caught even though it ends with the allowed "fractions"
    got = check_output(
        "Fractions: 1/2 + 1/2 = 1.",
        "Fractions and equivalent fractions: 1/2 + 1/2 = 1.",
        allowed_names=["Fractions"],
        other_names=["Equivalent fractions"],
    )
    assert got == "foreign_concept"


def test_a_name_already_in_the_original_text_is_tolerated() -> None:
    orig = "Ratios build on fractions: 1/2 is 1 to 2."
    ok = check_output(
        orig,
        "Ratios build on fractions, and 1/2 is 1 to 2.",
        allowed_names=["Fractions"],
        other_names=["Ratios"],
    )
    assert ok is None


def test_cache_ttl_lru_and_clear() -> None:
    now = [0.0]
    c = TTLCache(max_entries=2, ttl_seconds=10, clock=lambda: now[0])
    c.put("a", "1")
    now[0] = 5
    c.put("b", "2")
    assert c.get("a") == "1"  # refreshes recency, not the TTL
    c.put("c", "3")  # evicts the least recently used: "b"
    assert c.get("b") is None and c.get("a") == "1" and c.get("c") == "3"
    now[0] = 11  # "a" stored at t=0 is now older than the TTL; "c" (t=5) is not
    assert c.get("a") is None and c.get("c") == "3"
    assert len(c) == 1
    c.clear()
    assert len(c) == 0 and c.get("c") is None


def test_cache_key_changes_with_prompt_version_model_and_input() -> None:
    p = build_rephrase_payload("1/2", "Fractions", ["Fractions"])
    base = cache_key(p, prompt_version="v1", model="m")
    assert cache_key(p, prompt_version="v1", model="m") == base
    assert cache_key(p, prompt_version="v2", model="m") != base
    assert cache_key(p, prompt_version="v1", model="m2") != base
    assert (
        cache_key(build_rephrase_payload("1/3", "Fractions", ["Fractions"]), prompt_version="v1", model="m")
        != base
    )
    assert (
        cache_key(
            build_rephrase_payload("1/2", "Fractions", ["Fractions", "Ratios"]),
            prompt_version="v1",
            model="m",
        )
        != base
    )
