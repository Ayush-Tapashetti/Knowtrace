"""Read-only access to the latest evaluation run (differentiators D1/D2)."""

from __future__ import annotations

from knowtrace.repositories import diagnoses as repo
from knowtrace.services.context import Ctx
from knowtrace.services.errors import NotFoundError
from knowtrace.services.views import EvalMetric, EvalView


def latest(ctx: Ctx) -> EvalView:
    found = repo.latest_eval(ctx.session)
    if found is None:
        raise NotFoundError("evaluation run", "latest")
    run, results = found
    return EvalView(
        run_id=run.id,
        created_at=run.created_at,
        seed=run.seed,
        n_students=run.n_students,
        curriculum_hash=run.curriculum_hash,
        metrics=[EvalMetric(r.method, r.metric, r.value, r.n, r.detail) for r in results],
    )
