"""Curriculum use cases: seed loading, browsing concepts/items, the graph view."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlmodel import Session

from knowtrace.domain.config import DomainConfig
from knowtrace.domain.enums import AtomKind, ItemKind
from knowtrace.domain.errors import UnknownConceptError
from knowtrace.domain.graph import ancestors
from knowtrace.models import Concept, Item, ItemConcept, LessonAtom, PrerequisiteEdge
from knowtrace.repositories import curriculum as repo
from knowtrace.services import bundle as bundle_mod
from knowtrace.services.bundle import CurriculumBundle
from knowtrace.services.context import Ctx
from knowtrace.services.errors import ConflictError, NotFoundError
from knowtrace.services.views import ConceptDetailView, ConceptView, EdgeView, GraphView, ItemView, Page

SEED_FILES = ("concepts", "edges", "items", "item_concepts", "atoms")
_RUNTIME_TABLES = (
    "forecast_record",
    "lesson_step",
    "lesson",
    "diagnosis_probe",
    "mastery_state",
    "attempt",
    "diagnosis",
    "student",
)


@dataclass(frozen=True)
class SeedReport:
    action: str  # seeded | unchanged | reseeded
    curriculum_hash: str
    counts: dict[str, int]


def _read(directory: Path, name: str) -> list[dict[str, Any]]:
    path = directory / f"{name}.json"
    if not path.is_file():
        raise ConflictError(f"seed file missing: {path.name}", details={"file": path.name})
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ConflictError(f"seed file {path.name} must contain a JSON list")
    return data


def _rows(
    directory: Path,
) -> tuple[list[Concept], list[tuple[str, str]], list[Item], list[ItemConcept], list[LessonAtom]]:
    d = DomainConfig()
    concepts = [
        Concept(
            id=c["id"],
            name=c["name"],
            description=c.get("description", ""),
            strand=c.get("strand", "general"),
            tier=int(c["tier"]),
            p_init=c.get("p_init", d.p_init),
            p_learn=c.get("p_learn", d.p_learn),
            p_slip=c.get("p_slip", d.p_slip),
            p_guess=c.get("p_guess", d.p_guess),
            p_forget=c.get("p_forget", d.p_forget),
            half_life_days=c.get("half_life_days", 14.0),
        )
        for c in _read(directory, "concepts")
    ]
    edges = [(e["concept_id"], e["prereq_id"]) for e in _read(directory, "edges")]
    items = [
        Item(
            id=i["id"],
            stem=i["stem"],
            kind=ItemKind(i["kind"]),
            choices=i.get("choices"),
            answer=str(i["answer"]),
            tolerance_abs=i.get("tolerance_abs"),
            tolerance_rel=i.get("tolerance_rel"),
            difficulty=i.get("difficulty", 0.5),
            p_slip=i.get("p_slip"),
            p_guess=i.get("p_guess"),
        )
        for i in _read(directory, "items")
    ]
    links = [
        ItemConcept(item_id=x["item_id"], concept_id=x["concept_id"], is_primary=bool(x["is_primary"]))
        for x in _read(directory, "item_concepts")
    ]
    atoms = [
        LessonAtom(
            id=a["id"],
            concept_id=a["concept_id"],
            kind=AtomKind(a["kind"]),
            body=a.get("body", ""),
            est_seconds=int(a["est_seconds"]),
            order_hint=int(a.get("order_hint", 0)),
            item_id=a.get("item_id"),
        )
        for a in _read(directory, "atoms")
    ]
    return concepts, edges, items, links, atoms


def seed_from_dir(
    session: Session, directory: Path, *, auto_reseed: bool
) -> tuple[SeedReport, CurriculumBundle]:
    """Validate the authored files with the domain gates, then load them.

    Bad content raises a domain error *before* the database is touched. If the database already
    holds a different curriculum, it is rebuilt only when `auto_reseed` is on (dev), because
    every runtime row (students, attempts, diagnoses) is tied to a curriculum version.
    """
    concepts, edges, items, links, atoms = _rows(directory)
    fresh = bundle_mod.assemble(concepts, edges, items, links, atoms)  # raises on a bad graph/Q-matrix
    current = bundle_mod.load_bundle(session)
    if current is not None and current.hash == fresh.hash:
        return SeedReport("unchanged", fresh.hash, repo.counts(session)), current
    if current is not None:
        if not auto_reseed:
            raise ConflictError(
                "curriculum files changed but AUTO_RESEED is off",
                details={"database_hash": current.hash, "files_hash": fresh.hash},
            )
        for table in _RUNTIME_TABLES:
            session.execute(text(f"DELETE FROM {table}"))
        repo.wipe_curriculum(session)
    repo.add_all(session, concepts)
    repo.add_all(session, [PrerequisiteEdge(concept_id=c, prereq_id=p) for c, p in edges])
    repo.add_all(session, items)
    repo.add_all(session, links)
    repo.add_all(session, atoms)
    session.commit()
    return SeedReport("reseeded" if current else "seeded", fresh.hash, repo.counts(session)), fresh


def _concept_view(b: CurriculumBundle, cid: str) -> ConceptView:
    info = b.concepts[cid]
    return ConceptView(
        info.id, info.name, info.description, info.strand, info.tier, list(b.graph.parents[cid])
    )


def list_concepts(
    ctx: Ctx, *, strand: str | None, q: str | None, limit: int, offset: int
) -> Page[ConceptView]:
    b = ctx.bundle  # 503 when nothing is loaded, even for an empty page
    rows, total = repo.page_concepts(ctx.session, strand=strand, q=q, limit=limit, offset=offset)
    return Page([_concept_view(b, r.id) for r in rows], total, limit, offset)


def get_concept(ctx: Ctx, concept_id: str) -> ConceptDetailView:
    b = ctx.bundle
    if concept_id not in b.graph.concepts:
        raise UnknownConceptError(concept_id)
    base = _concept_view(b, concept_id)
    return ConceptDetailView(
        **base.__dict__,
        dependents=list(b.graph.children[concept_id]),
        ancestors=ancestors(b.graph, concept_id),
        item_count=sum(1 for row in b.qmatrix.values() if concept_id in row.concepts),
    )


def graph_view(ctx: Ctx) -> GraphView:
    b = ctx.bundle
    nodes = [_concept_view(b, cid) for cid in b.graph.order]
    edges = [EdgeView(p, c) for c in b.graph.order for p in b.graph.parents[c]]
    return GraphView(b.hash, nodes, edges)


def list_items(ctx: Ctx, *, concept_id: str | None, limit: int, offset: int) -> Page[ItemView]:
    b = ctx.bundle
    if concept_id is not None and concept_id not in b.graph.concepts:
        raise UnknownConceptError(concept_id)
    rows, total = repo.page_items(ctx.session, concept_id=concept_id, limit=limit, offset=offset)
    return Page([b.item_view(r.id) for r in rows], total, limit, offset)


def get_item(ctx: Ctx, item_id: str) -> ItemView:
    if item_id not in ctx.bundle.items:
        raise NotFoundError("item", item_id)
    return ctx.bundle.item_view(item_id)
