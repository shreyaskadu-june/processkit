// processkit browser calculations. Sources are listed in REFERENCES.md and on the website.
// Pure functions with no DOM access, so they can be tested with Node.
// Formulas match the Python package in src/processkit. SI units throughout.

export const G = 9.80665;

// ---------------------------------------------------------------------------
// Numerical helpers
// ---------------------------------------------------------------------------

/** Find a root of f in [lo, hi] by bisection. f must change sign across the bracket. */
export function bisect(f, lo, hi, { tol = 1e-12, maxIter = 200 } = {}) {
  let flo = f(lo);
  const fhi = f(hi);
  if (!Number.isFinite(flo) || !Number.isFinite(fhi) || Math.sign(flo) === Math.sign(fhi)) {
    throw new RangeError("No sign change across the search range, so no solution was found.");
  }
  for (let i = 0; i < maxIter; i++) {
    const mid = 0.5 * (lo + hi);
    const fmid = f(mid);
    if (fmid === 0 || (hi - lo) / 2 < tol) return mid;
    if (Math.sign(fmid) === Math.sign(flo)) {
      lo = mid;
      flo = fmid;
    } else {
      hi = mid;
    }
  }
  return 0.5 * (lo + hi);
}

function requirePositive(name, value) {
  if (!(Number.isFinite(value) && value > 0)) {
    throw new RangeError(`${name} must be a positive number.`);
  }
}

// ---------------------------------------------------------------------------
// Heat exchangers
// ---------------------------------------------------------------------------

export const ARRANGEMENTS = ["counterflow", "parallel", "shell_and_tube"];

export function lmtd(dt1, dt2) {
  if (!(dt1 > 0 && dt2 > 0)) {
    throw new RangeError(
      `Both terminal temperature differences must be positive (got ${dt1} and ${dt2}). ` +
        "Check for a temperature cross or an infeasible approach."
    );
  }
  if (Math.abs(dt1 - dt2) <= 1e-9 * Math.max(dt1, dt2)) return 0.5 * (dt1 + dt2);
  return (dt1 - dt2) / Math.log(dt1 / dt2);
}

/** LMTD correction factor F for one shell pass with an even number of tube passes. */
export function lmtdCorrectionFactor(thIn, thOut, tcIn, tcOut) {
  if (tcOut <= tcIn || thIn <= thOut) {
    throw new RangeError("The hot stream must cool and the cold stream must heat.");
  }
  const r = (thIn - thOut) / (tcOut - tcIn);
  const p = (tcOut - tcIn) / (thIn - tcIn);
  if (!(p > 0 && p < 1)) {
    throw new RangeError(`Thermal effectiveness P = ${p.toFixed(3)} is outside (0, 1), so the duty is infeasible.`);
  }
  const infeasible = "Infeasible for a single shell pass (temperature cross). Use more shells.";
  if (Math.abs(r - 1) < 1e-7) {
    const argNum = 2 - p * (2 - Math.SQRT2);
    const argDen = 2 - p * (2 + Math.SQRT2);
    if (argDen <= 0) throw new RangeError(infeasible);
    return ((Math.SQRT2 * p) / (1 - p)) / Math.log(argNum / argDen);
  }
  const s = Math.sqrt(r * r + 1);
  if (1 - r * p <= 0) throw new RangeError(infeasible);
  const numArg = 2 - p * (r + 1 - s);
  const denArg = 2 - p * (r + 1 + s);
  if (denArg <= 0) throw new RangeError(infeasible);
  return ((s / (r - 1)) * Math.log((1 - p) / (1 - r * p))) / Math.log(numArg / denArg);
}

/** Required area from duty, U and the four stream temperatures. */
export function sizeByLmtd({ duty, u, thIn, thOut, tcIn, tcOut, arrangement = "counterflow" }) {
  if (!ARRANGEMENTS.includes(arrangement)) throw new RangeError("Unknown flow arrangement.");
  requirePositive("Duty", duty);
  requirePositive("U", u);
  if (!(thIn > thOut && tcOut > tcIn)) {
    throw new RangeError("The hot stream must cool (inlet above outlet) and the cold stream must heat (outlet above inlet).");
  }
  const parallel = arrangement === "parallel";
  const dt1 = parallel ? thIn - tcIn : thIn - tcOut;
  const dt2 = parallel ? thOut - tcOut : thOut - tcIn;
  const lm = lmtd(dt1, dt2);
  const f = arrangement === "shell_and_tube" ? lmtdCorrectionFactor(thIn, thOut, tcIn, tcOut) : 1;
  return { area: duty / (u * f * lm), lmtd: lm, correctionFactor: f };
}

