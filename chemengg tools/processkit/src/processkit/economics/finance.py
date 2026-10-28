"""Discounted cash flow metrics, levelised costs and one-way sensitivity analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from scipy.optimize import brentq


def npv(rate: float, cashflows: Sequence[float]) -> float:
    """Net present value; ``cashflows[0]`` occurs at t = 0 (undiscounted)."""
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def irr(cashflows: Sequence[float], bracket: tuple[float, float] = (-0.99, 10.0)) -> float:
    """Internal rate of return: the rate where NPV is zero.

    Raises ``ValueError`` if the cash flows have no sign change or no root
    inside ``bracket``.
    """
    if not (any(cf < 0 for cf in cashflows) and any(cf > 0 for cf in cashflows)):
        raise ValueError("IRR needs at least one negative and one positive cash flow.")
    try:
        return brentq(lambda r: npv(r, cashflows), *bracket, xtol=1e-12)
    except ValueError as exc:
        raise ValueError("No IRR found in the bracket; the project may have multiple sign changes.") from exc


def payback_period(cashflows: Sequence[float]) -> float | None:
    """Simple (undiscounted) payback in periods, interpolated. None if never recovered."""
    cumulative = 0.0
    for t, cf in enumerate(cashflows):
        previous = cumulative
        cumulative += cf
        if t > 0 and cumulative >= 0 > previous:
            return (t - 1) + (-previous / cf)
    return None


def capital_recovery_factor(rate: float, years: int) -> float:
    """CRF = r (1 + r)^n / ((1 + r)^n - 1). Reduces to 1/n when r = 0."""
    if years <= 0:
        raise ValueError("years must be positive")
    if rate == 0:
        return 1.0 / years
    g = (1.0 + rate) ** years
    return rate * g / (g - 1.0)


def levelized_cost(
    capex: float,
    annual_opex: float,
    annual_output: float,
    rate: float,
    lifetime_years: int,
    annual_fuel_or_feed: float = 0.0,
) -> float:
    """Levelised cost of a constant-output asset: (CAPEX x CRF + fixed/variable costs) / annual output.

    Use this for LCOE (output in MWh, costs in currency) or LCOH (output in kg H2).
    Assumes constant annual output and costs, with no degradation, tax or
    financing structure. For those, use a full cash-flow model instead.
    """
    if annual_output <= 0:
        raise ValueError("annual_output must be positive")
    crf = capital_recovery_factor(rate, lifetime_years)
    return (capex * crf + annual_opex + annual_fuel_or_feed) / annual_output


def lcoe(
    capex: float,
    annual_opex: float,
    annual_energy: float,
    rate: float,
    lifetime_years: int,
    annual_fuel: float = 0.0,
) -> float:
    """Levelised cost of electricity (currency per unit of annual_energy)."""
    return levelized_cost(capex, annual_opex, annual_energy, rate, lifetime_years, annual_fuel)


def lcoh(
    capex: float,
    annual_opex: float,
    annual_hydrogen: float,
    rate: float,
    lifetime_years: int,
    annual_electricity_cost: float = 0.0,
) -> float:
    """Levelised cost of hydrogen (currency per unit of annual_hydrogen).

    For electrolytic hydrogen, pass the annual electricity bill as
    ``annual_electricity_cost``.
    """
    return levelized_cost(capex, annual_opex, annual_hydrogen, rate, lifetime_years, annual_electricity_cost)


@dataclass(frozen=True)
class SensitivityRow:
    parameter: str
    low_input: float
    high_input: float
    low_output: float
    high_output: float

    @property
    def swing(self) -> float:
        return abs(self.high_output - self.low_output)


def one_way_sensitivity(
    model: Callable[[Mapping[str, float]], float],
    base: Mapping[str, float],
    ranges: Mapping[str, tuple[float, float]],
) -> list[SensitivityRow]:
    """Vary each parameter across its (low, high) range, holding the rest at base.

    Returns rows sorted by output swing, largest first, ready for a tornado chart.
    """
    rows: list[SensitivityRow] = []
    for name, (lo, hi) in ranges.items():
        if name not in base:
            raise KeyError(f"'{name}' must be present in base values")
        p_lo = {**base, name: lo}
        p_hi = {**base, name: hi}
        rows.append(SensitivityRow(name, lo, hi, model(p_lo), model(p_hi)))
    return sorted(rows, key=lambda r: r.swing, reverse=True)
