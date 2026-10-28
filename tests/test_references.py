"""Formula checks: each test verifies a method against an independent formulation,
a known limit, or a published constant. See REFERENCES.md for the sources."""

import math

import pytest

from processkit.economics import capital_recovery_factor, escalate, irr, npv
from processkit.economics.capex import CEPCI
from processkit.unitops import FITTING_K, lmtd_correction_factor
from processkit.unitops.distillation import (
    fenske_split,
    gilliland,
    kirkbride,
    underwood_min_reflux,
    underwood_theta,
)
from processkit.unitops.flash import ANTOINE, psat_bar


# ---------- LMTD correction factor (Bowman, Mueller and Nagle) ----------
def _temps_for(p, r, T1=100.0, t1=20.0):
    """Build inlet and outlet temperatures that give exactly this P and R."""
    t2 = t1 + p * (T1 - t1)
    T2 = T1 - r * (t2 - t1)
    return T1, T2, t1, t2


def _alt_correction_factor(p, r):
    """Independent formulation: F = [tc / log10(td)] with tb, ta and td as in the Bowman chart method."""
    s = math.sqrt(r * r + 1)
    tb = 2 / p - 1 - r
    tc = s / (r - 1) * math.log10((1 - p) / (1 - p * r))
    td = (tb + s) / (tb - s)
    return tc / math.log10(td)


@pytest.mark.parametrize("p,r", [(0.1, 0.5), (0.3, 0.8), (0.49, 0.92), (0.2, 1.5), (0.2, 2.5)])
def test_correction_factor_matches_independent_formulation(p, r):
    assert lmtd_correction_factor(*_temps_for(p, r)) == pytest.approx(_alt_correction_factor(p, r), rel=1e-9)


def test_correction_factor_tends_to_one_as_p_tends_to_zero():
    assert lmtd_correction_factor(*_temps_for(0.001, 0.5)) == pytest.approx(1.0, abs=1e-3)


def test_correction_factor_r_equals_one_branch_matches_general_formula():
    # Values either side of R = 1 should agree closely.
    f_exact = lmtd_correction_factor(*_temps_for(0.25, 1.0))
    f_near = lmtd_correction_factor(*_temps_for(0.25, 1.0 + 1e-6))
    assert f_exact == pytest.approx(f_near, rel=1e-5)


# ---------- Gilliland (Eduljee form) ----------
def test_gilliland_tends_to_minimum_stages_at_high_reflux():
    assert gilliland(10.0, 1000.0, 1.0) == pytest.approx(10.0, rel=0.01)


def test_gilliland_diverges_as_reflux_approaches_minimum():
    assert gilliland(10.0, 1.001, 1.0) > 500


# ---------- Underwood ----------
def test_underwood_theta_lies_between_keys_and_satisfies_first_equation():
    alphas = [2.5, 1.0, 0.4]
    z = [0.3, 0.4, 0.3]
    theta = underwood_theta(alphas, z, q=0.5, alpha_lk=2.5, alpha_hk=1.0)
    assert 1.0 < theta < 2.5
    lhs = sum(a * zi / (a - theta) for a, zi in zip(alphas, z))
    assert lhs == pytest.approx(1 - 0.5, abs=1e-8)


def test_underwood_min_reflux_matches_second_equation():
    alphas = [2.5, 1.0, 0.4]
    theta = underwood_theta(alphas, [0.3, 0.4, 0.3], 1.0, 2.5, 1.0)
    xd = [0.97, 0.03, 0.0]
    assert underwood_min_reflux(alphas, xd, theta) == pytest.approx(
        sum(a * x / (a - theta) for a, x in zip(alphas, xd)) - 1.0
    )


# ---------- Fenske and Kirkbride ----------
def test_fenske_split_is_consistent_with_alpha_power_law():
    split = fenske_split(alpha_lk_hk=2.0, n_stages=10, bottoms_ratio=0.01)
    assert split.distillate_ratio == pytest.approx(2.0**10 * 0.01)


def test_kirkbride_ratio_is_one_when_feed_is_balanced():
    # If the bracketed term equals 1, log10(Nr/Ns) = 0, so Nr/Ns = 1.
    # Choose B/D so that (B/D) * (zHF/zLF) * (xLB/xHD)^2 = 1.
    z_hk, z_lk, xb_lk, xd_hk = 0.4, 0.3, 0.2, 0.2
    b_over_d = 1.0 / ((z_hk / z_lk) * (xb_lk / xd_hk) ** 2)
    assert kirkbride(z_hk, z_lk, xb_lk, xd_hk, b_over_d) == pytest.approx(1.0)


# ---------- Antoine constants (NIST) ----------
@pytest.mark.parametrize(
    "name,t_k,p_bar",
    [("benzene", 353.25, 1.01325), ("toluene", 383.75, 1.01325)],
)
def test_antoine_reproduces_normal_boiling_points(name, t_k, p_bar):
    # Normal boiling points: benzene 80.1 °C, toluene 110.6 °C.
    assert psat_bar(ANTOINE[name], t_k) == pytest.approx(p_bar, abs=0.005)


# ---------- Fitting K values (Crane TP-410) ----------
@pytest.mark.parametrize(
    "name,expected",
    [("elbow_90", 0.75), ("elbow_45", 0.35), ("tee_run", 0.4), ("tee_branch", 1.0),
     ("gate_valve_open", 0.17), ("globe_valve_open", 6.0), ("check_valve_swing", 2.0)],
)
def test_fitting_k_values_match_crane_table(name, expected):
    assert FITTING_K[name] == expected


# ---------- CEPCI and economics ----------
def test_cepci_2023_and_2022_values():
    assert CEPCI[2023] == pytest.approx(797.9)
    assert CEPCI[2022] == pytest.approx(816.0)
    assert escalate(100.0, 2022, 2023) == pytest.approx(100 * 797.9 / 816.0)


def test_capital_recovery_factor_standard_value():
    # Standard engineering economics table: CRF(10%, 10 years) = 0.16275
    assert capital_recovery_factor(0.10, 10) == pytest.approx(0.16275, abs=1e-5)


def test_npv_and_irr_reference_case():
    cfs = [-100.0, 60.0, 60.0]
    assert irr(cfs) == pytest.approx(0.130662, abs=1e-5)
    assert npv(0.10, cfs) == pytest.approx(-100 + 60 / 1.1 + 60 / 1.21)
