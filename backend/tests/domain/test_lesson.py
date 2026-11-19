from __future__ import annotations

import pytest

from knowtrace.domain.config import DomainConfig
from knowtrace.domain.enums import AtomKind
from knowtrace.domain.errors import LessonBudgetError, NoContentError, UnknownConceptError
from knowtrace.domain.lesson import assemble_lesson, bridge_concepts, lesson_est_seconds, recheck_passed
from knowtrace.domain.types import AtomSpec, LessonPlan
from tests.domain.fixture import CFG, build

CUR = build()
G = CUR.graph
WEAK = {c: 0.2 for c in G.order}


def make(root: str = "B", targets: tuple[str, ...] = ("F",), mastery: dict[str, float] | None = None,
         cfg: DomainConfig = CFG, atoms: list[AtomSpec] | None = None) -> LessonPlan:  # fmt: skip
    return assemble_lesson(G, CUR.atoms if atoms is None else atoms, CUR.items, CUR.qmatrix,
                           mastery or WEAK, root, list(targets), cfg)  # fmt: skip


def test_bridge_concepts_are_root_targets_and_everything_between() -> None:
    assert bridge_concepts(G, "B", ["F"]) == ["B", "C", "E", "F"]
    assert bridge_concepts(G, "C", ["D"]) == ["C", "D"]
    assert bridge_concepts(G, "B", ["B"]) == ["B"]
    assert bridge_concepts(G, "A", ["C", "E"]) == ["A", "B", "C", "E"]
    with pytest.raises(UnknownConceptError):
        bridge_concepts(G, "Z", ["F"])


def test_lesson_is_deterministic_numbered_and_within_budget() -> None:
    plan = make()
    assert plan == make()
    assert [s.position for s in plan.steps] == list(range(1, len(plan.steps) + 1))
    assert plan.est_seconds == lesson_est_seconds(plan.steps) <= CFG.lesson_budget_seconds
    assert plan.root == "B"


def test_lesson_order_and_checks_last() -> None:
    plan = make(cfg=DomainConfig(lesson_budget_seconds=10_000))
    kinds_root = [s.kind for s in plan.steps if s.concept_id == "B"]
    assert kinds_root == [AtomKind.DEFINITION, AtomKind.WORKED_EXAMPLE, AtomKind.BRIDGE, AtomKind.PRACTICE,
                          AtomKind.CHECK, AtomKind.CHECK]  # fmt: skip
    assert plan.steps[0].concept_id == "B" and plan.steps[0].kind is AtomKind.DEFINITION
    assert [s.concept_id for s in plan.steps[-2:]] == ["B", "B"]  # ends with >= min_checks root checks
    assert all(s.kind is AtomKind.CHECK for s in plan.steps[-CFG.min_checks :])
    # first appearance of each concept follows the topological order
    first = list(dict.fromkeys(s.concept_id for s in plan.steps))
    pos = {c: i for i, c in enumerate(G.order)}
    assert first == sorted(first, key=pos.__getitem__)
    assert set(first) == {"B", "C", "E", "F"}


def test_mastered_intermediates_are_skipped_but_root_is_always_taught() -> None:
    mastery = {**WEAK, "C": 0.95, "B": 0.99}
    plan = make(mastery=mastery, cfg=DomainConfig(lesson_budget_seconds=10_000))
    concepts = {s.concept_id for s in plan.steps}
    assert "C" not in concepts and {"B", "E", "F"} <= concepts


def test_budget_drops_farthest_intermediates_first_and_never_the_reserved_checks() -> None:
    full = make(cfg=DomainConfig(lesson_budget_seconds=10_000))
    tight = make(cfg=DomainConfig(lesson_budget_seconds=300))
    assert tight.est_seconds <= 300 < full.est_seconds
    assert "B" in {s.concept_id for s in tight.steps}
    assert "F" not in {s.concept_id for s in tight.steps}  # farthest (distance 3 from B) goes first
    checks = [s for s in tight.steps if s.kind is AtomKind.CHECK and s.concept_id == "B"]
    assert len(checks) >= CFG.min_checks

    tiny = make(root="B", targets=("B",), cfg=DomainConfig(lesson_budget_seconds=200))
    assert tiny.est_seconds <= 200
    assert sum(s.kind is AtomKind.CHECK for s in tiny.steps) >= 2
    assert any(s.kind is AtomKind.DEFINITION for s in tiny.steps)  # definitions are never dropped
    with pytest.raises(LessonBudgetError):
        make(
            root="B", targets=("B",), cfg=DomainConfig(lesson_budget_seconds=99)
        )  # definition 40s + two checks 60s = 100s needed


def test_item_bank_fallback_when_no_atoms_exist() -> None:
    plan = make(root="B", targets=("B",), atoms=[a for a in CUR.atoms if a.concept_id != "B"])
    assert all(s.atom_id is None and s.item_id for s in plan.steps)
    assert sum(s.kind is AtomKind.CHECK for s in plan.steps) == CFG.min_checks
    # fallback steps carry real items from the bank for that concept
    assert all(CUR.qmatrix[s.item_id].primary == "B" for s in plan.steps if s.item_id)


def test_no_content_raises() -> None:
    with pytest.raises(NoContentError):
        assemble_lesson(G, [], {}, {}, WEAK, "B", ["B"], CFG)

    # an intermediate concept with neither atoms nor bank items blocks the lesson
    no_c_atoms = [a for a in CUR.atoms if a.concept_id != "C"]
    no_c_items = {k: v for k, v in CUR.items.items() if CUR.qmatrix[k].primary != "C"}
    with pytest.raises(NoContentError) as e:
        assemble_lesson(G, no_c_atoms, no_c_items, CUR.qmatrix, WEAK, "B", ["D"],
                        DomainConfig(lesson_budget_seconds=10_000))  # fmt: skip
    assert e.value.concept_id == "C"

    # too few items to fill the reserved checks
    few = {k: v for k, v in CUR.items.items() if k in ("i.B.1",)}
    with pytest.raises(NoContentError) as e2:
        assemble_lesson(G, [], few, CUR.qmatrix, WEAK, "B", ["B"], CFG)
    assert e2.value.concept_id == "B"


def test_recheck_needs_mastery_and_streak() -> None:
    assert recheck_passed(0.9, 2, CFG) and recheck_passed(0.85, 3, CFG)
    assert not recheck_passed(0.84, 5, CFG) and not recheck_passed(0.95, 1, CFG)
