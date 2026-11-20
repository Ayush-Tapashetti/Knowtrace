"""Curriculum schemas: concepts, the graph, items (never with the answer key)."""

from __future__ import annotations

from pydantic import Field

from knowtrace.domain.enums import ItemKind
from knowtrace.schemas.common import PageMeta, Response


class ConceptOut(Response):
    id: str
    name: str
    description: str
    strand: str
    tier: int
    prerequisites: list[str]


class ConceptDetailOut(ConceptOut):
    dependents: list[str]
    ancestors: dict[str, int] = Field(description="Transitive prerequisite id -> distance in edges")
    item_count: int


class ConceptPage(PageMeta):
    items: list[ConceptOut]


class EdgeOut(Response):
    prerequisite: str
    dependent: str


class GraphOut(Response):
    curriculum_hash: str
    nodes: list[ConceptOut]
    edges: list[EdgeOut]


class ChoiceOut(Response):
    id: str
    text: str


class ItemOut(Response):
    id: str
    stem: str
    kind: ItemKind
    choices: list[ChoiceOut]
    concept_ids: list[str]
    primary_concept_id: str
    difficulty: float


class ItemPage(PageMeta):
    items: list[ItemOut]
