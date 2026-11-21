"""App factory: wires settings, database, middleware, error handlers and routers."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from sqlalchemy import Engine
from sqlmodel import Session

from knowtrace.core.db import init_db, make_engine
from knowtrace.core.ratelimit import RateLimitMiddleware
from knowtrace.core.settings import Settings, get_settings
from knowtrace.integrations.llm_client import LLMClient
from knowtrace.routers import api_router, errors
from knowtrace.routers.system import health
from knowtrace.schemas.system import HealthOut
from knowtrace.services.bundle import load_bundle
from knowtrace.services.context import domain_config
from knowtrace.services.curriculum import seed_from_dir

API_PREFIX = "/api/v1"
log = logging.getLogger("knowtrace")


def _operation_id(route: APIRoute) -> str:
    return route.name  # stable, readable names for the generated TypeScript client


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    llm_client: LLMClient | None = None,
    clock: Callable[[], datetime] | None = None,
    seed_on_startup: bool = True,
) -> FastAPI:
    s = settings or get_settings()
    eng = engine or make_engine(s.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(eng)
        seed_dir = Path(s.curriculum_dir)
        with Session(eng) as session:
            if seed_on_startup and (seed_dir / "concepts.json").is_file():
                report, app.state.bundle = seed_from_dir(session, seed_dir, auto_reseed=s.auto_reseed)
                log.info("curriculum %s hash=%s", report.action, report.curriculum_hash[:12])
            else:
                app.state.bundle = load_bundle(session)
                if app.state.bundle is None:
                    log.warning("no curriculum loaded; endpoints that need it return 503")
        try:
            yield
        finally:
            eng.dispose()  # the app owns its engine; release the connection pool on shutdown

    app = FastAPI(
        title="KnowTrace API",
        version="0.1.0",
        description="Root-cause knowledge-gap diagnosis on a curriculum prerequisite graph.",
        lifespan=lifespan,
        generate_unique_id_function=_operation_id,
    )
    app.state.settings, app.state.engine, app.state.llm_client = s, eng, llm_client
    app.state.cfg = domain_config(s)
    app.state.clock = clock or (lambda: datetime.now(UTC))
    app.state.bundle = None
    app.state.rephraser = None

    app.add_middleware(RateLimitMiddleware, per_minute=s.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    errors.install(app)
    app.include_router(api_router, prefix=API_PREFIX)
    app.add_api_route("/health", health, methods=["GET"], include_in_schema=False, response_model=HealthOut)
    return app
