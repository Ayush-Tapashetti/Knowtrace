from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from knowtrace.core.deps import CtxDep
from knowtrace.schemas.common import ERROR_RESPONSES, Limit, Offset
from knowtrace.schemas.curriculum import ConceptDetailOut, ConceptPage, GraphOut, ItemOut, ItemPage
from knowtrace.services import curriculum as svc

router = APIRouter(tags=["curriculum"], responses=ERROR_RESPONSES)


@router.get("/concepts", summary="List concepts (paginated, filterable)")
def list_concepts(
    ctx: CtxDep,
    limit: Limit = 50,
    offset: Offset = 0,
    strand: Annotated[str | None, Query(max_length=60)] = None,
    q: Annotated[str | None, Query(max_length=60, description="Case-insensitive name search")] = None,
) -> ConceptPage:
    return ConceptPage.model_validate(svc.list_concepts(ctx, strand=strand, q=q, limit=limit, offset=offset))


@router.get("/concepts/{concept_id}", summary="One concept with its prerequisites and dependents")
def get_concept(concept_id: str, ctx: CtxDep) -> ConceptDetailOut:
    return ConceptDetailOut.model_validate(svc.get_concept(ctx, concept_id))


@router.get("/graph", summary="The whole prerequisite graph (nodes in topological order)")
def get_graph(ctx: CtxDep) -> GraphOut:
    return GraphOut.model_validate(svc.graph_view(ctx))


@router.get("/items", summary="List practice items (answers are never returned)")
def list_items(
    ctx: CtxDep,
    limit: Limit = 50,
    offset: Offset = 0,
    concept_id: Annotated[str | None, Query(max_length=100)] = None,
) -> ItemPage:
    return ItemPage.model_validate(svc.list_items(ctx, concept_id=concept_id, limit=limit, offset=offset))


@router.get("/items/{item_id}", summary="One practice item (no answer key)")
def get_item(item_id: str, ctx: CtxDep) -> ItemOut:
    return ItemOut.model_validate(svc.get_item(ctx, item_id))
