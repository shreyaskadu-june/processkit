"""Shared Pint unit registry.

All processkit modules that return quantities with units use this single
registry, so quantities from different modules can be combined freely.
"""

from __future__ import annotations

import pint

ureg = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = ureg.Quantity


def to_float(value, unit: str) -> float:
    """Return ``value`` as a float in ``unit``.

    Pint quantities are converted. Bare numbers are assumed to already be
    expressed in ``unit``.
    """
    if isinstance(value, ureg.Quantity):
        return float(value.to(unit).magnitude)
    return float(value)
