from __future__ import annotations

import itertools
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from knowtrace.domain.bkt import bkt_transition
from knowtrace.domain.errors import InvalidParameterError
from knowtrace.domain.forecast import (
    beta_cdf,
    beta_quantile,
    forecast_interval,
    forecast_mastery,
    predict_next_correct,
    time_to_mastery,
)

rate = st.floats(0.01, 0.5)


@given(st.floats(0.01, 0.99), rate, rate, st.integers(0, 40))
def test_closed_form_equals_iterating_the_transition(p0: float, learn: float, forget: float, n: int) -> None:
    p = p0
    for _ in range(n):
        p = bkt_transition(p, learn, forget)
    assert forecast_mastery(p0, learn, forget, n) == pytest.approx(p, abs=1e-9)


@given(st.floats(0.01, 0.99), st.floats(0.01, 0.5), st.floats(0.01, 0.49))
def test_forecast_is_monotone_toward_the_long_run_level(p0: float, learn: float, forget: float) -> None:
    if learn + forget > 1:
        return
    star = learn / (learn + forget)
    seq = [forecast_mastery(p0, learn, forget, n) for n in range(15)]
    assert seq[0] == pytest.approx(p0)
    diffs = [b - a for a, b in itertools.pairwise(seq)]
    assert all(d >= -1e-9 for d in diffs) if p0 <= star else all(d <= 1e-9 for d in diffs)
    assert all(abs(x - star) <= abs(p0 - star) + 1e-9 for x in seq)


def test_forecast_rejects_bad_parameters() -> None:
    with pytest.raises(InvalidParameterError):
        forecast_mastery(0.5, 0.1, 0.1, -1)
    with pytest.raises(InvalidParameterError):
        forecast_mastery(0.5, 0.0, 0.0, 1)


def test_time_to_mastery() -> None:
    assert time_to_mastery(0.9, 0.15, 0.02, 0.85, 100) == 0
    n = time_to_mastery(0.3, 0.15, 0.02, 0.85, 100)
    assert n is not None and forecast_mastery(0.3, 0.15, 0.02, n) >= 0.85 > forecast_mastery(
        0.3, 0.15, 0.02, n - 1
    )
    assert time_to_mastery(0.3, 0.05, 0.10, 0.85, 1000) is None  # long-run level 0.33 < theta
    assert time_to_mastery(0.3, 0.15, 0.02, 0.85, 3) is None  # reachable, but not within 3 steps


def test_beta_cdf_matches_known_values() -> None:
    assert beta_cdf(2, 2, 0.5) == pytest.approx(0.5, abs=1e-12)  # symmetric
    assert beta_cdf(1, 1, 0.3) == pytest.approx(0.3, abs=1e-12)  # uniform
    assert beta_cdf(2, 1, 0.5) == pytest.approx(0.25, abs=1e-12)  # F(x) = x^2
    assert beta_cdf(1, 3, 0.5) == pytest.approx(1 - 0.5**3, abs=1e-12)  # F(x) = 1-(1-x)^3
    assert beta_cdf(5, 5, 0.0) == 0.0 and beta_cdf(5, 5, 1.0) == 1.0
    with pytest.raises(InvalidParameterError):
        beta_cdf(0, 1, 0.5)


@given(st.floats(0.5, 20), st.floats(0.5, 20), st.floats(0.02, 0.98))
def test_quantile_inverts_cdf(a: float, b: float, q: float) -> None:
    assert beta_cdf(a, b, beta_quantile(a, b, q)) == pytest.approx(q, abs=1e-8)


def test_interval_brackets_the_mean_and_narrows_with_evidence() -> None:
    lo, hi = forecast_interval(0.6, 10)
    assert lo < 0.6 < hi
    lo2, hi2 = forecast_interval(0.6, 100)
    assert (hi2 - lo2) < (hi - lo) and lo < lo2 and hi2 < hi
    lo3, hi3 = forecast_interval(0.6, 10, level=0.5)
    assert (hi3 - lo3) < (hi - lo)
    # Beta(2,1) check: 5th percentile of F(x)=x^2 is sqrt(0.05)
    assert beta_quantile(2, 1, 0.05) == pytest.approx(math.sqrt(0.05), abs=1e-9)
    with pytest.raises(InvalidParameterError):
        forecast_interval(0.5, 0)


def test_predict_next_correct_is_noisy_and() -> None:
    assert predict_next_correct(["A"], {"A": 0.5}, 0.1, 0.2) == pytest.approx(0.5 * 0.9 + 0.5 * 0.2)
