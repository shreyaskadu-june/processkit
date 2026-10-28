import {
  test } from "node:test";
import assert from "node:assert/strict";
import {
  gilliland,
  lmtdCorrectionFactor,
  psatBar,
  CEPCI,
  escalate,
  ANTOINE,
  bisect,
  bubblePointTemperature,
  capexScale,
  capitalRecoveryFactor,
  diameterForPressureDrop,
  effectiveness,
  flashTP,
  frictionFactor,
  fugDesign,
  irr,
  kValues,
  levelisedCost,
  lmtd,
  npv,
  pipePressureDrop,
  rachfordRice,
  rateByNtu,
  sizeByLmtd,
  underwoodTheta,
} from "../../docs/js/calc.js";

const close = (actual, expected, tol = 1e-6) =>
  assert.ok(Math.abs(actual - expected) <= tol, `expected ${expected}, got ${actual}`);

test("bisect finds a simple root", () => {
  close(bisect((x) => x * x - 2, 0, 2), Math.SQRT2, 1e-9);
});

test("LMTD matches the textbook value and handles equal differences", () => {
  close(lmtd(20, 10), 10 / Math.log(2), 1e-9);
  close(lmtd(15, 15), 15, 1e-9);
  assert.throws(() => lmtd(10, -2), RangeError);
});

test("counterflow area equals Q / (U * LMTD)", () => {
  const r = sizeByLmtd({ duty: 1e6, u: 500, thIn: 150, thOut: 90, tcIn: 30, tcOut: 80 });
  const expectedLmtd = (70 - 60) / Math.log(70 / 60);
  close(r.lmtd, expectedLmtd, 1e-9);
  close(r.area, 1e6 / (500 * expectedLmtd), 1e-9);
});

test("sizing rejects streams that do not cool and heat in the right direction", () => {
  assert.throws(() => sizeByLmtd({ duty: 1e6, u: 500, thIn: 150, thOut: 200, tcIn: 30, tcOut: 80 }), RangeError);
  assert.throws(() => sizeByLmtd({ duty: 1e6, u: 500, thIn: 150, thOut: 90, tcIn: 80, tcOut: 30 }), RangeError);
});

test("shell-and-tube correction factor is between 0 and 1", () => {
  const r = sizeByLmtd({ duty: 1e6, u: 500, thIn: 150, thOut: 90, tcIn: 30, tcOut: 80, arrangement: "shell_and_tube" });
  assert.ok(r.correctionFactor > 0 && r.correctionFactor < 1);
});

test("single shell rejects an infeasible temperature cross", () => {
  assert.throws(() => sizeByLmtd({ duty: 1e6, u: 500, thIn: 100, thOut: 50, tcIn: 20, tcOut: 70, arrangement: "shell_and_tube" }), RangeError);
});

test("effectiveness-NTU counterflow formula and rating energy balance", () => {
  const expected = (1 - Math.exp(-0.5)) / (1 - 0.5 * Math.exp(-0.5));
  close(effectiveness(1, 0.5, "counterflow"), expected, 1e-12);
  const r = rateByNtu({ cHot: 2000, cCold: 3000, ua: 4000, thIn: 150, tcIn: 20 });
  close(r.duty, 2000 * (150 - r.thOut), 1e-6);
  close(r.duty, 3000 * (r.tcOut - 20), 1e-6);
});

test("friction factor: laminar and smooth-pipe turbulent values", () => {
  close(frictionFactor(1000), 0.064, 1e-12);
  close(frictionFactor(1e5, 0), 0.018, 2e-4);
});

test("pipe pressure drop components add up and the diameter solver round-trips", () => {
  const params = { flow: 0.01, length: 150, density: 1000, viscosity: 1e-3 };
  const res = pipePressureDrop({ ...params, diameter: 0.05, fittings: { elbow_90: 4 }, elevationChange: 5 });
  close(res.dpTotal, res.dpFriction + res.dpFittings + res.dpStatic, 1e-9);
  const d = diameterForPressureDrop(20_000, params);
  close(pipePressureDrop({ ...params, diameter: d }).dpTotal, 20_000, 1e-3);
});

test("Rachford-Rice known solution and single-phase detection", () => {
  close(rachfordRice([0.5, 0.5], [2, 0.5]), 0.5, 1e-9);
  assert.equal(flashTP([0.5, 0.5], [0.1, 0.2]).phase, "liquid");
  assert.equal(flashTP([0.5, 0.5], [5, 4]).phase, "vapour");
});