export function effectiveness(ntu, cr, arrangement = "counterflow") {
  if (ntu < 0 || cr < 0 || cr > 1) throw new RangeError("NTU must be ≥ 0 and Cr between 0 and 1.");
  if (cr === 0) return 1 - Math.exp(-ntu);
  if (arrangement === "counterflow") {
    if (Math.abs(cr - 1) < 1e-9) return ntu / (1 + ntu);
    const e = Math.exp(-ntu * (1 - cr));
    return (1 - e) / (1 - cr * e);
  }
  if (arrangement === "parallel") return (1 - Math.exp(-ntu * (1 + cr))) / (1 + cr);
  if (arrangement === "shell_and_tube") {
    const s = Math.sqrt(1 + cr * cr);
    const e = Math.exp(-ntu * s);
    return ntu > 0 ? 2 / (1 + cr + (s * (1 + e)) / (1 - e)) : 0;
  }
  throw new RangeError("Unknown flow arrangement.");
}

/** Rate an existing exchanger from UA and inlet temperatures. c values are m_dot × cp in W/K. */
export function rateByNtu({ cHot, cCold, ua, thIn, tcIn, arrangement = "counterflow" }) {
  requirePositive("Hot-side heat capacity rate", cHot);
  requirePositive("Cold-side heat capacity rate", cCold);
  const cMin = Math.min(cHot, cCold);
  const cMax = Math.max(cHot, cCold);
  const cr = cMin / cMax;
  const ntu = ua / cMin;
  const eff = effectiveness(ntu, cr, arrangement);
  const q = eff * cMin * (thIn - tcIn);
  return {
    duty: q,
    effectiveness: eff,
    ntu,
    thOut: thIn - q / cHot,
    tcOut: tcIn + q / cCold,
  };
}

// ---------------------------------------------------------------------------
// Hydraulics
// ---------------------------------------------------------------------------

export const FITTING_K = {
  elbow_90: 0.75,
  elbow_45: 0.35,
  tee_run: 0.4,
  tee_branch: 1.0,
  gate_valve_open: 0.17,
  globe_valve_open: 6.0,
  ball_valve_open: 0.05,
  check_valve_swing: 2.0,
  entrance_sharp: 0.5,
  entrance_rounded: 0.05,
  exit: 1.0,
};

function colebrook(re, relRough) {
  let f = 0.25 / Math.log10(relRough / 3.7 + 5.74 / re ** 0.9) ** 2;
  for (let i = 0; i < 100; i++) {
    const invSqrt = -2 * Math.log10(relRough / 3.7 + 2.51 / (re * Math.sqrt(f)));
    const fNew = 1 / invSqrt ** 2;
    if (Math.abs(fNew - f) < 1e-12) return fNew;
    f = fNew;
  }
  return f;
}

/** Darcy friction factor. Laminar below Re 2300, Colebrook-White above 4000, linear blend between. */
export function frictionFactor(re, relRough = 0) {
  if (!(re > 0)) throw new RangeError("Reynolds number must be positive.");
  if (re < 2300) return 64 / re;
  if (re >= 4000) return colebrook(re, relRough);
  const fLam = 64 / 2300;
  const fTurb = colebrook(4000, relRough);
  const w = (re - 2300) / (4000 - 2300);
  return fLam + w * (fTurb - fLam);
}

/**
 * Pressure drop through a pipe with fittings. Units: m, m³/s, kg/m³, Pa·s, Pa.
 * fittings is an object of FITTING_K names to counts, e.g. { elbow_90: 4 }.
 */
