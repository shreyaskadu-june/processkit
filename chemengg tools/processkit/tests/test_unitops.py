import math

import numpy as np
import pytest

from processkit.unitops import (
    ANTOINE,
    bubble_point_pressure,
    bubble_point_temperature,
    dew_point_temperature,
    diameter_for_pressure_drop,
    effectiveness,
    flash_pt_ideal,
    flash_tp,
    fenske_min_stages,
    fug_design,
    friction_factor,
    gilliland,
    lmtd,
    lmtd_correction_factor,
    ntu_from_effectiveness,
    pipe_pressure_drop,
    pump_duty,
    rachford_rice,
    rate_by_ntu,
    size_by_lmtd,
    underwood_min_reflux,
    underwood_theta,
)


# ---------------- heat exchangers ----------------
def test_lmtd_known_value():
    assert lmtd(20.0, 10.0) == pytest.approx(10.0 / math.log(2.0))


def test_lmtd_equal_differences_returns_arithmetic_mean():
    assert lmtd(15.0, 15.0) == pytest.approx(15.0)


def test_lmtd_rejects_temperature_cross():
    with pytest.raises(ValueError):
        lmtd(10.0, -2.0)


def test_size_by_lmtd_counterflow_area():
    # Q = 1 MW, U = 500 W/m2K, hot 150->90 C, cold 30->80 C (counterflow)
    res = size_by_lmtd(1e6, 500.0, 150.0, 90.0, 30.0, 80.0, "counterflow")
    dt1, dt2 = 150 - 80, 90 - 30
    assert res.lmtd == pytest.approx((dt1 - dt2) / math.log(dt1 / dt2))
    assert res.area == pytest.approx(1e6 / (500 * res.lmtd))


def test_correction_factor_bounded_and_below_one_for_shell():
    f = lmtd_correction_factor(150.0, 90.0, 30.0, 80.0)
    assert 0.0 < f < 1.0


def test_correction_factor_equal_capacity_branch_is_continuous():
    # R = 1 uses a separate closed form; it should join the general one smoothly.
    # Here R = (100-80)/(40-20) = 1 and P = 20/80 = 0.25 (feasible for one shell).
    f_at_r1 = lmtd_correction_factor(100.0, 80.0, 20.0, 40.0)
    f_near_r1 = lmtd_correction_factor(100.0, 80.0 + 1e-4, 20.0, 40.0)
    assert f_at_r1 == pytest.approx(f_near_r1, rel=1e-3)


def test_correction_factor_rejects_infeasible_single_shell():
    # R = 1, P = 0.625 cannot be achieved in one shell pass (temperature cross).
    with pytest.raises(ValueError):
        lmtd_correction_factor(100.0, 50.0, 20.0, 70.0)


@pytest.mark.parametrize("arr", ["counterflow", "parallel", "shell_and_tube"])
@pytest.mark.parametrize("ntu,cr", [(0.5, 0.3), (2.0, 0.7), (3.0, 1.0), (1.2, 0.0)])
def test_effectiveness_ntu_round_trip(arr, ntu, cr):
    eff = effectiveness(ntu, cr, arr)
    if cr == 0.0:
        # Capacity ratio zero: only the NTU -> effectiveness direction is defined here.
        assert eff == pytest.approx(1 - math.exp(-ntu))
        return
    if arr == "parallel" and eff >= 1 / (1 + cr):
        pytest.skip("parallel-flow effectiveness cannot reach the inverse's domain")
    assert ntu_from_effectiveness(eff, cr, arr) == pytest.approx(ntu, rel=1e-6)


def test_counterflow_effectiveness_matches_textbook():
    # NTU = 1, Cr = 0.5 -> eps = (1 - e^-0.5)/(1 - 0.5 e^-0.5)
    expected = (1 - math.exp(-0.5)) / (1 - 0.5 * math.exp(-0.5))
    assert effectiveness(1.0, 0.5, "counterflow") == pytest.approx(expected)


def test_rate_by_ntu_energy_balance_closes():
    r = rate_by_ntu(c_hot=2000.0, c_cold=3000.0, ua=4000.0, t_hot_in=150.0, t_cold_in=20.0)
    assert r.duty == pytest.approx(2000.0 * (150 - r.t_hot_out))
    assert r.duty == pytest.approx(3000.0 * (r.t_cold_out - 20))
    assert 0 < r.effectiveness < 1


# ---------------- hydraulics ----------------
def test_laminar_friction_factor():
    assert friction_factor(1000.0) == pytest.approx(0.064)


def test_smooth_turbulent_friction_factor_matches_colebrook():
    # Smooth pipe, Re = 1e5: Colebrook gives f ~ 0.0180
    assert friction_factor(1e5, 0.0) == pytest.approx(0.0180, abs=2e-4)


def test_pipe_pressure_drop_components_sum_to_total():
    res = pipe_pressure_drop(
        flow=0.01, diameter=0.05, length=100.0, density=1000.0, viscosity=1e-3,
        fittings={"elbow_90": 4, "gate_valve_open": 1}, elevation_change=5.0,
    )
    assert res.dp_total == pytest.approx(res.dp_friction + res.dp_fittings + res.dp_static)
    assert res.regime == "turbulent"


