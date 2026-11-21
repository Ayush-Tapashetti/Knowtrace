"""Every endpoint, driven for real, matches docs/openapi.json (see contract_check.py)."""

from __future__ import annotations

from tests.api.contract_check import run


def test_every_endpoint_matches_the_exported_contract() -> None:
    driver, problems = run()
    assert not problems, "\n".join(problems)
    assert len(driver.seen) >= 21