test("benzene-toluene bubble point is about 92 °C at 1 atm and flash is consistent", () => {
  const ants = [ANTOINE.benzene, ANTOINE.toluene];
  const tBub = bubblePointTemperature([0.5, 0.5], ants, 1.01325);
  assert.ok(tBub > 362 && tBub < 368, `bubble point ${tBub} K`);
  const res = flashTP([0.5, 0.5], kValues(ants, tBub, 1.01325));
  close(res.vaporFraction, 0, 1e-9);
});

test("Underwood theta satisfies its equation and FUG gives a sensible design", () => {
  const alphas = [2.5, 1.0, 0.4];
  const z = [0.3, 0.4, 0.3];
  const theta = underwoodTheta(alphas, z, 1, 2.5, 1);
  assert.ok(theta > 1 && theta < 2.5);
  close(alphas.reduce((s, a, i) => s + (a * z[i]) / (a - theta), 0), 0, 1e-8);
  const d = fugDesign({ alphas, zFeed: z, xd: [0.97, 0.03, 0], xb: [0.01, 0.05, 0.94], lk: 0, hk: 1, q: 1, reflux: 1.2 });
  assert.ok(d.nMin < d.nActual);
  close(d.r, 1.2 * d.rMin, 1e-9);
});

test("capex scaling follows the power law and CEPCI escalation", () => {
  close(capexScale({ costRef: 100, sizeRef: 1, sizeNew: 2 }), 100 * 2 ** 0.6, 1e-9);
  close(escalate(100, 2019, 2021), (100 * 708) / 607.5, 1e-9);
});

test("NPV and IRR agree on a simple project", () => {
  const cfs = [-100, 60, 60];
  close(irr(cfs), 0.130662, 1e-5);
  close(npv(irr(cfs), cfs), 0, 1e-7);
  assert.throws(() => irr([10, 20]), RangeError);
});

test("capital recovery factor and levelised cost", () => {
  close(capitalRecoveryFactor(0.1, 10), 0.162745, 1e-5);
  close(capitalRecoveryFactor(0, 10), 0.1, 1e-12);
  close(
    levelisedCost({ capex: 1_000_000, annualOpex: 20_000, annualOutput: 50_000, rate: 0, lifetimeYears: 20 }),
    (1_000_000 / 20 + 20_000) / 50_000,
    1e-12
  );
});

// ---- Formula checks: independent formulation, limits and published constants ----
function altCorrectionFactor(p, r) {
  const s = Math.sqrt(r * r + 1);
  const tb = 2 / p - 1 - r;
  const tc = (s / (r - 1)) * Math.log10((1 - p) / (1 - p * r));
  const td = (tb + s) / (tb - s);
  return tc / Math.log10(td);
}
function tempsFor(p, r, T1 = 100, t1 = 20) {
  const t2 = t1 + p * (T1 - t1);
  const T2 = T1 - r * (t2 - t1);
  return { thIn: T1, thOut: T2, tcIn: t1, tcOut: t2 };
}

test("LMTD correction factor matches the independent Bowman formulation", () => {
  for (const [p, r] of [[0.1, 0.5], [0.3, 0.8], [0.49, 0.92], [0.2, 1.5], [0.2, 2.5]]) {
    const t = tempsFor(p, r);
    close(lmtdCorrectionFactor(t.thIn, t.thOut, t.tcIn, t.tcOut), altCorrectionFactor(p, r), 1e-9);
  }
});

test("correction factor tends to 1 as P tends to 0", () => {
  const t = tempsFor(0.001, 0.5);
  close(lmtdCorrectionFactor(t.thIn, t.thOut, t.tcIn, t.tcOut), 1, 1e-3);
});

test("Gilliland limits: minimum stages at high reflux, divergence near minimum reflux", () => {
  close(gilliland(10, 1000, 1), 10, 0.01);
  assert.ok(gilliland(10, 1.001, 1) > 500);
});

test("Antoine constants reproduce normal boiling points of benzene and toluene", () => {
  close(psatBar(ANTOINE.benzene, 353.25), 1.01325, 0.005);
  close(psatBar(ANTOINE.toluene, 383.75), 1.01325, 0.005);
});

test("CEPCI 2023 and 2022 values and the escalation ratio", () => {
  close(CEPCI[2023], 797.9, 1e-9);
  close(CEPCI[2022], 816.0, 1e-9);
  close(escalate(100, 2022, 2023), (100 * 797.9) / 816.0, 1e-9);
});

test("capital recovery factor reference value (10%, 10 years = 0.16275)", () => {
  close(capitalRecoveryFactor(0.1, 10), 0.16275, 1e-5);
});
