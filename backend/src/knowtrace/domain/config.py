"""Domain configuration. Plain data: services build it from Settings, tests build it directly."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainConfig:
    # Diagnosis / mastery thresholds (Step 3 defaults)
    theta_master: float = 0.85
    tau_conf: float = 0.80
    min_probes: int = 1
    max_probes: int = 4
    max_rechecks: int = 3
    recheck_streak: int = 2
    # Lesson assembly
    lesson_budget_seconds: int = 300
    min_checks: int = 2
    fallback_item_seconds: int = 45
    fallback_items_per_concept: int = 2
    # Numerics
    eps: float = 1e-6
    # BKT defaults (used when seeding concepts that omit their own)
    p_init: float = 0.30
    p_learn: float = 0.15
    p_slip: float = 0.10
    p_guess: float = 0.20
    p_forget: float = 0.02
    # Forecast: pseudo-observations behind a fresh concept's Beta interval
    forecast_k0: float = 4.0
