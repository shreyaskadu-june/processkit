"""Ideal-solution (Raoult's law) vapour-liquid equilibrium and flash calculations.

Sources: Rachford and Rice (1952); Antoine constants from the NIST WebBook. See REFERENCES.md.

Pressures are in bar and temperatures in K, matching the Antoine constants.
Valid only for ideal liquid and ideal vapour phases: low-to-moderate pressure
and chemically similar components. Use an equation of state for anything
else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, Sequence

import numpy as np
from scipy.optimize import brentq


class Antoine(NamedTuple):
    """log10(P / bar) = A - B / (C + T / K)."""

    name: str
    A: float
    B: float
    C: float


#: Antoine constants (NIST-style: P in bar, T in K). Check the validity range
#: of each correlation before relying on it far outside those limits.
ANTOINE: dict[str, Antoine] = {
    "benzene": Antoine("benzene", 4.01814, 1203.835, -53.226),
    "toluene": Antoine("toluene", 4.07827, 1343.943, -53.773),
    "water": Antoine("water", 5.40221, 1838.675, -31.737),
}


def psat_bar(ant: Antoine, t: float) -> float:
    """Pure-component vapour pressure (bar) at temperature ``t`` (K)."""
    return 10.0 ** (ant.A - ant.B / (ant.C + t))


def ideal_k_values(antoines: Sequence[Antoine], t: float, p: float) -> np.ndarray:
    """K-values K_i = Psat_i(T) / P for an ideal solution."""
    return np.array([psat_bar(a, t) / p for a in antoines])


@dataclass(frozen=True)
class FlashResult:
    vapor_fraction: float  #: V/F, 0 (all liquid) to 1 (all vapour)
    x: np.ndarray  #: liquid mole fractions
    y: np.ndarray  #: vapour mole fractions
    phase: str  #: "liquid", "two-phase" or "vapor"


def rachford_rice(z: Sequence[float], k: Sequence[float]) -> float:
    """Solve the Rachford-Rice equation for the vapour fraction beta.

    Returns 0 or 1 when the mixture is entirely liquid or entirely vapour.
    """
    z = np.asarray(z, dtype=float)
    k = np.asarray(k, dtype=float)

    def f(beta: float) -> float:
        return float(np.sum(z * (k - 1.0) / (1.0 + beta * (k - 1.0))))

    if f(0.0) <= 0.0:  # sum(z K) <= 1: subcooled liquid
        return 0.0
    if f(1.0) >= 0.0:  # sum(z / K) <= 1: superheated vapour
        return 1.0
    lo = 1.0 / (1.0 - k.max()) if k.max() > 1 else 0.0
    hi = 1.0 / (1.0 - k.min()) if k.min() < 1 else 1.0
    lo = max(lo, 0.0) + 1e-12
    hi = min(hi, 1.0) - 1e-12
    return float(brentq(f, lo, hi, xtol=1e-14))


def flash_tp(z: Sequence[float], k: Sequence[float]) -> FlashResult:
    """Isothermal-isobaric flash given feed composition and K-values."""
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    k = np.asarray(k, dtype=float)
    beta = rachford_rice(z, k)
    x = z / (1.0 + beta * (k - 1.0))
    y = k * x
    x, y = x / x.sum(), y / y.sum()
    phase = "liquid" if beta == 0.0 else "vapor" if beta == 1.0 else "two-phase"
    return FlashResult(beta, x, y, phase)


def flash_pt_ideal(z: Sequence[float], antoines: Sequence[Antoine], p: float, t: float) -> FlashResult:
    """Flash at pressure ``p`` (bar) and temperature ``t`` (K) assuming Raoult's law."""
    return flash_tp(z, ideal_k_values(antoines, t, p))


def _bracket_root(fun, lo: float, hi: float, what: str) -> float:
    try:
        return brentq(fun, lo, hi, xtol=1e-10)
    except ValueError as exc:
        raise ValueError(f"Could not bracket the {what} between {lo} K and {hi} K.") from exc


def bubble_point_pressure(x: Sequence[float], antoines: Sequence[Antoine], t: float) -> float:
    """Bubble pressure (bar) of liquid with composition ``x`` at temperature ``t`` (K)."""
    x = np.asarray(x, dtype=float)
    return float(sum(xi * psat_bar(a, t) for xi, a in zip(x, antoines)))


def dew_point_pressure(y: Sequence[float], antoines: Sequence[Antoine], t: float) -> float:
    """Dew pressure (bar) of vapour with composition ``y`` at temperature ``t`` (K)."""
    y = np.asarray(y, dtype=float)
    return float(1.0 / sum(yi / psat_bar(a, t) for yi, a in zip(y, antoines)))


def bubble_point_temperature(
    x: Sequence[float], antoines: Sequence[Antoine], p: float, t_bounds: tuple[float, float] = (150.0, 700.0)
) -> float:
    """Bubble temperature (K) at pressure ``p`` (bar)."""
    x = np.asarray(x, dtype=float)

    def f(t: float) -> float:
        return float(sum(xi * psat_bar(a, t) for xi, a in zip(x, antoines))) - p

    return _bracket_root(f, *t_bounds, what="bubble temperature")


def dew_point_temperature(
    y: Sequence[float], antoines: Sequence[Antoine], p: float, t_bounds: tuple[float, float] = (150.0, 700.0)
) -> float:
    """Dew temperature (K) at pressure ``p`` (bar)."""
    y = np.asarray(y, dtype=float)

    def f(t: float) -> float:
        return float(1.0 / sum(yi / psat_bar(a, t) for yi, a in zip(y, antoines))) - p

    return _bracket_root(f, *t_bounds, what="dew temperature")
