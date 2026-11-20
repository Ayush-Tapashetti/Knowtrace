"""Masking and the egress allowlist. Every byte bound for a model passes through here.

Two layers: (1) the payload type has *only* allowlisted fields, so student ids, pseudonyms,
answers and mastery numbers cannot be expressed in it; (2) `mask_text` scrubs identifier-shaped
strings from the free text that is allowed through. `mask_text` is deterministic and idempotent.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

# The only things that may leave the trust boundary.
ALLOWED_PAYLOAD_KEYS = frozenset({"concept_name", "allowed_concepts", "text", "reading_level"})
READING_LEVELS = frozenset({"grade 6", "grade 8", "grade 10"})

# Order matters: more specific shapes first, so an email is not half-eaten by the digit rule.
_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    # Any token shaped like local@domain.tld. Deliberately broader than common mail addresses:
    # RFC 5322 allows characters such as * ! # $ & ' / = ? ^ ` { | } ~ in the local part;
    # only brackets, quotes and separators are excluded so surrounding punctuation survives.
    (re.compile(r'[^\s@()<>\[\],;:"]+@[^\s@()<>\[\],;:"]+\.[^\s@()<>\[\],;:"]*[A-Za-z]{2,}'), "[email]"),
    (re.compile(r"https?://\S+"), "[link]"),
    (
        re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
        "[id]",
    ),
    (re.compile(r"\bstudent-[0-9a-fA-F]{3,}\b", re.IGNORECASE), "[student]"),
    (re.compile(r"\b\d{2}[A-Za-z]{2,4}\d{3,6}\b"), "[id]"),  # roll-number shaped, e.g. 21ABC1234
    (re.compile(r"(?<![\w.])\+?\d(?:[ -]?\d){8,}(?![\w.])"), "[number]"),  # 9+ digits: phones, ids
)


def mask_text(text: str) -> str:
    """Replace emails, links, UUIDs, student pseudonyms, roll numbers and long digit runs.

    Ordinary maths (`1/2 + 3.14 = 100`) is untouched. Applying it twice changes nothing.
    """
    for pattern, placeholder in _RULES:
        text = pattern.sub(placeholder, text)
    return text


@dataclass(frozen=True, slots=True)
class RephrasePayload:
    concept_name: str
    allowed_concepts: tuple[str, ...]
    text: str
    reading_level: str


def build_rephrase_payload(
    text: str, concept_name: str, allowed_concepts: Sequence[str], reading_level: str = "grade 8"
) -> RephrasePayload:
    """Build the only object a prompt may be rendered from. Every string is masked."""
    if reading_level not in READING_LEVELS:
        raise ValueError(f"reading_level must be one of {sorted(READING_LEVELS)}")
    return RephrasePayload(
        concept_name=mask_text(concept_name),
        allowed_concepts=tuple(sorted({mask_text(c) for c in allowed_concepts})),
        text=mask_text(text),
        reading_level=reading_level,
    )
