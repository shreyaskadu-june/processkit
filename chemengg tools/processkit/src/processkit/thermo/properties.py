"""Thermophysical properties via CoolProp, with Pint units in and out.

Example
-------
>>> from processkit.thermo import Fluid
>>> from processkit import Q_
>>> water = Fluid("Water")
>>> round(water.density(T=Q_(25, "degC"), P=Q_(1, "atm")).to("kg/m^3").magnitude)  # doctest: +SKIP
997

Any argument may be a Pint quantity (converted to SI internally) or a bare
number already in SI units (K, Pa).
"""

from __future__ import annotations

from dataclasses import dataclass

import CoolProp.CoolProp as CP

from ..units import Q_, ureg


def _si(value, si_unit: str) -> float:
    if isinstance(value, ureg.Quantity):
        return float(value.to(si_unit).magnitude)
    return float(value)


def _out(value: float, unit: str):
    return Q_(value, unit)


@dataclass
class Fluid:
    """A pure fluid or CoolProp mixture string, e.g. ``"Water"`` or ``"Water[0.5]&Ethanol[0.5]"``."""

    name: str

    def __post_init__(self) -> None:
        # Validate early so typos fail at construction, not deep in a calculation.
        try:
            CP.PropsSI("Tcrit", self.name)
        except ValueError as exc:
            raise ValueError(f"CoolProp does not recognise fluid '{self.name}'.") from exc

    # ---- state-point properties --------------------------------------------
    def _prop(self, output: str, t, p, unit: str):
        value = CP.PropsSI(output, "T", _si(t, "K"), "P", _si(p, "Pa"), self.name)
        return _out(value, unit)

    def density(self, T, P):
        return self._prop("D", T, P, "kg/m^3")

    def molar_density(self, T, P):
        return self._prop("Dmolar", T, P, "mol/m^3")

    def enthalpy(self, T, P):
        return self._prop("H", T, P, "J/kg")

    def entropy(self, T, P):
        return self._prop("S", T, P, "J/kg/K")

    def cp(self, T, P):
        return self._prop("CPMASS", T, P, "J/kg/K")

    def cv(self, T, P):
        return self._prop("CVMASS", T, P, "J/kg/K")

    def viscosity(self, T, P):
        return self._prop("VISCOSITY", T, P, "Pa*s")

    def conductivity(self, T, P):
        return self._prop("CONDUCTIVITY", T, P, "W/m/K")

    def prandtl(self, T, P):
        return _out(CP.PropsSI("PRANDTL", "T", _si(T, "K"), "P", _si(P, "Pa"), self.name), "dimensionless")

    def phase(self, T, P) -> str:
        return CP.PhaseSI("T", _si(T, "K"), "P", _si(P, "Pa"), self.name)

    # ---- saturation and critical data --------------------------------------
    def saturation_pressure(self, T):
        return _out(CP.PropsSI("P", "T", _si(T, "K"), "Q", 0, self.name), "Pa")

    def saturation_temperature(self, P):
        return _out(CP.PropsSI("T", "P", _si(P, "Pa"), "Q", 0, self.name), "K")

    def latent_heat(self, T):
        """Enthalpy of vaporisation at temperature T (J/kg)."""
        t = _si(T, "K")
        h_v = CP.PropsSI("H", "T", t, "Q", 1, self.name)
        h_l = CP.PropsSI("H", "T", t, "Q", 0, self.name)
        return _out(h_v - h_l, "J/kg")

    @property
    def critical_temperature(self):
        return _out(CP.PropsSI("Tcrit", self.name), "K")

    @property
    def critical_pressure(self):
        return _out(CP.PropsSI("pcrit", self.name), "Pa")

    @property
    def molar_mass(self):
        return _out(CP.PropsSI("M", self.name), "kg/mol")
