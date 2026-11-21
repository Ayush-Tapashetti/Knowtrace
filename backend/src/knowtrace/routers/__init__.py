"""HTTP layer: thin routers. They import services, schemas and core.deps only."""

from fastapi import APIRouter

from knowtrace.routers import curriculum, diagnoses, lessons, students, system

api_router = APIRouter()
for module in (system, curriculum, students, diagnoses, lessons):
    api_router.include_router(module.router)
