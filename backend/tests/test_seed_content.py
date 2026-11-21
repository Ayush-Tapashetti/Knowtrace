"""P0-1 on the real authored curriculum (not a fixture): size, mapping, answer keys, lesson budget."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlmodel import Session

from knowtrace.core.db import init_db, make_engine
from knowtrace.domain.config import DomainConfig
from knowtrace.domain.grading import grade_answer
from knowtrace.domain.lesson import assemble_lesson
from knowtrace.services.bundle import CurriculumBundle
from knowtrace.services.curriculum import seed_from_dir

SEED = Path(__file__).resolve().parents[1] / "content" / "seed"


@pytest.fixture(scope="module")
def bundle() -> Iterator[CurriculumBundle]:
    eng = make_engine("sqlite://")
    init_db(eng)
    with Session(eng) as s:
        _, b = seed_from_dir(s, SEED, auto_reseed=False)
    yield b
    eng.dispose()


def test_size_meets_the_scope(bundle: CurriculumBundle) -> None:
    assert len(bundle.graph.concepts) >= 40
    per: dict[str, int] = {c: 0 for c in bundle.graph.concepts}
    for row in bundle.qmatrix.values():
        per[row.primary] += 1
    assert min(per.values()) >= 3, {c: n for c, n in per.items() if n < 3}


def test_every_item_maps_to_a_concept_and_has_one_correct_choice(bundle: CurriculumBundle) -> None:
    for iid, spec in bundle.items.items():
        assert bundle.qmatrix[iid].concepts, iid
        right = [c for c in bundle.item_info[iid].choices if grade_answer(spec, c.id)]
        assert len(right) == 1, iid
        texts = [c.text for c in bundle.item_info[iid].choices]
        assert len(set(texts)) == len(texts), f"duplicate choice text in {iid}"


def test_some_items_need_two_concepts(bundle: CurriculumBundle) -> None:
    assert sum(len(r.concepts) > 1 for r in bundle.qmatrix.values()) >= 5


def test_graph_has_depth_for_ancestor_diagnosis(bundle: CurriculumBundle) -> None:
    assert max(len(a) for a in bundle.graph.anc.values()) >= 6
    assert all(
        bundle.graph.order.index(p) < bundle.graph.order.index(c)
        for c, ps in bundle.graph.parents.items()
        for p in ps
    )


def test_every_concept_can_be_taught_within_five_minutes(bundle: CurriculumBundle) -> None:
    cfg = DomainConfig()
    cold = {c: 0.1 for c in bundle.graph.concepts}
    for cid in bundle.graph.concepts:
        plan = assemble_lesson(
            bundle.graph, bundle.atoms, bundle.items, bundle.qmatrix, cold, cid, [cid], cfg
        )
        again = assemble_lesson(
            bundle.graph, bundle.atoms, bundle.items, bundle.qmatrix, cold, cid, [cid], cfg
        )
        assert plan == again, cid  # P0-4: identical inputs, identical lesson
        assert plan.est_seconds <= cfg.lesson_budget_seconds, cid
        assert (
            sum(1 for s in plan.steps if s.concept_id == cid and s.kind.value == "CHECK") >= cfg.min_checks
        ), cid


def test_lesson_text_is_present_and_names_no_other_concept_id() -> None:
    atoms = json.loads((SEED / "atoms.json").read_text(encoding="utf-8"))
    for a in atoms:
        if a["item_id"] is None:
            assert a["body"].strip(), a["id"]
