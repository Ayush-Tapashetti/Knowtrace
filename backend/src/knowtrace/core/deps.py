"""FastAPI dependencies: one DB session and one service context per request."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from knowtrace.integrations.rephraser import Rephraser
from knowtrace.services.bundle import load_bundle
from knowtrace.services.context import Ctx


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def get_ctx(request: Request, session: Annotated[Session, Depends(get_session)]) -> Ctx:
    st = request.app.state
    if st.bundle is None:  # seeded after startup (tests, CLI): pick it up once
        st.bundle = load_bundle(session)
    if st.rephraser is None and st.bundle is not None:
        st.rephraser = Rephraser.from_settings(st.settings, st.bundle.concept_names, client=st.llm_client)
    return Ctx(
        session=session,
        settings=st.settings,
        cfg=st.cfg,
        now=st.clock(),
        rephraser=st.rephraser,
        loaded_bundle=st.bundle,
    )


CtxDep = Annotated[Ctx, Depends(get_ctx)]
