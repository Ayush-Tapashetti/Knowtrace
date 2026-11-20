"""In-memory view of the authored curriculum: validated domain objects plus display text."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from knowtrace.domain.graph import validate_graph, validate_qmatrix
from knowtrace.domain.hashing import curriculum_hash
from knowtrace.domain.types import AtomSpec, ConceptSpec, Graph, ItemSpec, QRow
from knowtrace.models import Concept, Item, ItemConcept, LessonAtom
from knowtrace.repositories import curriculum as repo
from knowtrace.services.views import ChoiceView, ItemView


@dataclass(frozen=True)
class ConceptInfo:
    id: str
    name: str
    description: str
    strand: str
    tier: int


@dataclass(frozen=True)
class ItemInfo:
    id: str
    stem: str
    choices: tuple[ChoiceView, ...]


@dataclass(frozen=True, eq=False)
class CurriculumBundle:
    graph: Graph
    items: dict[str, ItemSpec]
    qmatrix: dict[str, QRow]
    atoms: list[AtomSpec]
    hash: str
    concepts: dict[str, ConceptInfo]
    item_info: dict[str, ItemInfo]

    @property
    def concept_names(self) -> dict[str, str]:
        return {cid: c.name for cid, c in self.concepts.items()}

    def name(self, concept_id: str) -> str:
        info = self.concepts.get(concept_id)
        return info.name if info else concept_id

    def item_view(self, item_id: str) -> ItemView:
        spec, row, info = self.items[item_id], self.qmatrix[item_id], self.item_info[item_id]
        return ItemView(
            id=item_id,
            stem=info.stem,
            kind=spec.kind,
            choices=list(info.choices),
            concept_ids=list(row.concepts),
            primary_concept_id=row.primary,
            difficulty=spec.difficulty,
        )

    def atom_body(self, atom_id: str) -> str:
        return next((a.body for a in self.atoms if a.id == atom_id), "")


def concept_spec(c: Concept) -> ConceptSpec:
    return ConceptSpec(
        id=c.id,
        tier=c.tier,
        p_init=c.p_init,
        p_learn=c.p_learn,
        p_slip=c.p_slip,
        p_guess=c.p_guess,
        p_forget=c.p_forget,
        half_life_days=c.half_life_days,
        name=c.name,
    )


def item_spec(i: Item) -> ItemSpec:
    return ItemSpec(
        id=i.id,
        kind=i.kind,
        answer=i.answer,
        choices=tuple(str(c["id"]) for c in (i.choices or [])),
        tolerance_abs=i.tolerance_abs,
        tolerance_rel=i.tolerance_rel,
        difficulty=i.difficulty,
        p_slip=i.p_slip,
        p_guess=i.p_guess,
    )


def atom_spec(a: LessonAtom) -> AtomSpec:
    return AtomSpec(a.id, a.concept_id, a.kind, a.est_seconds, a.order_hint, a.item_id, a.body)


def qmatrix_from_links(links: list[ItemConcept]) -> dict[str, QRow]:
    by_item: dict[str, list[ItemConcept]] = {}
    for link in links:
        by_item.setdefault(link.item_id, []).append(link)
    out: dict[str, QRow] = {}
    for iid, rows in by_item.items():
        primary = next(r.concept_id for r in rows if r.is_primary)
        out[iid] = QRow(tuple(sorted(r.concept_id for r in rows)), primary)
    return out


def assemble(
    concepts: list[Concept],
    edges: list[tuple[str, str]],
    items: list[Item],
    links: list[ItemConcept],
    atoms: list[LessonAtom],
) -> CurriculumBundle:
    """Validate with the domain gates and build the bundle. Raises domain errors on bad content."""
    graph = validate_graph([concept_spec(c) for c in concepts], edges)
    item_specs = {i.id: item_spec(i) for i in items}
    qmatrix = qmatrix_from_links(links)
    validate_qmatrix(graph, item_specs, qmatrix)
    atom_specs = [atom_spec(a) for a in atoms]
    return CurriculumBundle(
        graph=graph,
        items=item_specs,
        qmatrix=qmatrix,
        atoms=atom_specs,
        hash=curriculum_hash(graph, item_specs, qmatrix, atom_specs),
        concepts={c.id: ConceptInfo(c.id, c.name, c.description, c.strand, c.tier) for c in concepts},
        item_info={
            i.id: ItemInfo(
                i.id, i.stem, tuple(ChoiceView(str(c["id"]), str(c["text"])) for c in (i.choices or []))
            )
            for i in items
        },
    )


def load_bundle(session: Session) -> CurriculumBundle | None:
    """Build the bundle from the database; None when no curriculum has been seeded."""
    concepts = list(repo.all_concepts(session))
    if not concepts:
        return None
    return assemble(
        concepts,
        [(e.concept_id, e.prereq_id) for e in repo.all_edges(session)],
        list(repo.all_items(session)),
        list(repo.all_item_links(session)),
        list(repo.all_atoms(session)),
    )
