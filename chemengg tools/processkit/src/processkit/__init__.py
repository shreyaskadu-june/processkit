"""processkit: chemical engineering and energy systems design tools.

Subpackages
-----------
unitops    Heat exchangers, pipe/pump hydraulics, flash calculations, FUG distillation
thermo     CoolProp wrapper with Pint unit handling
economics  CAPEX scaling/CEPCI, finance metrics, LCOE/LCOH, sensitivity analysis
pfd        Process flow diagram generator (YAML/Python spec -> Graphviz DOT / SVG)

Unless stated otherwise, functions take and return SI units (K or degC where
documented, Pa, kg, m, s, W, J).
"""

from .units import Q_, ureg

__version__ = "0.1.0"

__all__ = ["Q_", "ureg", "__version__"]
