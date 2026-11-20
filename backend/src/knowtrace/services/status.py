"""Readiness: database reachable, curriculum loaded, and whether the optional model is in play."""

from __future__ import annotations

from sqlalchemy import text

from knowtrace.repositories import curriculum as repo
from knowtrace.services.context import Ctx
from knowtrace.services.views import StatusView


def status(ctx: Ctx) -> StatusView:
    try:
        ctx.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    b = ctx.loaded_bundle
    model_on = ctx.settings.llm_enabled
    return StatusView(
        status="ok" if db_ok and b is not None else "degraded",
        app_env=ctx.settings.app_env,
        database_ok=db_ok,
        curriculum_loaded=b is not None,
        curriculum_hash=b.hash if b else None,
        counts=repo.counts(ctx.session) if db_ok else {},
        llm_mode="model" if model_on else "deterministic",
        fallback_active=not model_on,
        llm_model=ctx.settings.llm_model if model_on else None,
    )
