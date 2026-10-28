"""Shortcut distillation: Fenske (minimum stages), Underwood (minimum reflux),
Gilliland (actual stages, Eduljee form) and Kirkbride (feed stage location).

Assumes constant relative volatility, a saturated-liquid or general feed
described by its thermal condition q, and sharp-ish key-component split.
These are screening-level estimates, not a rigorous stage-by-stage design.
Sources: Fenske (1932), Underwood (1946), Eduljee (1975), Kirkbride (1944). See REFERENCES.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from scipy.optimize import brentq


@dataclass(frozen=True)
class FenskeSplit:
    distillate_ratio: float  #: (x_LK / x_HK) in distillate
    bottoms_ratio: float  #: (x_LK / x_HK) in bottoms


def fenske_min_stages(
    xd_lk: float, xd_hk: float, xb_lk: float, xb_hk: float, alpha_lk_hk: float
) -> float:
    """Minimum theoretical stages at total reflux (Fenske equation).

    ``alpha_lk_hk`` is the relative volatility of the light key with respect
    to the heavy key. Returns stages including the reboiler.
    """
    if alpha_lk_hk <= 1:
        raise ValueError("Light key must be more volatile than the heavy key (alpha > 1).")
    if min(xd_lk, xd_hk, xb_lk, xb_hk) <= 0:
        raise ValueError(
            "Key-component mole fractions must be strictly positive for the Fenske equation; "
            "specify a small nonzero value (e.g. 1e-4) instead of zero."
        )
    return math.log((xd_lk / xd_hk) * (xb_hk / xb_lk)) / math.log(alpha_lk_hk)


def fenske_split(alpha_lk_hk: float, n_stages: float, bottoms_ratio: float) -> FenskeSplit:
    """Distillate composition ratio for ``n_stages`` at total reflux.

    Rearranges the Fenske equation: (x_LK/x_HK)_D = alpha^N * (x_LK/x_HK)_B.
    """
    d_ratio = alpha_lk_hk**n_stages * bottoms_ratio
    return FenskeSplit(distillate_ratio=d_ratio, bottoms_ratio=bottoms_ratio)


def underwood_theta(alphas: Sequence[float], z: Sequence[float], q: float, alpha_lk: float, alpha_hk: float) -> float:
    """Root theta of Underwood's first equation, sum(alpha_i z_i / (alpha_i - theta)) = 1 - q.

    theta lies strictly between alpha_HK and alpha_LK.
    """
    if alpha_lk <= alpha_hk:
        raise ValueError("alpha_lk must be greater than alpha_hk.")

    def f(theta: float) -> float:
        return sum(a * zi / (a - theta) for a, zi in zip(alphas, z)) - (1.0 - q)

    return brentq(f, alpha_hk + 1e-9, alpha_lk - 1e-9, xtol=1e-12)


def underwood_min_reflux(alphas: Sequence[float], xd: Sequence[float], theta: float) -> float:
    """Minimum reflux ratio from Underwood's second equation.

    R_min + 1 = sum(alpha_i x_D,i / (alpha_i - theta)).
    """
    return sum(a * xdi / (a - theta) for a, xdi in zip(alphas, xd)) - 1.0


def gilliland(n_min: float, r: float, r_min: float) -> float:
    """Actual number of stages N for reflux ratio ``r``, via the Eduljee form of the Gilliland correlation."""
    if r <= r_min:
        raise ValueError("Reflux ratio must exceed the minimum reflux ratio.")
    x = (r - r_min) / (r + 1.0)
    y = 1.0 - math.exp(((1.0 + 54.4 * x) / (11.0 + 117.2 * x)) * ((x - 1.0) / math.sqrt(x)))
    return (n_min + y) / (1.0 - y)


def kirkbride(
    z_hk_feed: float,
    z_lk_feed: float,
    xb_lk: float,
    xd_hk: float,
    b_over_d: float,
) -> float:
    """Kirkbride ratio of rectifying to stripping stages, N_rect / N_strip.

    log10(N_rect / N_strip) = 0.206 * log10[(B/D) (z_HK/z_LK) (x_LK,B / x_HK,D)^2]

    Arguments: feed heavy- and light-key mole fractions, light-key fraction
    in the bottoms, heavy-key fraction in the distillate, and B/D.
    """
    ratio = b_over_d * (z_hk_feed / z_lk_feed) * (xb_lk / xd_hk) ** 2
    return 10.0 ** (0.206 * math.log10(ratio))


@dataclass(frozen=True)
class FUGResult:
    n_min: float  #: minimum stages (incl. reboiler)
    theta: float  #: Underwood theta
    r_min: float  #: minimum reflux ratio
    r: float  #: operating reflux ratio
    n_actual: float  #: actual theoretical stages (incl. reboiler)
    feed_stage_fraction: float  #: N_rect / N_actual (rough feed location estimate)


def fug_design(
    alphas: Sequence[float],
    z_feed: Sequence[float],
    xd: Sequence[float],
    xb: Sequence[float],
    lk: int,
    hk: int,
    q: float = 1.0,
    reflux_factor: float = 1.2,
    b_over_d: float | None = None,
) -> FUGResult:
    """Full Fenske-Underwood-Gilliland shortcut design.

    Parameters
    ----------
    alphas : relative volatilities of every component (same reference component)
    z_feed, xd, xb : feed, distillate and bottoms mole fractions per component
    lk, hk : indices of the light and heavy key components
    q : feed thermal condition (1 = saturated liquid, 0 = saturated vapour)
    reflux_factor : operating R as a multiple of R_min (commonly 1.1 to 1.5)
    b_over_d : bottoms/distillate molar ratio, needed only for the feed-stage estimate
    """
    alpha_lk_hk = alphas[lk] / alphas[hk]
    n_min = fenske_min_stages(xd[lk], xd[hk], xb[lk], xb[hk], alpha_lk_hk)
    theta = underwood_theta(alphas, z_feed, q, alphas[lk], alphas[hk])
    r_min = underwood_min_reflux(alphas, xd, theta)
    r = reflux_factor * r_min
    n_act = gilliland(n_min, r, r_min)
    feed_frac = float("nan")
    if b_over_d is not None:
        ratio = kirkbride(z_feed[hk], z_feed[lk], xb[lk], xd[hk], b_over_d)
        feed_frac = ratio / (1.0 + ratio)
    return FUGResult(n_min, theta, r_min, r, n_act, feed_frac)
