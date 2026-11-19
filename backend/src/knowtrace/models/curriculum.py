"""Authored curriculum content: concepts, prerequisite edges, items, Q-matrix, lesson atoms."""

from typing import Any

from sqlalchemy import JSON, CheckConstraint, Column, Index, text
from sqlmodel import Field, Relationship, SQLModel

from knowtrace.domain.enums import AtomKind, ItemKind
from knowtrace.models._base import enum_col, prob_check


class Concept(SQLModel, table=True):
    __tablename__ = "concept"
    __table_args__ = (
        prob_check("concept", "p_init"),
        prob_check("concept", "p_learn"),
        prob_check("concept", "p_slip"),
        prob_check("concept", "p_guess"),
        prob_check("concept", "p_forget"),
        CheckConstraint("half_life_days > 0", name="ck_concept_half_life_pos"),
    )

    id: str = Field(primary_key=True)  # authored slug, e.g. "frac.add.unlike"
    name: str
    description: str
    strand: str
    tier: int
    p_init: float
    p_learn: float
    p_slip: float
    p_guess: float
    p_forget: float
    half_life_days: float


class PrerequisiteEdge(SQLModel, table=True):
    """`concept_id` depends on `prereq_id`. Acyclicity is enforced by `validate_graph` (5B)."""

    __tablename__ = "prerequisite_edge"
    __table_args__ = (
        CheckConstraint("concept_id <> prereq_id", name="ck_edge_no_self_loop"),
        # query served: descendants_of(c)
        Index("ix_edge_prereq", "prereq_id"),
    )

    concept_id: str = Field(primary_key=True, foreign_key="concept.id", ondelete="CASCADE")
    prereq_id: str = Field(primary_key=True, foreign_key="concept.id", ondelete="CASCADE")


class Item(SQLModel, table=True):
    __tablename__ = "item"
    __table_args__ = (
        prob_check("item", "p_slip", nullable=True),
        prob_check("item", "p_guess", nullable=True),
        CheckConstraint("difficulty >= 0 AND difficulty <= 1", name="ck_item_difficulty_unit"),
        CheckConstraint("tolerance_abs IS NULL OR tolerance_abs >= 0", name="ck_item_tol_abs"),
        CheckConstraint("tolerance_rel IS NULL OR tolerance_rel >= 0", name="ck_item_tol_rel"),
    )

    id: str = Field(primary_key=True)
    stem: str
    kind: ItemKind = Field(sa_column=enum_col(ItemKind))
    choices: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    answer: str
    tolerance_abs: float | None = None
    tolerance_rel: float | None = None
    difficulty: float
    p_slip: float | None = None
    p_guess: float | None = None

    concept_links: list["ItemConcept"] = Relationship(
        back_populates="item", sa_relationship_kwargs={"passive_deletes": True}
    )


class ItemConcept(SQLModel, table=True):
    """Q-matrix row: concept `concept_id` is required to answer item `item_id`."""

    __tablename__ = "item_concept"
    __table_args__ = (
        # query served: items_for_concept(c)
        Index("ix_item_concept_concept_item", "concept_id", "item_id"),
        # exactly-one-primary is enforced as at-most-one here, plus `validate_qmatrix` (5B)
        Index(
            "uq_item_concept_one_primary",
            "item_id",
            unique=True,
            sqlite_where=text("is_primary"),
            postgresql_where=text("is_primary"),
        ),
    )

    item_id: str = Field(primary_key=True, foreign_key="item.id", ondelete="CASCADE")
    concept_id: str = Field(primary_key=True, foreign_key="concept.id", ondelete="RESTRICT")
    is_primary: bool

    item: Item = Relationship(back_populates="concept_links")


class LessonAtom(SQLModel, table=True):
    __tablename__ = "lesson_atom"
    __table_args__ = (
        CheckConstraint("est_seconds > 0", name="ck_atom_est_seconds_pos"),
        CheckConstraint(
            "kind NOT IN ('PRACTICE', 'CHECK') OR item_id IS NOT NULL",
            name="ck_atom_practice_has_item",
        ),
        # query served: atoms_for_concept(c) in assembly order
        Index("ix_atom_concept_kind_order", "concept_id", "kind", "order_hint"),
    )

    id: str = Field(primary_key=True)
    concept_id: str = Field(foreign_key="concept.id", ondelete="RESTRICT")
    kind: AtomKind = Field(sa_column=enum_col(AtomKind))
    body: str
    est_seconds: int
    order_hint: int
    item_id: str | None = Field(default=None, foreign_key="item.id", ondelete="RESTRICT")
