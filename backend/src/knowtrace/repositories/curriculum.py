"""Curriculum queries: concepts, edges, items with their Q-matrix links, lesson atoms."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func
from sqlmodel import Session, col, delete, select

from knowtrace.models import Concept, Item, ItemConcept, LessonAtom, PrerequisiteEdge


def all_concepts(s: Session) -> Sequence[Concept]:
    return s.exec(select(Concept).order_by(col(Concept.tier), col(Concept.id))).all()


def all_edges(s: Session) -> Sequence[PrerequisiteEdge]:
    return s.exec(
        select(PrerequisiteEdge).order_by(col(PrerequisiteEdge.concept_id), col(PrerequisiteEdge.prereq_id))
    ).all()


def all_items(s: Session) -> Sequence[Item]:
    return s.exec(select(Item).order_by(col(Item.id))).all()


def all_item_links(s: Session) -> Sequence[ItemConcept]:
    return s.exec(select(ItemConcept).order_by(col(ItemConcept.item_id), col(ItemConcept.concept_id))).all()


def all_atoms(s: Session) -> Sequence[LessonAtom]:
    return s.exec(
        select(LessonAtom).order_by(
            col(LessonAtom.concept_id), col(LessonAtom.order_hint), col(LessonAtom.id)
        )
    ).all()


def get_concept(s: Session, concept_id: str) -> Concept | None:
    return s.get(Concept, concept_id)


def get_item(s: Session, item_id: str) -> Item | None:
    return s.get(Item, item_id)


def get_atom(s: Session, atom_id: str) -> LessonAtom | None:
    return s.get(LessonAtom, atom_id)


def page_concepts(
    s: Session, *, strand: str | None, q: str | None, limit: int, offset: int
) -> tuple[Sequence[Concept], int]:
    stmt = select(Concept)
    if strand:
        stmt = stmt.where(Concept.strand == strand)
    if q:
        stmt = stmt.where(col(Concept.name).ilike(f"%{q}%"))
    total = s.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = s.exec(stmt.order_by(col(Concept.tier), col(Concept.id)).offset(offset).limit(limit)).all()
    return rows, int(total)


def page_items(s: Session, *, concept_id: str | None, limit: int, offset: int) -> tuple[Sequence[Item], int]:
    stmt = select(Item)
    if concept_id:
        stmt = stmt.where(
            col(Item.id).in_(select(ItemConcept.item_id).where(ItemConcept.concept_id == concept_id))
        )
    total = s.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = s.exec(stmt.order_by(col(Item.id)).offset(offset).limit(limit)).all()
    return rows, int(total)


def counts(s: Session) -> dict[str, int]:
    return {
        "concepts": int(s.exec(select(func.count()).select_from(Concept)).one()),
        "edges": int(s.exec(select(func.count()).select_from(PrerequisiteEdge)).one()),
        "items": int(s.exec(select(func.count()).select_from(Item)).one()),
        "atoms": int(s.exec(select(func.count()).select_from(LessonAtom)).one()),
    }


def wipe_curriculum(s: Session) -> None:
    """Delete authored content in FK-safe order (runtime rows must already be gone)."""
    for table in (LessonAtom, ItemConcept, Item, PrerequisiteEdge, Concept):
        s.exec(delete(table))


def add_all(s: Session, rows: Sequence[object]) -> None:
    s.add_all(rows)
    s.flush()
