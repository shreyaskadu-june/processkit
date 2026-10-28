"""Single-phase pipe pressure drop and pump duty (SI units throughout)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from scipy.optimize import brentq

G = 9.80665  #: standard gravity, m/s^2

#: Approximate resistance coefficients K for common fittings (turbulent flow,
#: typical textbook values). Real values depend on size and geometry; supply
#: your own via ``k_extra`` for design-quality work.
FITTING_K: dict[str, float] = {
    "elbow_90": 0.75,
    "elbow_45": 0.35,
    "tee_run": 0.4,
    "tee_branch": 1.0,
    "gate_valve_open": 0.17,
    "globe_valve_open": 6.0,
    "ball_valve_open": 0.05,
    "check_valve_swing": 2.0,
    "entrance_sharp": 0.5,
    "entrance_rounded": 0.05,
    "exit": 1.0,
}


def reynolds(density: float, velocity: float, diameter: float, viscosity: float) -> float:
    return density * velocity * diameter / viscosity


def _colebrook(re: float, rel_rough: float) -> float:
    f = 0.25 / (math.log10(rel_rough / 3.7 + 5.74 / re**0.9)) ** 2  # Swamee-Jain start
    for _ in range(100):
        inv_sqrt = -2.0 * math.log10(rel_rough / 3.7 + 2.51 / (re * math.sqrt(f)))
        f_new = 1.0 / inv_sqrt**2
        if abs(f_new - f) < 1e-12:
            return f_new
        f = f_new
    return f


def friction_factor(re: float, relative_roughness: float = 0.0) -> float:
    """Darcy friction factor.

    Laminar (Re < 2300): 64/Re. Turbulent (Re >= 4000): Colebrook-White.
    The transitional range is linearly interpolated, which is an engineering
    convenience rather than a physical model; treat results there with care.
    """
    if re <= 0:
        raise ValueError("Reynolds number must be positive")
    if re < 2300:
        return 64.0 / re
    if re >= 4000:
        return _colebrook(re, relative_roughness)
    f_lam = 64.0 / 2300.0
    f_turb = _colebrook(4000.0, relative_roughness)
    w = (re - 2300.0) / (4000.0 - 2300.0)
    return f_lam + w * (f_turb - f_lam)


@dataclass(frozen=True)
class PipeResult:
    velocity: float  #: m/s
    reynolds: float
    friction_factor: float
    regime: str
    dp_friction: float  #: Pa
    dp_fittings: float  #: Pa
    dp_static: float  #: Pa (positive = uphill)
    dp_total: float  #: Pa


def pipe_pressure_drop(
    flow: float,
    diameter: float,
    length: float,
    density: float,
    viscosity: float,
    roughness: float = 4.5e-5,
    fittings: Mapping[str, int] | None = None,
    k_extra: float = 0.0,
    elevation_change: float = 0.0,
) -> PipeResult:
    """Pressure drop through a straight pipe with fittings.

    Parameters
    ----------
    flow : volumetric flow rate, m^3/s
    diameter, length, roughness : m (default roughness is commercial steel)
    fittings : mapping of ``FITTING_K`` names to counts, e.g. ``{"elbow_90": 4}``
    k_extra : additional summed K (e.g. equipment or valves with known K)
    elevation_change : outlet minus inlet elevation, m
    """
    area = math.pi * diameter**2 / 4.0
    v = flow / area
    re = reynolds(density, v, diameter, viscosity)
    f = friction_factor(re, roughness / diameter)
    dyn = 0.5 * density * v**2
    k_sum = k_extra
    for name, count in (fittings or {}).items():
        if name not in FITTING_K:
            raise KeyError(f"Unknown fitting '{name}'. Known: {sorted(FITTING_K)}")
        k_sum += FITTING_K[name] * count
    dp_f = f * length / diameter * dyn
    dp_fit = k_sum * dyn
    dp_s = density * G * elevation_change
    regime = "laminar" if re < 2300 else "turbulent" if re >= 4000 else "transitional"
    return PipeResult(v, re, f, regime, dp_f, dp_fit, dp_s, dp_f + dp_fit + dp_s)


def diameter_for_pressure_drop(
    target_dp: float,
    flow: float,
    length: float,
    density: float,
    viscosity: float,
    roughness: float = 4.5e-5,
    fittings: Mapping[str, int] | None = None,
    k_extra: float = 0.0,
    elevation_change: float = 0.0,
) -> float:
    """Smallest pipe inner diameter (m) whose total pressure drop equals ``target_dp`` (Pa)."""

    def residual(d: float) -> float:
        return (
            pipe_pressure_drop(flow, d, length, density, viscosity, roughness, fittings, k_extra, elevation_change).dp_total
            - target_dp
        )

    lo, hi = 0.005, 5.0
    if residual(lo) < 0 or residual(hi) > 0:
        raise ValueError("Target pressure drop cannot be met for diameters between 5 mm and 5 m.")
    return brentq(residual, lo, hi, xtol=1e-9)


@dataclass(frozen=True)
class PumpDuty:
    head: float  #: m of the pumped fluid
    hydraulic_power: float  #: W
    shaft_power: float  #: W


def pump_duty(flow: float, dp: float, density: float, efficiency: float = 0.70) -> PumpDuty:
    """Pump head, hydraulic power and shaft power for a differential pressure ``dp`` (Pa)."""
    if not 0 < efficiency <= 1:
        raise ValueError("efficiency must be in (0, 1]")
    hydraulic = flow * dp
    return PumpDuty(head=dp / (density * G), hydraulic_power=hydraulic, shaft_power=hydraulic / efficiency)


def npsh_available(
    p_source_abs: float,
    p_vapor: float,
    density: float,
    static_head: float = 0.0,
    suction_loss_dp: float = 0.0,
) -> float:
    """NPSH available (m of liquid).

    ``p_source_abs`` is the absolute pressure at the liquid surface of the
    supply vessel, ``static_head`` the liquid level above the pump centreline
    (negative for suction lift), and ``suction_loss_dp`` the friction plus
    fitting loss on the suction line (Pa).
    """
    return (p_source_abs - p_vapor - suction_loss_dp) / (density * G) + static_head
