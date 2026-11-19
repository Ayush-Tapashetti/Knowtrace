from __future__ import annotations

import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from knowtrace.domain.enums import ItemKind
from knowtrace.domain.errors import (
    GraphCycleError,
    GraphStructureError,
    QMatrixError,
    UnknownConceptError,
)
from knowtrace.domain.graph import (
    ancestors,
    children,
    coverage_report,
    descendants,
    parents,
    topological_order,
    validate_graph,
    validate_qmatrix,
)
from knowtrace.domain.hashing import curriculum_hash
from knowtrace.domain.types import ConceptSpec, ItemSpec, QRow
from tests.domain.fixture import EDGES, TIERS, build, concept, mcq


def test_validate_builds_expected_structure() -> None:
    g = build().graph
    assert g.parents["F"] == ("C", "E") and g.children["B"] == ("C", "E")
    assert g.anc["F"] == {"A", "B", "C", "E"}
    assert g.desc["B"] == {"C", "D", "E", "F"}
    assert topological_order(g) == ["A", "B", "C", "E", "D", "F"]  # ties by (tier, id)


def test_cycle_is_rejected_with_a_concrete_path() -> None:
    cs = [concept(c) for c in "ABC"]
    with pytest.raises(GraphCycleError) as e:
        validate_graph(cs, [("B", "A"), ("C", "B"), ("A", "C")])
    path = e.value.path
    assert path[0] == path[-1] and set(path) == {"A", "B", "C"}


def test_self_loop_duplicate_dangling_and_reserved_ids() -> None:
    cs = [concept("A"), concept("B")]
    with pytest.raises(GraphCycleError):
        validate_graph(cs, [("A", "A")])
    with pytest.raises(GraphStructureError):
        validate_graph(cs, [("B", "A"), ("B", "A")])
    with pytest.raises(UnknownConceptError):
        validate_graph(cs, [("B", "Z")])
    with pytest.raises(GraphStructureError):
        validate_graph([concept("SLIP")], [])
    with pytest.raises(GraphStructureError):
        validate_graph([concept("A"), concept("A")], [])


def test_ancestors_descendants_distances_exclude_self() -> None:
    g = build().graph
    assert ancestors(g, "F") == {"C": 1, "E": 1, "B": 2, "A": 3}  # min distance via C or E
    assert descendants(g, "A") == {"B": 1, "C": 2, "E": 2, "D": 3, "F": 3}
    assert "F" not in ancestors(g, "F") and "A" not in descendants(g, "A")
    assert parents(g, "A") == () and children(g, "D") == ()
    with pytest.raises(UnknownConceptError):
        ancestors(g, "nope")


@given(st.integers(0, 10_000), st.integers(2, 25), st.floats(0.0, 0.6))
def test_topological_order_puts_prerequisites_first(seed: int, n: int, density: float) -> None:
    rng = random.Random(seed)
    ids = [f"c{i}" for i in range(n)]
    cs = [ConceptSpec(i, rng.randint(1, 5), 0.3, 0.15, 0.1, 0.2, 0.02, 14.0) for i in ids]
    # a DAG by construction: edges only from later ids to earlier ones, then shuffled
    edges = [(ids[j], ids[i]) for j in range(n) for i in range(j) if rng.random() < density]
    rng.shuffle(edges)
    rng.shuffle(cs)
    g = validate_graph(cs, edges)
    pos = {c: k for k, c in enumerate(g.order)}
    assert sorted(g.order) == sorted(ids)
    assert all(pos[pre] < pos[dep] for dep, pre in edges)
    for c in ids:  # closures agree with BFS and each other
        assert set(ancestors(g, c)) == g.anc[c]
        assert set(descendants(g, c)) == g.desc[c]
        assert all((c in g.desc[a]) for a in g.anc[c])


def test_qmatrix_validation() -> None:
    cur = build()
    validate_qmatrix(cur.graph, cur.items, cur.qmatrix)

    def bad(items: dict[str, ItemSpec], q: dict[str, QRow]) -> None:
        with pytest.raises(QMatrixError):
            validate_qmatrix(cur.graph, items, q)

    bad({**cur.items, "x": mcq("x")}, cur.qmatrix)  # item without a row
    bad(cur.items, {**cur.qmatrix, "i.A.1": QRow((), "A")})  # no concepts
    bad(cur.items, {**cur.qmatrix, "i.A.1": QRow(("A", "B"), "C")})  # primary not among concepts
    bad(
        {**cur.items, "i.A.1": ItemSpec("i.A.1", ItemKind.MCQ, "z", ("a", "b"))}, cur.qmatrix
    )  # answer not a choice
    bad({**cur.items, "i.A.1": ItemSpec("i.A.1", ItemKind.MCQ, "a", ("a",))}, cur.qmatrix)  # one choice
    bad(
        {**cur.items, "i.A.1": ItemSpec("i.A.1", ItemKind.NUMERIC, "abc")}, cur.qmatrix
    )  # unparseable numeric
    with pytest.raises(UnknownConceptError):
        validate_qmatrix(cur.graph, cur.items, {**cur.qmatrix, "i.A.1": QRow(("Q",), "Q")})


def test_coverage_report_counts_every_concept() -> None:
    cur = build()
    cov = coverage_report(cur.graph, cur.items, cur.qmatrix)
    assert set(cov) == set(TIERS)
    assert cov["F"] == 3 + 1 and cov["C"] == 3 + 1 and cov["A"] == 3  # F.multi covers F and C
    assert cov["D"] == 3 + 1 and cov["B"] == 3 + 1  # D.multi covers D and B


def test_curriculum_hash_is_order_independent_and_content_sensitive() -> None:
    cur = build()
    h = curriculum_hash(cur.graph, cur.items, cur.qmatrix, cur.atoms)
    assert len(h) == 64

    shuffled = list(cur.atoms)
    random.Random(1).shuffle(shuffled)
    items = dict(reversed(list(cur.items.items())))
    reordered = validate_graph([concept(c) for c in reversed(list(TIERS))], list(reversed(EDGES)))
    assert curriculum_hash(reordered, items, cur.qmatrix, shuffled) == h

    changed = {**cur.items, "i.A.1": mcq("i.A.1", p_guess=0.11, difficulty=0.1)}
    assert curriculum_hash(cur.graph, changed, cur.qmatrix, cur.atoms) != h
    assert curriculum_hash(cur.graph, cur.items, cur.qmatrix, cur.atoms[:-1]) != h