export function pipePressureDrop({
  flow,
  diameter,
  length,
  density,
  viscosity,
  roughness = 4.5e-5,
  fittings = {},
  kExtra = 0,
  elevationChange = 0,
}) {
  requirePositive("Flow rate", flow);
  requirePositive("Diameter", diameter);
  requirePositive("Length", length);
  requirePositive("Density", density);
  requirePositive("Viscosity", viscosity);
  const area = (Math.PI * diameter ** 2) / 4;
  const v = flow / area;
  const re = (density * v * diameter) / viscosity;
  const f = frictionFactor(re, roughness / diameter);
  const dyn = 0.5 * density * v ** 2;
  let kSum = kExtra;
  for (const [name, count] of Object.entries(fittings)) {
    if (!(name in FITTING_K)) throw new RangeError(`Unknown fitting: ${name}`);
    kSum += FITTING_K[name] * count;
  }
  const dpFriction = (f * length) / diameter * dyn;
  const dpFittings = kSum * dyn;
  const dpStatic = density * G * elevationChange;
  const regime = re < 2300 ? "laminar" : re >= 4000 ? "turbulent" : "transitional";
  return {
    velocity: v,
    reynolds: re,
    frictionFactor: f,
    regime,
    dpFriction,
    dpFittings,
    dpStatic,
    dpTotal: dpFriction + dpFittings + dpStatic,
  };
}

/** Smallest pipe inner diameter (m) giving the target total pressure drop (Pa). */
export function diameterForPressureDrop(targetDp, params) {
  const residual = (d) => pipePressureDrop({ ...params, diameter: d }).dpTotal - targetDp;
  return bisect(residual, 0.005, 5, { tol: 1e-9 });
}

export function pumpDuty({ flow, dp, density, efficiency = 0.7 }) {
  if (!(efficiency > 0 && efficiency <= 1)) throw new RangeError("Efficiency must be above 0 and at most 1.");
  const hydraulic = flow * dp;
  return {
    head: dp / (density * G),
    hydraulicPower: hydraulic,
    shaftPower: hydraulic / efficiency,
  };
}

// ---------------------------------------------------------------------------
// Flash (ideal Raoult's law; pressures in bar, temperatures in K)
// ---------------------------------------------------------------------------

export const ANTOINE = {
  benzene: { A: 4.01814, B: 1203.835, C: -53.226 },
  toluene: { A: 4.07827, B: 1343.943, C: -53.773 },
  water: { A: 5.40221, B: 1838.675, C: -31.737 },
};

export function psatBar(ant, t) {
  return 10 ** (ant.A - ant.B / (ant.C + t));
}

export function kValues(ants, t, p) {
  return ants.map((a) => psatBar(a, t) / p);
}

export function rachfordRice(z, k) {
  const f = (beta) => z.reduce((sum, zi, i) => sum + (zi * (k[i] - 1)) / (1 + beta * (k[i] - 1)), 0);
  if (f(0) <= 0) return 0; // all liquid
  if (f(1) >= 0) return 1; // all vapour
  return bisect(f, 0, 1);
}

export function flashTP(z, k) {
  const total = z.reduce((a, b) => a + b, 0);
  const zn = z.map((zi) => zi / total);
  const beta = rachfordRice(zn, k);
  let x = zn.map((zi, i) => zi / (1 + beta * (k[i] - 1)));
  let y = x.map((xi, i) => k[i] * xi);
  const sx = x.reduce((a, b) => a + b, 0);
  const sy = y.reduce((a, b) => a + b, 0);
  x = x.map((v) => v / sx);
  y = y.map((v) => v / sy);
  const phase = beta === 0 ? "liquid" : beta === 1 ? "vapour" : "two-phase";
  return { vaporFraction: beta, x, y, phase };
}

export function bubblePointTemperature(x, ants, p, [lo = 150, hi = 700] = []) {
  return bisect((t) => x.reduce((s, xi, i) => s + xi * psatBar(ants[i], t), 0) - p, lo, hi);
}

export function dewPointTemperature(y, ants, p, [lo = 150, hi = 700] = []) {
  return bisect((t) => 1 / y.reduce((s, yi, i) => s + yi / psatBar(ants[i], t), 0) - p, lo, hi);
}

// ---------------------------------------------------------------------------
// Shortcut distillation (Fenske, Underwood, Gilliland)
// ---------------------------------------------------------------------------