def test_diameter_for_pressure_drop_round_trip():
    target = 20_000.0
    d = diameter_for_pressure_drop(target, 0.01, 150.0, 1000.0, 1e-3)
    back = pipe_pressure_drop(0.01, d, 150.0, 1000.0, 1e-3).dp_total
    assert back == pytest.approx(target, rel=1e-6)


def test_unknown_fitting_raises():
    with pytest.raises(KeyError):
        pipe_pressure_drop(0.01, 0.05, 10, 1000, 1e-3, fittings={"unicorn": 1})


def test_pump_head_for_water():
    # 100 kPa on water: head = dp / (rho g) = 10.2 m
    duty = pump_duty(flow=0.01, dp=1e5, density=1000.0, efficiency=0.7)
    assert duty.head == pytest.approx(10.197, rel=1e-3)
    assert duty.shaft_power == pytest.approx(duty.hydraulic_power / 0.7)


# ---------------- flash ----------------
def test_rachford_rice_known_solution():
    # z = [0.5, 0.5], K = [2, 0.5]  ->  beta = 0.5
    assert rachford_rice([0.5, 0.5], [2.0, 0.5]) == pytest.approx(0.5)


def test_flash_mass_balance_and_sum_to_one():
    res = flash_tp([0.3, 0.7], [2.5, 0.6])
    assert res.x.sum() == pytest.approx(1.0)
    assert res.y.sum() == pytest.approx(1.0)
    z = np.array([0.3, 0.7])
    assert (res.vapor_fraction * res.y + (1 - res.vapor_fraction) * res.x) == pytest.approx(z)


def test_flash_single_phase_detection():
    assert flash_tp([0.5, 0.5], [0.1, 0.2]).phase == "liquid"
    assert flash_tp([0.5, 0.5], [5.0, 4.0]).phase == "vapor"


def test_bubble_point_is_consistent_with_flash():
    ants = [ANTOINE["benzene"], ANTOINE["toluene"]]
    x = [0.5, 0.5]
    t_bub = bubble_point_temperature(x, ants, p=1.01325)
    p_bub = bubble_point_pressure(x, ants, t_bub)
    assert p_bub == pytest.approx(1.01325, rel=1e-6)
    # Just at the bubble point, the liquid is saturated: vapour fraction ~ 0
    res = flash_pt_ideal(x, ants, p=p_bub, t=t_bub)
    assert res.vapor_fraction == pytest.approx(0.0, abs=1e-6)


def test_dew_point_temperature_above_bubble_point():
    ants = [ANTOINE["benzene"], ANTOINE["toluene"]]
    t_bub = bubble_point_temperature([0.5, 0.5], ants, p=1.01325)
    t_dew = dew_point_temperature([0.5, 0.5], ants, p=1.01325)
    assert t_dew > t_bub


def test_benzene_toluene_equimolar_bubble_point_is_physically_reasonable():
    ants = [ANTOINE["benzene"], ANTOINE["toluene"]]
    t_bub = bubble_point_temperature([0.5, 0.5], ants, p=1.01325)
    # Literature bubble point of equimolar benzene/toluene at 1 atm is about 92 C (365 K).
    assert 362.0 < t_bub < 368.0


# ---------------- distillation ----------------
def test_fenske_minimum_stages_known_value():
    # alpha = 2, xD = 0.99/0.01, xB = 0.01/0.99
    n = fenske_min_stages(0.99, 0.01, 0.01, 0.99, 2.0)
    assert n == pytest.approx(math.log(99 * 99) / math.log(2.0))


def test_underwood_theta_between_keys_and_satisfies_equation():
    alphas = [2.5, 1.0, 0.4]
    z = [0.3, 0.4, 0.3]
    q = 1.0
    theta = underwood_theta(alphas, z, q, alpha_lk=2.5, alpha_hk=1.0)
    assert 1.0 < theta < 2.5
    lhs = sum(a * zi / (a - theta) for a, zi in zip(alphas, z))
    assert lhs == pytest.approx(1 - q, abs=1e-8)


def test_underwood_min_reflux_positive():
    alphas = [2.5, 1.0, 0.4]
    theta = underwood_theta(alphas, [0.3, 0.4, 0.3], 1.0, 2.5, 1.0)
    rmin = underwood_min_reflux(alphas, [0.98, 0.02, 0.0], theta)
    assert rmin > 0


def test_gilliland_stage_count_decreases_with_reflux():
    n_min, r_min = 10.0, 1.0
    n_low = gilliland(n_min, 1.3, r_min)
    n_high = gilliland(n_min, 2.5, r_min)
    assert n_low > n_high > n_min


def test_fug_design_end_to_end():
    alphas = [2.5, 1.0, 0.4]
    z = [0.3, 0.4, 0.3]
    xd = [0.97, 0.03, 0.0]
    xb = [0.01, 0.05, 0.94]
    res = fug_design(alphas, z, xd, xb, lk=0, hk=1, q=1.0, reflux_factor=1.2, b_over_d=1.0)
    assert res.n_min < res.n_actual
    assert res.r == pytest.approx(1.2 * res.r_min)
    assert 0 < res.feed_stage_fraction < 1
