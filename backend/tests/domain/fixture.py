"""Small hand-checkable curriculum used across the domain tests.

A -> B -> C -> D        (arrows point from prerequisite to dependent)
     B -> E -> F
          C -> F        (F has two parents: C and E)
"""

from __future__ import annotations

from dataclasses import dataclass

from knowtrace.domain.config import DomainConfig
from knowtrace.domain.enums import AtomKind, ItemKind
from knowtrace.domain.graph import validate_graph
from knowtrace.domain.types import AtomSpec, ConceptSpec, Graph, ItemSpec, QRow

TIERS = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 3, "F": 4}
EDGES = [("B", "A"), ("C", "B"), ("D", "C"), ("E", "B"), ("F", "C"), ("F", "E")]  # (concept, prereq)
CFG = DomainConfig()


def concept(cid: str, **kw: float) -> ConceptSpec:
    base = {
        "p_init": 0.3,
        "p_learn": 0.15,
        "p_slip": 0.1,
        "p_guess": 0.2,
        "p_forget": 0.02,
        "half_life_days": 14.0,
    }
    base.update(kw)
    return ConceptSpec(id=cid, tier=TIERS.get(cid, 1), **base)  # type: ignore[arg-type]


def mcq(item_id: str, **kw: float) -> ItemSpec:
    return ItemSpec(id=item_id, kind=ItemKind.MCQ, answer="a", choices=("a", "b", "c", "d"), **kw)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Curriculum:
    graph: Graph
    items: dict[str, ItemSpec]
    qmatrix: dict[str, QRow]
    atoms: list[AtomSpec]


def build(items_per_concept: int = 3, guess: float = 0.1) -> Curriculum:
    graph = validate_graph([concept(c) for c in TIERS], EDGES)
    items: dict[str, ItemSpec] = {}
    qmatrix: dict[str, QRow] = {}
    atoms: list[AtomSpec] = []
    for c in TIERS:
        for n in range(1, items_per_concept + 1):
            iid = f"i.{c}.{n}"
            items[iid] = mcq(iid, p_guess=guess, difficulty=n / 10)
            qmatrix[iid] = QRow((c,), c)
        atoms += [
            AtomSpec(f"a.{c}.def", c, AtomKind.DEFINITION, 40, 1),
            AtomSpec(f"a.{c}.ex", c, AtomKind.WORKED_EXAMPLE, 60, 1),
            AtomSpec(f"a.{c}.br", c, AtomKind.BRIDGE, 20, 1),
            AtomSpec(f"a.{c}.pr", c, AtomKind.PRACTICE, 45, 1, item_id=f"i.{c}.1"),
            AtomSpec(f"a.{c}.ck1", c, AtomKind.CHECK, 30, 1, item_id=f"i.{c}.2"),
            AtomSpec(f"a.{c}.ck2", c, AtomKind.CHECK, 30, 2, item_id=f"i.{c}.3"),
        ]
    # two multi-concept items
    items["i.F.multi"] = mcq("i.F.multi", p_guess=guess)
    qmatrix["i.F.multi"] = QRow(("F", "C"), "F")
    items["i.D.multi"] = mcq("i.D.multi", p_guess=guess)
    qmatrix["i.D.multi"] = QRow(("D", "B"), "D")
    return Curriculum(graph, items, qmatrix, atoms)
