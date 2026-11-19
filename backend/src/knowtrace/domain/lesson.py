"""Micro-lesson assembly: pick and order authored atoms along the gap path, within a time budget."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from knowtrace.domain.bkt import clamp_prob
from knowtrace.domain.config import DomainConfig
from knowtrace.domain.enums import AtomKind
from knowtrace.domain.errors import LessonBudgetError, NoContentError, UnknownConceptError
from knowtrace.domain.graph import descendants
from knowtrace.domain.types import AtomSpec, Graph, ItemSpec, LessonPlan, LessonStepPlan, Prob, QRow

_ROOT_CORE = (AtomKind.DEFINITION, AtomKind.WORKED_EXAMPLE, AtomKind.BRIDGE, AtomKind.PRACTICE)
_MID_KINDS = (AtomKind.DEFINITION, AtomKind.WORKED_EXAMPLE, AtomKind.BRIDGE)
# Dropped in this order when the lesson is over budget (definitions and reserved checks never are).
_DROP_ORDER = (AtomKind.BRIDGE, AtomKind.PRACTICE, AtomKind.WORKED_EXAMPLE)


def bridge_concepts(graph: Graph, root: str, targets: Sequence[str]) -> list[str]:
    """Root, targets, and every concept between them, in topological order."""
    for cid in (root, *targets):
        if cid not in graph.concepts:
            raise UnknownConceptError(cid)
    keep: set[str] = {root, *targets}
    for t in targets:
        keep |= graph.desc[root] & graph.anc[t]
    return [c for c in graph.order if c in keep]


def lesson_est_seconds(steps: Sequence[LessonStepPlan]) -> int:
    return sum(s.est_seconds for s in steps)


def _atom_step(a: AtomSpec) -> LessonStepPlan:
    return LessonStepPlan(0, a.concept_id, a.kind, a.est_seconds, atom_id=a.id, item_id=a.item_id)


def _sorted_atoms(atoms: Sequence[AtomSpec], concept: str, kinds: Sequence[AtomKind]) -> list[AtomSpec]:
    out: list[AtomSpec] = []
    for kind in kinds:
        out += sorted(
            (a for a in atoms if a.concept_id == concept and a.kind is kind),
            key=lambda a: (a.order_hint, a.id),
        )
    return out


def _fallback_items(
    concept: str,
    kind: AtomKind,
    items: Mapping[str, ItemSpec],
    qmatrix: Mapping[str, QRow],
    cfg: DomainConfig,
    limit: int,
    used: set[str],
) -> list[LessonStepPlan]:
    """Item-bank steps for a concept with no authored content (easiest first)."""
    pool = sorted(
        (
            i
            for i in items.values()
            if i.id in qmatrix and qmatrix[i.id].primary == concept and i.id not in used
        ),
        key=lambda i: (i.difficulty, i.id),
    )
    steps = [LessonStepPlan(0, concept, kind, cfg.fallback_item_seconds, item_id=i.id) for i in pool[:limit]]
    used.update(s.item_id for s in steps if s.item_id)
    return steps


def assemble_lesson(
    graph: Graph,
    atoms: Sequence[AtomSpec],
    items: Mapping[str, ItemSpec],
    qmatrix: Mapping[str, QRow],
    mastery: Mapping[str, Prob],
    root: str,
    targets: Sequence[str],
    cfg: DomainConfig,
) -> LessonPlan:
    """Build a deterministic lesson for the gap at `root`.

    Order: root core (definition, worked example, bridge, practice), then the unmastered
    intermediate concepts on the way to the targets (topological order, teaching atoms only), then
    the root's check atoms last. Concepts already mastered are skipped; the root is always taught.
    Over budget: drop the farthest intermediates first, then optional root atoms; the first
    `min_checks` root checks are never dropped. Without authored atoms, item-bank items stand in.
    """
    concepts = bridge_concepts(graph, root, targets)
    mids = [
        c for c in concepts
        if c != root and clamp_prob(mastery.get(c, 0.0)) < cfg.theta_master
    ]  # fmt: skip

    used_items: set[str] = {a.item_id for a in atoms if a.item_id and a.concept_id == root}
    # --- root ---
    core = [_atom_step(a) for a in _sorted_atoms(atoms, root, _ROOT_CORE)]
    checks = [_atom_step(a) for a in _sorted_atoms(atoms, root, (AtomKind.CHECK,))]
    # Reserved checks come first: item-bank fallback must never starve them of items.
    if len(checks) < cfg.min_checks:
        checks += _fallback_items(
            root, AtomKind.CHECK, items, qmatrix, cfg, cfg.min_checks - len(checks), used_items
        )
    if len(checks) < cfg.min_checks:
        raise NoContentError(root)
    if not core:
        core = _fallback_items(
            root, AtomKind.PRACTICE, items, qmatrix, cfg, cfg.fallback_items_per_concept, used_items
        )

    # --- intermediates ---
    mid_steps: dict[str, list[LessonStepPlan]] = {}
    for c in mids:
        steps = [_atom_step(a) for a in _sorted_atoms(atoms, c, _MID_KINDS)]
        if not steps:
            steps = _fallback_items(
                c, AtomKind.PRACTICE, items, qmatrix, cfg, cfg.fallback_items_per_concept, set()
            )
        if not steps:
            raise NoContentError(c)
        mid_steps[c] = steps

    def total() -> int:
        return (
            sum(s.est_seconds for s in core)
            + sum(s.est_seconds for steps in mid_steps.values() for s in steps)
            + sum(s.est_seconds for s in checks)
        )

    # --- budget ---
    reserved = cfg.min_checks
    while total() > cfg.lesson_budget_seconds and len(checks) > reserved:
        checks.pop()  # optional extra checks go first
    if total() > cfg.lesson_budget_seconds and mid_steps:
        dist = descendants(graph, root)
        for c in sorted(mid_steps, key=lambda c: (-dist.get(c, 0), c)):
            if total() <= cfg.lesson_budget_seconds:
                break
            del mid_steps[c]
    for kind in _DROP_ORDER:
        while total() > cfg.lesson_budget_seconds:
            idx = next((i for i in range(len(core) - 1, -1, -1) if core[i].kind is kind), None)
            if idx is None:
                break
            core.pop(idx)
    if total() > cfg.lesson_budget_seconds:
        raise LessonBudgetError(f"required steps need {total()}s, budget is {cfg.lesson_budget_seconds}s")

    ordered = [*core, *(s for c in mids if c in mid_steps for s in mid_steps[c]), *checks]
    numbered = tuple(
        LessonStepPlan(i, s.concept_id, s.kind, s.est_seconds, s.atom_id, s.item_id)
        for i, s in enumerate(ordered, start=1)
    )
    return LessonPlan(root, numbered, lesson_est_seconds(numbered))


def recheck_passed(p_root: Prob, correct_streak: int, cfg: DomainConfig) -> bool:
    """Passed once the root concept is mastered and the learner got the latest checks right."""
    return p_root >= cfg.theta_master and correct_streak >= cfg.recheck_streak
