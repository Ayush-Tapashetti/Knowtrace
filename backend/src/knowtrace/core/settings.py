"""Typed settings loaded from environment / `.env` (see repo-root `.env.example`).

Every non-`VITE_*` variable in `.env.example` is a field here, and vice versa
(enforced by `tests/test_settings.py`).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # the shared .env also holds VITE_* variables
        case_sensitive=False,
    )

    # --- App ---
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(8000, ge=1, le=65535)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    rate_limit_per_minute: int = Field(120, ge=1)

    # --- Data ---
    database_url: str = "sqlite:///./data/knowtrace.db"
    curriculum_dir: str = "./backend/content/seed"
    auto_reseed: bool = True

    # --- Domain thresholds (defaults equal Step 3 DomainConfig) ---
    theta_master: float = Field(0.85, gt=0.0, lt=1.0)
    tau_conf: float = Field(0.80, gt=0.5, lt=1.0)  # must beat the runner-up, so > 0.5
    min_probes: int = Field(1, ge=0)
    max_probes: int = Field(4, ge=1)
    max_rechecks: int = Field(3, ge=1)
    lesson_budget_seconds: int = Field(300, ge=30)
    min_checks: int = Field(2, ge=1)

    # --- Determinism / optional model (D3) ---
    deterministic_only: bool = True
    llm_rephrase_enabled: bool = False
    anthropic_api_key: SecretStr | None = None  # optional; never logged
    llm_model: str = "claude-sonnet-5-5"
    llm_timeout_seconds: float = Field(8.0, gt=0)
    llm_max_retries: int = Field(1, ge=0)

    # --- Eval harness (D1, D2) ---
    eval_seed: int = 1234
    eval_n_students: int = Field(300, ge=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            v = [o.strip() for o in v.split(",") if o.strip()]
        if isinstance(v, list) and "*" in v:
            raise ValueError("CORS_ORIGINS must not contain a wildcard")
        return v

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _empty_key_is_unset(cls, v: object) -> object:
        return None if v == "" else v

    @model_validator(mode="after")
    def _check_consistency(self) -> Settings:
        if self.max_probes < self.min_probes:
            raise ValueError("MAX_PROBES must be >= MIN_PROBES")
        return self

    @property
    def llm_enabled(self) -> bool:
        """True only if every gate for the optional model is open (D3)."""
        key = self.anthropic_api_key
        return (
            not self.deterministic_only
            and self.llm_rephrase_enabled
            and key is not None
            and bool(key.get_secret_value())
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
