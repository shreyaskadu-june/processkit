"""Heat exchanger sizing and rating (LMTD and effectiveness-NTU methods).

Conventions: temperatures in any consistent unit (K or degC; only differences
matter), heat capacity rates ``C = m_dot * cp`` in W/K, duty in W, U in
W/m^2/K, area in m^2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

ARRANGEMENTS = ("counterflow", "parallel", "shell_and_tube")
_TOL = 1e-9


# --------------------------------------------------------------------------
# Basic helpers
# --------------------------------------------------------------------------
def sensible_duty(m_dot: float, cp: float, t_in: float, t_out: float) -> float:
    """Heat duty magnitude (W) for a stream heated or cooled without phase change."""
    return abs(m_dot * cp * (t_out - t_in))


def lmtd(dt1: float, dt2: float) -> float:
    """Log-mean temperature difference from the two terminal differences."""
    if dt1 <= 0 or dt2 <= 0:
        raise ValueError(
            f"Terminal temperature differences must be positive (got {dt1}, {dt2}); "
            "check for a temperature cross or an infeasible approach."
        )
    if abs(dt1 - dt2) <= _TOL * max(dt1, dt2):
        return 0.5 * (dt1 + dt2)
    return (dt1 - dt2) / math.log(dt1 / dt2)


def _terminal_differences(th_in, th_out, tc_in, tc_out, flow):
    if flow == "parallel":
        return th_in - tc_in, th_out - tc_out
    # counterflow and shell-and-tube (counter-current reference)
    return th_in - tc_out, th_out - tc_in


def lmtd_correction_factor(th_in: float, th_out: float, tc_in: float, tc_out: float) -> float:
    """LMTD correction factor F for one shell pass with an even number of tube passes.

    Uses the Bowman/Mueller/Nagle closed form. Raises ``ValueError`` when the
    duty is infeasible for a single shell (F undefined); use more shells or a
    different arrangement in that case.
    """
    if tc_out <= tc_in or th_in <= th_out:
        raise ValueError("Hot stream must cool and cold stream must heat.")
    r = (th_in - th_out) / (tc_out - tc_in)
    p = (tc_out - tc_in) / (th_in - tc_in)
    if not 0 < p < 1:
        raise ValueError(f"Thermal effectiveness P={p:.3f} is outside (0, 1); infeasible.")
    if abs(r - 1.0) < 1e-7:
        arg_num = 2 - p * (2 - math.sqrt(2))
        arg_den = 2 - p * (2 + math.sqrt(2))
        if arg_den <= 0:
            raise ValueError("Infeasible for a single shell pass (temperature cross).")
        return (math.sqrt(2) * p / (1 - p)) / math.log(arg_num / arg_den)
    s = math.sqrt(r * r + 1)
    if 1 - r * p <= 0:
        raise ValueError("Infeasible for a single shell pass (temperature cross).")
    num_arg = 2 - p * (r + 1 - s)
    den_arg = 2 - p * (r + 1 + s)
    if den_arg <= 0:
        raise ValueError("Infeasible for a single shell pass (temperature cross).")
    return (s / (r - 1)) * math.log((1 - p) / (1 - r * p)) / math.log(num_arg / den_arg)


# --------------------------------------------------------------------------
# LMTD sizing
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class HXSizing:
    area: float  #: required heat transfer area, m^2
    duty: float  #: W
    lmtd: float  #: uncorrected LMTD for the chosen flow arrangement
    f_correction: float  #: LMTD correction factor (1 for pure counter/parallel flow)
    u: float  #: overall coefficient used, W/m^2/K
    arrangement: str


def size_by_lmtd(
    duty: float,
    u: float,
    th_in: float,
    th_out: float,
    tc_in: float,
    tc_out: float,
    arrangement: str = "counterflow",
) -> HXSizing:
    """Required area A = Q / (U * F * LMTD)."""
    if arrangement not in ARRANGEMENTS:
        raise ValueError(f"arrangement must be one of {ARRANGEMENTS}")
    if u <= 0 or duty <= 0:
        raise ValueError("duty and u must be positive")
    flow = "parallel" if arrangement == "parallel" else "counter"
    dt1, dt2 = _terminal_differences(th_in, th_out, tc_in, tc_out, flow)
    lm = lmtd(dt1, dt2)
    f = lmtd_correction_factor(th_in, th_out, tc_in, tc_out) if arrangement == "shell_and_tube" else 1.0
    return HXSizing(area=duty / (u * f * lm), duty=duty, lmtd=lm, f_correction=f, u=u, arrangement=arrangement)


# --------------------------------------------------------------------------
# Effectiveness-NTU
# --------------------------------------------------------------------------
def effectiveness(ntu: float, cr: float, arrangement: str = "counterflow") -> float:
    """Heat exchanger effectiveness from NTU and capacity ratio Cr = Cmin/Cmax."""
    if ntu < 0 or not 0 <= cr <= 1:
        raise ValueError("Need ntu >= 0 and 0 <= cr <= 1")
    if cr == 0:
        return 1 - math.exp(-ntu)
    if arrangement == "counterflow":
        if abs(cr - 1) < _TOL:
            return ntu / (1 + ntu)
        e = math.exp(-ntu * (1 - cr))
        return (1 - e) / (1 - cr * e)
    if arrangement == "parallel":
        return (1 - math.exp(-ntu * (1 + cr))) / (1 + cr)
    if arrangement == "shell_and_tube":
        s = math.sqrt(1 + cr * cr)
        e = math.exp(-ntu * s)
        return 2.0 / (1 + cr + s * (1 + e) / (1 - e)) if ntu > 0 else 0.0
    raise ValueError(f"arrangement must be one of {ARRANGEMENTS}")


def ntu_from_effectiveness(eff: float, cr: float, arrangement: str = "counterflow") -> float:
    """Invert the effectiveness relation to get NTU."""
    if not 0 < eff < 1:
        raise ValueError("effectiveness must be in (0, 1)")
    if cr == 0:
        return -math.log(1 - eff)
    if arrangement == "counterflow":
        if abs(cr - 1) < _TOL:
            return eff / (1 - eff)
        return math.log((eff - 1) / (eff * cr - 1)) / (cr - 1)
    if arrangement == "parallel":
        if eff >= 1 / (1 + cr):
            raise ValueError(f"effectiveness {eff:.3f} exceeds the parallel-flow limit {1 / (1 + cr):.3f}")
        return -math.log(1 - eff * (1 + cr)) / (1 + cr)
    if arrangement == "shell_and_tube":
        s = math.sqrt(1 + cr * cr)
        big_e = (2 / eff - (1 + cr)) / s
        if big_e <= 1:
            raise ValueError("effectiveness too high for a single shell pass")
        return -math.log((big_e - 1) / (big_e + 1)) / s
    raise ValueError(f"arrangement must be one of {ARRANGEMENTS}")


@dataclass(frozen=True)
class HXRating:
    duty: float
    effectiveness: float
    ntu: float
    cr: float
    t_hot_out: float
    t_cold_out: float


def rate_by_ntu(
    c_hot: float,
    c_cold: float,
    ua: float,
    t_hot_in: float,
    t_cold_in: float,
    arrangement: str = "counterflow",
) -> HXRating:
    """Rate an existing exchanger: given UA and inlet temperatures, find duty and outlets.

    ``c_hot`` and ``c_cold`` are heat capacity rates m_dot*cp (W/K). For a
    condensing or boiling stream pass a very large value (e.g. 1e12).
    """
    c_min, c_max = min(c_hot, c_cold), max(c_hot, c_cold)
    cr = c_min / c_max
    ntu = ua / c_min
    eff = effectiveness(ntu, cr, arrangement)
    q = eff * c_min * (t_hot_in - t_cold_in)
    return HXRating(
        duty=q,
        effectiveness=eff,
        ntu=ntu,
        cr=cr,
        t_hot_out=t_hot_in - q / c_hot,
        t_cold_out=t_cold_in + q / c_cold,
    )
