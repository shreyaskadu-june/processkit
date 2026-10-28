import shutil
from pathlib import Path

import pytest

from processkit import Q_
from processkit.economics import (
    capex_scale,
    capital_recovery_factor,
    escalate,
    irr,
    lcoe,
    lcoh,
    npv,
    one_way_sensitivity,
    payback_period,
)
from processkit.pfd import Flowsheet, render

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "feed_train.yaml"


# ---------------- thermo ----------------
@pytest.fixture(scope="module")
def water():
    from processkit.thermo import Fluid

    return Fluid("Water")


def test_water_density_at_25C_and_1atm(water):
    rho = water.density(T=Q_(25, "degC"), P=Q_(1, "atm")).to("kg/m^3").magnitude
    assert rho == pytest.approx(997.0, rel=5e-3)


def test_water_saturation_temperature_at_1atm(water):
    t_sat = water.saturation_temperature(Q_(101325, "Pa")).to("degC").magnitude
    assert t_sat == pytest.approx(100.0, abs=0.1)


def test_units_are_pint_quantities(water):
    cp = water.cp(T=Q_(300, "K"), P=Q_(1, "bar"))
    assert cp.check("[length] ** 2 / [time] ** 2 / [temperature]")  # J/kg/K dimensions
    assert cp.to("kJ/kg/K").magnitude == pytest.approx(4.18, rel=1e-2)


def test_latent_heat_of_water_at_100C(water):
    hfg = water.latent_heat(Q_(373.15, "K")).to("kJ/kg").magnitude
    assert hfg == pytest.approx(2257, rel=1e-2)


def test_unknown_fluid_raises():
    from processkit.thermo import Fluid

    with pytest.raises(ValueError):
        Fluid("NotARealFluid123")


# ---------------- economics ----------------
def test_six_tenths_rule():
    assert capex_scale(100.0, 1.0, 2.0) == pytest.approx(100 * 2**0.6)


def test_cepci_escalation():
    assert escalate(100.0, 2019, 2021) == pytest.approx(100 * 708.0 / 607.5)


def test_capital_recovery_factor_known_value():
    # 10%, 10 years -> 0.16275
    assert capital_recovery_factor(0.10, 10) == pytest.approx(0.162745, rel=1e-4)
    assert capital_recovery_factor(0.0, 10) == pytest.approx(0.1)


def test_npv_and_irr_consistency():
    cfs = [-100.0, 60.0, 60.0]
    r = irr(cfs)
    assert r == pytest.approx(0.130662, rel=1e-4)
    assert npv(r, cfs) == pytest.approx(0.0, abs=1e-8)


def test_irr_requires_sign_change():
    with pytest.raises(ValueError):
        irr([10.0, 20.0])


def test_payback_period_interpolates():
    assert payback_period([-100.0, 50.0, 50.0, 50.0]) == pytest.approx(2.0)
    assert payback_period([-100.0, 10.0]) is None


def test_lcoe_zero_discount_reduces_to_simple_average():
    # No discounting: CRF = 1/n, so LCOE = (capex/n + opex) / energy
    value = lcoe(capex=1_000_000, annual_opex=20_000, annual_energy=50_000, rate=0.0, lifetime_years=20)
    assert value == pytest.approx((1_000_000 / 20 + 20_000) / 50_000)


def test_lcoh_includes_electricity():
    base = lcoh(capex=5e6, annual_opex=1e5, annual_hydrogen=1e6, rate=0.08, lifetime_years=20)
    with_power = lcoh(capex=5e6, annual_opex=1e5, annual_hydrogen=1e6, rate=0.08, lifetime_years=20,
                      annual_electricity_cost=3e6)
    assert with_power - base == pytest.approx(3.0)


def test_one_way_sensitivity_sorts_by_swing():
    def model(p):
        return 2 * p["a"] + 0.1 * p["b"]

    rows = one_way_sensitivity(model, {"a": 1.0, "b": 1.0}, {"a": (0.5, 1.5), "b": (0.5, 1.5)})
    assert [r.parameter for r in rows] == ["a", "b"]
    assert rows[0].swing == pytest.approx(2.0)


# ---------------- PFD ----------------
def test_example_yaml_loads_and_emits_dot():
    fs = Flowsheet.from_yaml(EXAMPLE)
    dot = fs.to_dot()
    assert dot.startswith("digraph flowsheet {")
    assert '"P-101"' in dot and '"E-101" [' in dot
    assert '"T-101" -> "P-101"' in dot


def test_unknown_stream_endpoint_rejected():
    with pytest.raises(ValueError):
        Flowsheet.from_dict({"units": [{"id": "A"}], "streams": [{"from": "A", "to": "B"}]})


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        Flowsheet.from_dict({"units": [{"id": "A"}, {"id": "A"}]})


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        Flowsheet.from_dict({"units": [{"id": "A", "kind": "spaceship"}]})


def test_quotes_in_labels_are_escaped():
    fs = Flowsheet.from_dict({"units": [{"id": "A", "label": 'say "hi"'}]})
    assert r'say \"hi\"' in fs.to_dot()


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")
def test_render_svg(tmp_path):
    out = render(Flowsheet.from_yaml(EXAMPLE), tmp_path / "pfd.svg")
    assert out.exists()
    assert "<svg" in out.read_text(encoding="utf-8")
