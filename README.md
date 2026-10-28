# processkit

Chemical engineering and energy systems design tools in Python.

| Module | What it does |
|---|---|
| `processkit.unitops` | Heat exchangers (LMTD, correction factor, ε-NTU), pipe and pump hydraulics, NPSH, ideal VLE flash and bubble/dew points, Fenske-Underwood-Gilliland shortcut distillation with Kirkbride feed location |
| `processkit.thermo` | CoolProp property wrapper with Pint units (density, Cp, viscosity, saturation, latent heat, …) |
| `processkit.economics` | CEPCI indexing, power-law capacity scaling, installed-cost factors, NPV/IRR/payback, capital recovery, LCOE/LCOH, one-way sensitivity (tornado) |
| `processkit.pfd` | Process flow diagrams from YAML or Python: Graphviz DOT, SVG, PNG or PDF, plus a `processkit-pfd` command |

## Install

```bash
pip install -e ".[dev]"
# Graphviz is needed only for rendering diagrams:
#   apt install graphviz   |   brew install graphviz   |   conda install graphviz
```

## Quick examples

```python
from processkit import Q_
from processkit.unitops import size_by_lmtd, fug_design, ANTOINE, flash_pt_ideal
from processkit.thermo import Fluid
from processkit.economics import capex_scale, lcoe, one_way_sensitivity
from processkit.pfd import Flowsheet, render

# Heat exchanger area: 1 MW, U = 500 W/m²K, counterflow
hx = size_by_lmtd(1e6, 500, th_in=150, th_out=90, tc_in=30, tc_out=80)
print(hx.area)  # m²

# Water density at 25 °C, 1 atm (Pint quantity)
rho = Fluid("Water").density(T=Q_(25, "degC"), P=Q_(1, "atm"))
print(rho.to("kg/m^3"))

# Scale a $2.0M reactor from 10 to 25 m³ and escalate 2019 -> 2021 dollars
cost = capex_scale(2.0e6, 10, 25, year_ref=2019, year_new=2021)

# Benzene-toluene flash at 1 atm and 370 K
res = flash_pt_ideal([0.5, 0.5], [ANTOINE["benzene"], ANTOINE["toluene"]], p=1.01325, t=370)
print(res.phase, res.vapor_fraction)

# Shortcut column design
design = fug_design(alphas=[2.5, 1.0, 0.4], z_feed=[0.3, 0.4, 0.3],
                    xd=[0.97, 0.03, 0.0], xb=[0.0, 0.05, 0.95], lk=0, hk=1, q=1.0)
print(design.n_actual, design.r)

# Flowsheet diagram
Flowsheet.from_yaml("examples/feed_train.yaml")  # then: render(fs, "pfd.svg")
```

From the command line:

```bash
processkit-pfd examples/feed_train.yaml -o feed_train.svg
processkit-pfd examples/feed_train.yaml --dot   # print DOT source
```

## Conventions

- Unit-operation functions take plain floats in SI units (K or °C where noted, Pa, kg, m, s, W).
- Thermo functions accept and return Pint quantities. Bare numbers are read as SI.
- Each function documents its model assumptions in its docstring. Read them before using results for design.

## References

The sources for each method are listed in [REFERENCES.md](REFERENCES.md).

## Limitations

These are screening and teaching tools, not replacements for commercial simulators or detailed design.

- VLE flash and bubble/dew calculations assume ideal solutions and use Antoine constants. Use an equation of state for non-ideal or high-pressure systems.
- The shortcut distillation methods assume constant relative volatility and do not model stage-by-stage behaviour.
- Pipe friction uses Colebrook-White in turbulent flow and a linear blend across the transition region.
- The fitting K values are typical textbook figures, not vendor data.
- CEPCI values in `economics/capex.py` are included for convenience. Verify and update them against the published series.

## Web calculators

A static, browser-based version of the calculators lives in `docs/`. It needs no install and works offline once loaded. It covers heat exchanger area, pipe and pump hydraulics, a benzene-toluene flash, shortcut distillation, capital cost scaling, and levelised cost. Thermodynamic property lookups need CoolProp and are only in the Python package for now.

The page is plain HTML, CSS and JavaScript, with no build step. The maths in `docs/js/calc.js` mirrors the Python package and is tested with Node:

```bash
node --test tests/js/calc.test.mjs
```

To publish it on GitHub Pages, go to **Settings → Pages**, choose **Deploy from a branch**, select `main`, and set the folder to `/docs`. The site will then be available at `https://shreyaskadu-june.github.io/processkit/`.

## Testing

```bash
pytest
```

## Licence

MIT.