export function fenskeMinStages(xdLk, xdHk, xbLk, xbHk, alphaLkHk) {
  if (alphaLkHk <= 1) throw new RangeError("The light key must be more volatile than the heavy key (α > 1).");
  if (Math.min(xdLk, xdHk, xbLk, xbHk) <= 0) {
    throw new RangeError("Key-component mole fractions must be above zero. Use a small value such as 0.0001.");
  }
  return Math.log((xdLk / xdHk) * (xbHk / xbLk)) / Math.log(alphaLkHk);
}

export function underwoodTheta(alphas, z, q, alphaLk, alphaHk) {
  const f = (theta) => alphas.reduce((s, a, i) => s + (a * z[i]) / (a - theta), 0) - (1 - q);
  return bisect(f, alphaHk + 1e-9, alphaLk - 1e-9, { tol: 1e-12 });
}

export function underwoodMinReflux(alphas, xd, theta) {
  return alphas.reduce((s, a, i) => s + (a * xd[i]) / (a - theta), 0) - 1;
}

/** Actual stages from Eduljee's form of the Gilliland correlation. */
export function gilliland(nMin, r, rMin) {
  if (r <= rMin) throw new RangeError("The reflux ratio must exceed the minimum reflux ratio.");
  const x = (r - rMin) / (r + 1);
  const y = 1 - Math.exp(((1 + 54.4 * x) / (11 + 117.2 * x)) * ((x - 1) / Math.sqrt(x)));
  return (nMin + y) / (1 - y);
}

export function fugDesign({ alphas, zFeed, xd, xb, lk, hk, q = 1, reflux = 1.2 }) {
  const nMin = fenskeMinStages(xd[lk], xd[hk], xb[lk], xb[hk], alphas[lk] / alphas[hk]);
  const theta = underwoodTheta(alphas, zFeed, q, alphas[lk], alphas[hk]);
  const rMin = underwoodMinReflux(alphas, xd, theta);
  const r = reflux * rMin;
  const nActual = gilliland(nMin, r, rMin);
  return { nMin, theta, rMin, r, nActual };
}

// ---------------------------------------------------------------------------
// Economics
// ---------------------------------------------------------------------------

/** CEPCI annual averages. Verify against the published series before costed work. */
export const CEPCI = { 2018: 603.1, 2019: 607.5, 2020: 596.2, 2021: 708.0, 2022: 816.0, 2023: 797.9 };

export function escalate(cost, fromYear, toYear) {
  if (!(fromYear in CEPCI) || !(toYear in CEPCI)) {
    throw new RangeError("No CEPCI value for one of those years. Choose 2018 to 2023.");
  }
  return (cost * CEPCI[toYear]) / CEPCI[fromYear];
}

export function capexScale({ costRef, sizeRef, sizeNew, exponent = 0.6 }) {
  requirePositive("Reference size", sizeRef);
  requirePositive("New size", sizeNew);
  return costRef * (sizeNew / sizeRef) ** exponent;
}

export function npv(rate, cashflows) {
  return cashflows.reduce((s, cf, t) => s + cf / (1 + rate) ** t, 0);
}

export function irr(cashflows) {
  if (!(cashflows.some((c) => c < 0) && cashflows.some((c) => c > 0))) {
    throw new RangeError("IRR needs at least one negative and one positive cash flow.");
  }
  return bisect((r) => npv(r, cashflows), -0.99, 10, { tol: 1e-12 });
}

export function capitalRecoveryFactor(rate, years) {
  if (!(years > 0)) throw new RangeError("Lifetime must be at least one year.");
  if (rate === 0) return 1 / years;
  const g = (1 + rate) ** years;
  return (rate * g) / (g - 1);
}

/** Levelised cost per unit of annual output: (CAPEX × CRF + annual costs) / output. */
export function levelisedCost({ capex, annualOpex, annualOutput, rate, lifetimeYears, annualFuel = 0 }) {
  requirePositive("Annual output", annualOutput);
  const crf = capitalRecoveryFactor(rate, lifetimeYears);
  return (capex * crf + annualOpex + annualFuel) / annualOutput;
}
