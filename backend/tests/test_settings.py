from pathlib import Path

import pytest
from pydantic import ValidationError

from knowtrace.core.settings import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def _env_example_keys() -> set[str]:
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0])
    return keys


def test_defaults_match_step3_domain_config() -> None:
    s = Settings(_env_file=None)
    assert (s.theta_master, s.tau_conf) == (0.85, 0.80)
    assert (s.min_probes, s.max_probes, s.max_rechecks) == (1, 4, 3)
    assert (s.lesson_budget_seconds, s.min_checks) == (300, 2)
    assert s.deterministic_only is True
    assert s.llm_enabled is False


def test_env_example_and_settings_stay_in_sync() -> None:
    # Every non-frontend variable in .env.example is a Settings field, and vice versa.
    example = {k.lower() for k in _env_example_keys() if not k.startswith("VITE_")}
    fields = set(Settings.model_fields)
    assert example == fields


def test_env_example_loads_cleanly() -> None:
    s = Settings(_env_file=ENV_EXAMPLE)
    assert s.cors_origins == ["http://localhost:5173"]
    assert s.anthropic_api_key is None  # empty value means unset


def test_cors_comma_list_and_wildcard_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, https://b.test")
    assert Settings(_env_file=None).cors_origins == ["http://a.test", "https://b.test"]
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("name", "value"),
    [("THETA_MASTER", "1.5"), ("TAU_CONF", "0.4"), ("MAX_PROBES", "0"), ("API_PORT", "70000")],
)
def test_bad_values_fail_fast(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_min_probes_cannot_exceed_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIN_PROBES", "5")
    monkeypatch.setenv("MAX_PROBES", "4")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_llm_needs_all_three_switches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_REPHRASE_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-not-a-real-key")
    assert Settings(_env_file=None).llm_enabled is False  # DETERMINISTIC_ONLY still true
    monkeypatch.setenv("DETERMINISTIC_ONLY", "false")
    assert Settings(_env_file=None).llm_enabled is True
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert Settings(_env_file=None).llm_enabled is False
