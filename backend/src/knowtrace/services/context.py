"""Per-request context handed to every service function."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session

from knowtrace.core.settings import Settings
from knowtrace.domain.config import DomainConfig
from knowtrace.integrations.rephraser import Rephraser
from knowtrace.services.bundle import CurriculumBundle
from knowtrace.services.errors import CurriculumNotLoadedError


@dataclass
class Ctx:
    session: Session
    settings: Settings
    cfg: DomainConfig
    now: datetime
    rephraser: Rephraser | None
    loaded_bundle: CurriculumBundle | None

    @property
    def bundle(self) -> CurriculumBundle:
        if self.loaded_bundle is None:
            raise CurriculumNotLoadedError()
        return self.loaded_bundle

    def commit(self) -> None:
        self.session.commit()


def domain_config(s: Settings) -> DomainConfig:
    return DomainConfig(
        theta_master=s.theta_master,
        tau_conf=s.tau_conf,
        min_probes=s.min_probes,
        max_probes=s.max_probes,
        max_rechecks=s.max_rechecks,
        lesson_budget_seconds=s.lesson_budget_seconds,
        min_checks=s.min_checks,
    )
