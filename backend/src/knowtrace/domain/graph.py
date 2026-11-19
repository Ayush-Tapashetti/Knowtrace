"""Curriculum graph: validation, traversal, Q-matrix checks, coverage."""

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Iterable, Mapping, Sequence

from knowtrace.domain.enums import ItemKind
from knowtrace.domain.errors import (
    GraphCycleError,
    GraphStructureError,
    QMatrixError,
    UnknownConceptError,
)
from knowtrace.domain.grading import parse_number
from knowtrace.domain.types import SLIP, ConceptSpec, Graph, ItemSpec, QRow


def validate_graph(concepts: Sequence[ConceptSpec], edges: Iterable[tuple[str, str]]) -> Graph:
    """Build a `Graph` from concepts and `(concept_id, prereq_id)` edges.

    Rejects duplicate concepts/edges, the reserved id `SLIP`, dangling ids, self-loops and cycles
    (the cycle error carries one concrete cycle path).
    """
    specs: dict[str, ConceptSpec] = {}
    for c in concepts:
        if c.id == SLIP:
            raise GraphStructureError(f"concept id {SLIP!r} is reserved")
        if c.id in specs:
            raise GraphStructureError(f"duplicate concept {c.id!r}")
        specs[c.id] = c

    parent_sets: dict[str, set[str]] = {cid: set() for cid in specs}
    child_sets: dict[str, set[str]] = {cid: set() for cid in specs}
    for dep, pre in edges:
        for cid in (dep, pre):
            if cid not in specs:
                raise UnknownConceptError(cid)
        if dep == pre:
            raise GraphCycleError([dep, dep])
        if pre in parent_sets[dep]:
            raise GraphStructureError(f"duplicate edge {dep!r} -> {pre!r}")
        parent_sets[dep].add(pre)
        child_sets[pre].add(dep)

    parents = {cid: tuple(sorted(s)) for cid, s in parent_sets.items()}
    children = {cid: tuple(sorted(s)) for cid, s in child_sets.items()}

    # Kahn's algorithm with a (tier, id) heap gives a deterministic topological order.
    indeg = {cid: len(parents[cid]) for cid in specs}
    heap = [(specs[cid].tier, cid) for cid, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        _, cid = heapq.heappop(heap)
        order.append(cid)
        for child in children[cid]:
            indeg[child] -= 1
            if indeg[child] == 0:
                heapq.heappush(heap, (specs[child].tier, child))

    if len(order) < len(specs):
        raise GraphCycleError(_find_cycle(parents, set(specs) - set(order)))

    anc: dict[str, frozenset[str]] = {}
    for cid in order:
        acc: set[str] = set()
        for p in parents[cid]:
            acc.add(p)
            acc |= anc[p]
        anc[cid] = frozenset(acc)
    desc: dict[str, frozenset[str]] = {}
    for cid in reversed(order):
        acc = set()
        for ch in children[cid]:
            acc.add(ch)
            acc |= desc[ch]
        desc[cid] = frozenset(acc)

    return Graph(concepts=specs, parents=parents, children=children, order=tuple(order), anc=anc, desc=desc)


def _find_cycle(parents: Mapping[str, tuple[str, ...]], remaining: set[str]) -> list[str]:
    """Every node left after Kahn has a parent that is also left, so walking parents must loop."""
    node = min(remaining)
    seen: dict[str, int] = {}
    path: list[str] = []
    while node not in seen:
        seen[node] = len(path)
        path.append(node)
        node = min(p for p in parents[node] if p in remaining)
    return [*path[seen[node] :], node]


def _require(graph: Graph, concept_id: str) -> None:
    if concept_id not in graph.concepts:
        raise UnknownConceptError(concept_id)


def topological_order(graph: Graph) -> list[str]:
    return list(graph.order)


def parents(graph: Graph, concept_id: str) -> tuple[str, ...]:
    _require(graph, concept_id)
    return graph.parents[concept_id]


def children(graph: Graph, concept_id: str) -> tuple[str, ...]:
    _require(graph, concept_id)
    return graph.children[concept_id]


def _bfs(start: str, step: Mapping[str, tuple[str, ...]]) -> dict[str, int]:
    dist: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque((n, 1) for n in step[start])
    while queue:
        node, d = queue.popleft()
        if node in dist:
            continue
        dist[node] = d
        queue.extend((n, d + 1) for n in step[node])
    return dist


def ancestors(graph: Graph, concept_id: str) -> dict[str, int]:
    """Transitive prerequisites with minimum edge distance. Never includes `concept_id`."""
    _require(graph, concept_id)
    return _bfs(concept_id, graph.parents)


def descendants(graph: Graph, concept_id: str) -> dict[str, int]:
    """Transitive dependents with minimum edge distance. Never includes `concept_id`."""
    _require(graph, concept_id)
    return _bfs(concept_id, graph.children)


def validate_qmatrix(graph: Graph, items: Mapping[str, ItemSpec], qmatrix: Mapping[str, QRow]) -> None:
    """Every item has >= 1 known concept and exactly one primary; item payloads are well-formed."""
    if set(items) != set(qmatrix):
        missing = sorted(set(items) ^ set(qmatrix))
        raise QMatrixError(f"items and Q-matrix disagree on: {missing}")
    for item_id in sorted(items):
        item, row = items[item_id], qmatrix[item_id]
        if not row.concepts:
            raise QMatrixError(f"item {item_id!r} has no concepts")
        if len(set(row.concepts)) != len(row.concepts):
            raise QMatrixError(f"item {item_id!r} repeats a concept")
        for cid in row.concepts:
            _require(graph, cid)
        if row.primary not in row.concepts:
            raise QMatrixError(f"item {item_id!r}: primary {row.primary!r} not among its concepts")
        if item.kind is ItemKind.MCQ:
            if len(item.choices) < 2 or len(set(item.choices)) != len(item.choices):
                raise QMatrixError(f"MCQ item {item_id!r} needs >= 2 distinct choices")
            if item.answer not in item.choices:
                raise QMatrixError(f"MCQ item {item_id!r}: answer is not one of the choices")
        else:
            try:
                parse_number(item.answer)
            except ValueError as exc:
                raise QMatrixError(f"NUMERIC item {item_id!r}: unparseable answer") from exc


def coverage_report(
    graph: Graph, items: Mapping[str, ItemSpec], qmatrix: Mapping[str, QRow]
) -> dict[str, int]:
    """Number of items that require each concept (zero included). Seed gate: >= 3 per concept."""
    counts = dict.fromkeys(sorted(graph.concepts), 0)
    for item_id in items:
        for cid in qmatrix[item_id].concepts:
            _require(graph, cid)
            counts[cid] += 1
    return counts
