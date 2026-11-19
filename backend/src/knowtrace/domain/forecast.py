"""Learning-trajectory forecasts: closed-form mastery curve, time-to-mastery, Beta intervals."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from knowtrace.domain.bkt import clamp_prob, item_success_probability
from knowtrace.domain.errors import InvalidParameterError
from knowtrace.domain.types import Prob


def forecast_mastery(p0: Prob, learn: Prob, forget: Prob, n: int) -> Prob:
    """Mastery after `n` practice opportunities: `p* + (p0 - p*)·(1 - learn - forget)^n`.

    `p* = learn / (learn + forget)` is the long-run level. `n = 0` returns `p0`; the curve is
    monotone toward `p*` whenever `learn + forget <= 1`.
    """
    if n < 0:
        raise InvalidParameterError("n must be >= 0")
    if learn + forget <= 0:
        raise InvalidParameterError("learn + forget must be > 0")
    p_star = learn / (learn + forget)
    return clamp_prob(p_star + (p0 - p_star) * (1.0 - learn - forget) ** n)


def time_to_mastery(p0: Prob, learn: Prob, forget: Prob, theta: Prob, max_steps: int) -> int | None:
    """Smallest `n` with `forecast_mastery >= theta`; None if the long-run level cannot reach it
    ("not reachable at the current rate") or it takes more than `max_steps`."""
    if p0 >= theta:
        return 0
    if learn / (learn + forget) <= theta:
        return None
    for n in range(1, max_steps + 1):
        if forecast_mastery(p0, learn, forget, n) >= theta:
            return n
    return None


# --- Regularised incomplete beta (continued fraction, Lentz) ------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    tiny, eps = 1e-300, 3e-14
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 301):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def beta_cdf(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if a <= 0 or b <= 0:
        raise InvalidParameterError("beta parameters must be > 0")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_quantile(a: float, b: float, q: float) -> float:
    """Inverse of `beta_cdf` by bisection (deterministic, no randomness)."""
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if beta_cdf(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def forecast_interval(p_mean: Prob, n_eff: float, level: float = 0.90) -> tuple[Prob, Prob]:
    """Central interval of Beta(p·n_eff, (1-p)·n_eff). Larger `n_eff` means a narrower band."""
    if n_eff <= 0 or not 0.0 < level < 1.0:
        raise InvalidParameterError("n_eff must be > 0 and level in (0, 1)")
    p = clamp_prob(p_mean)
    a, b = p * n_eff, (1.0 - p) * n_eff
    tail = (1.0 - level) / 2.0
    return clamp_prob(beta_quantile(a, b, tail)), clamp_prob(beta_quantile(a, b, 1.0 - tail))


def predict_next_correct(
    concept_ids: Sequence[str], mastery: Mapping[str, Prob], slip: Prob, guess: Prob
) -> Prob:
    """Probability the next item with these concepts is answered correctly (noisy-AND)."""
    return item_success_probability(concept_ids, mastery, slip, guess)
