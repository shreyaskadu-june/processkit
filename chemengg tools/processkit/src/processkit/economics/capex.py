"""Capital cost estimation: CEPCI cost indexing and power-law capacity scaling.

CEPCI values below are annual averages recalled from Chemical Engineering
magazine and are provided for convenience only. Verify them against the
published series before using them in a costed study, and add newer years
as they are published.
"""

from __future__ import annotations

from typing import Mapping

CEPCI: dict[int, float] = {
    2018: 603.1,
    2019: 607.5,
    2020: 596.2,
    2021: 708.0,
    2022: 816.0,
    2023: 797.9,
}


def cepci_index(year: int, table: Mapping[int, float] | None = None) -> float:
    table = CEPCI if table is None else table
    if year not in table:
        raise KeyError(f"No CEPCI value for {year}; add it to the table you pass in.")
    return table[year]


def escalate(cost: float, from_year: int, to_year: int, table: Mapping[int, float] | None = None) -> float:
    """Escalate a cost from one year's money to another using the CEPCI."""
    return cost * cepci_index(to_year, table) / cepci_index(from_year, table)


def capex_scale(
    cost_ref: float,
    size_ref: float,
    size_new: float,
    exponent: float = 0.6,
    year_ref: int | None = None,
    year_new: int | None = None,
    table: Mapping[int, float] | None = None,
) -> float:
    """Scale a reference equipment cost to a new capacity with the power law.

    C_new = C_ref * (S_new / S_ref) ** n, optionally escalated with the CEPCI.
    The six-tenths rule (n = 0.6) is a common default but varies by equipment
    type. Typical exponents are roughly 0.5 to 0.8.
    """
    if size_ref <= 0 or size_new <= 0:
        raise ValueError("Sizes must be positive.")
    cost = cost_ref * (size_new / size_ref) ** exponent
    if year_ref is not None and year_new is not None:
        cost = escalate(cost, year_ref, year_new, table)
    return cost


def installed_cost(equipment_cost: float, factors: Mapping[str, float]) -> float:
    """Total installed cost from purchased equipment cost using Lang-style module factors.

    ``factors`` maps item names to fractional allowances, e.g. ``{"installation": 0.4,
    "piping": 0.7, "instrumentation": 0.2}``. Each is multiplied by the purchased
    equipment cost and summed with it. Use your company's or a textbook's factors.
    """
    return equipment_cost * (1.0 + sum(factors.values()))
