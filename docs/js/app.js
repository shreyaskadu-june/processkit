// Wires the calculator forms on index.html to the calculations in calc.js.
import {
  ANTOINE,
  bubblePointTemperature,
  capexScale,
  dewPointTemperature,
  diameterForPressureDrop,
  escalate,
  flashTP,
  fugDesign,
  kValues,
  levelisedCost,
  pipePressureDrop,
  pumpDuty,
  sizeByLmtd,
  capitalRecoveryFactor,
} from "./calc.js";

const K_OFFSET = 273.15;

// ---------------------------------------------------------------------------
// Form helpers
// ---------------------------------------------------------------------------

/** Read a number from a named form field. Throws a readable error if missing or invalid. */
function num(form, name, label) {
  const raw = form.elements.namedItem(name)?.value?.trim() ?? "";
  if (raw === "") throw new RangeError(`Please enter ${label}.`);
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new RangeError(`${label} must be a number.`);
  return value;
}

function fmt(value, digits = 4) {
  if (!Number.isFinite(value)) return "not defined";
  if (value === 0) return "0";
  return value.toLocaleString("en-GB", { maximumSignificantDigits: digits });
}

/** Build a definition list of [label, value] pairs. */
function resultList(rows) {
  const dl = document.createElement("dl");
  dl.className = "result-list";
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    dl.append(dt, dd);
  }
  return dl;
}

function showResult(form, rows, heading) {
  const out = form.querySelector("output.result");
  const h = document.createElement("h3");
  h.textContent = heading;
  out.replaceChildren(h, resultList(rows));
  const err = form.querySelector(".error");
  err.hidden = true;
  err.textContent = "";
}

function showError(form, message) {
  const out = form.querySelector("output.result");
  out.replaceChildren();
  const err = form.querySelector(".error");
  err.textContent = message;
  err.hidden = false;
}

function sumCheck(values, label) {
  const total = values.reduce((a, b) => a + b, 0);
  if (Math.abs(total - 1) > 0.01) {
    throw new RangeError(`${label} must sum to 1. They currently sum to ${fmt(total, 4)}.`);
  }
}

// ---------------------------------------------------------------------------
// Calculators
// ---------------------------------------------------------------------------

const calculators = {
  "heat-exchanger"(form) {
    const duty = num(form, "duty", "a heat duty") * 1000; // kW to W
    const u = num(form, "u", "the overall U value");
    const thIn = num(form, "thIn", "the hot stream inlet temperature");
    const thOut = num(form, "thOut", "the hot stream outlet temperature");
    const tcIn = num(form, "tcIn", "the cold stream inlet temperature");
    const tcOut = num(form, "tcOut", "the cold stream outlet temperature");
    const arrangement = form.elements.namedItem("arrangement").value;
    const r = sizeByLmtd({ duty, u, thIn, thOut, tcIn, tcOut, arrangement });
    return [
      ["Required area", `${fmt(r.area)} m²`],
      ["Log-mean temperature difference", `${fmt(r.lmtd)} K`],
      ["Correction factor F", fmt(r.correctionFactor)],
      ["Duty", `${fmt(duty / 1000)} kW`],
    ];
  },

  pipe(form) {
    const flow = num(form, "flowM3h", "the volumetric flow") / 3600; // m³/h to m³/s
    const diameter = num(form, "diameterMm", "the inner diameter") / 1000;
    const length = num(form, "length", "the pipe length");
    const density = num(form, "density", "the fluid density");
    const viscosity = num(form, "viscosityMpas", "the viscosity") / 1000; // mPa·s to Pa·s
    const roughness = num(form, "roughnessUm", "the pipe roughness") / 1e6; // µm to m
    const elbows = num(form, "elbows", "the number of elbows");
    const gates = num(form, "gateValves", "the number of gate valves");
    const elevation = num(form, "elevation", "the elevation gain");
    const efficiency = num(form, "efficiency", "the pump efficiency") / 100;
    if (efficiency <= 0 || efficiency > 1) throw new RangeError("Pump efficiency must be above 0 and at most 100.");

    const p = pipePressureDrop({
      flow,
      diameter,
      length,
      density,
      viscosity,
      roughness,
      fittings: { elbow_90: elbows, gate_valve_open: gates },
      elevationChange: elevation,
    });
    const pump = pumpDuty({ flow, dp: p.dpTotal, density, efficiency });
    return [
      ["Velocity", `${fmt(p.velocity)} m/s`],
      ["Reynolds number", fmt(p.reynolds, 3)],
      ["Flow regime", p.regime],
      ["Friction factor", fmt(p.frictionFactor)],
      ["Friction loss", `${fmt(p.dpFriction / 1000)} kPa`],
      ["Fitting loss", `${fmt(p.dpFittings / 1000)} kPa`],
      ["Static head", `${fmt(p.dpStatic / 1000)} kPa`],
      ["Total pressure drop", `${fmt(p.dpTotal / 1000)} kPa`],
      ["Pump head", `${fmt(pump.head)} m of fluid`],
      ["Shaft power", `${fmt(pump.shaftPower / 1000)} kW`],
      ["Smallest diameter for a 50 kPa drop (same flow)", minDiameterText({ flow, length, density, viscosity, roughness, elbows, gates, elevation })],
    ];
  },

  flash(form) {
    const p = num(form, "p", "the pressure");
    const tC = num(form, "tC", "the temperature");
    const zB = num(form, "z", "the benzene mole fraction");
    if (zB < 0 || zB > 1) throw new RangeError("The benzene mole fraction must be between 0 and 1.");
    const ants = [ANTOINE.benzene, ANTOINE.toluene];
    const z = [zB, 1 - zB];
    const t = tC + K_OFFSET;
    const res = flashTP(z, kValues(ants, t, p));
    const tBubble = bubblePointTemperature(z, ants, p);
    const tDew = dewPointTemperature(z, ants, p);
    return [
      ["Phase", res.phase],
      ["Vapour fraction", fmt(res.vaporFraction)],
      ["Liquid benzene mole fraction", fmt(res.x[0])],
      ["Vapour benzene mole fraction", fmt(res.y[0])],
      ["Bubble point of this feed at this pressure", `${fmt(tBubble - K_OFFSET)} °C`],
      ["Dew point of this feed at this pressure", `${fmt(tDew - K_OFFSET)} °C`],
    ];
  },

  distillation(form) {
    const alphas = [num(form, "a1", "α for component 1"), num(form, "a2", "α for component 2"), num(form, "a3", "α for component 3")];
    const zFeed = [num(form, "z1", "the feed fraction of component 1"), num(form, "z2", "the feed fraction of component 2"), num(form, "z3", "the feed fraction of component 3")];
    const xd = [num(form, "d1", "the distillate fraction of component 1"), num(form, "d2", "the distillate fraction of component 2"), num(form, "d3", "the distillate fraction of component 3")];
    const xb = [num(form, "b1", "the bottoms fraction of component 1"), num(form, "b2", "the bottoms fraction of component 2"), num(form, "b3", "the bottoms fraction of component 3")];
    const q = num(form, "q", "the feed condition q");
    const reflux = num(form, "reflux", "the reflux multiple");
    if (reflux <= 1) throw new RangeError("The reflux multiple must be greater than 1, since operating reflux must exceed the minimum.");
    if (alphas[0] <= alphas[1]) throw new RangeError("Component 1 (light key) must be more volatile than component 2 (heavy key), so α₁ must exceed α₂.");
    sumCheck(zFeed, "Feed fractions");
    sumCheck(xd, "Distillate fractions");
    sumCheck(xb, "Bottoms fractions");
    const d = fugDesign({ alphas, zFeed, xd, xb, lk: 0, hk: 1, q, reflux });
    return [
      ["Minimum stages (Fenske)", fmt(d.nMin)],
      ["Underwood theta", fmt(d.theta)],
      ["Minimum reflux ratio", fmt(d.rMin)],
      ["Operating reflux ratio", fmt(d.r)],
      ["Actual theoretical stages (including reboiler)", fmt(d.nActual)],
    ];
  },

  capex(form) {
    const costRef = num(form, "costRef", "the reference cost");
    const sizeRef = num(form, "sizeRef", "the reference size");
    const sizeNew = num(form, "sizeNew", "the new size");
    const exponent = num(form, "exponent", "the scaling exponent");
    const yearRef = num(form, "yearRef", "the reference year");
    const yearNew = num(form, "yearNew", "the target year");
    const scaled = capexScale({ costRef, sizeRef, sizeNew, exponent });
    const escalated = escalate(scaled, yearRef, yearNew);
    return [
      ["Scaled cost (reference year money)", fmt(scaled, 6)],
      [`Cost in ${yearNew} money`, fmt(escalated, 6)],
    ];
  },

  lcoe(form) {
    const capex = num(form, "capex", "the capital cost");
    const opex = num(form, "opex", "the annual operating cost");
    const fuel = num(form, "fuel", "the annual fuel or electricity cost");
    const output = num(form, "output", "the annual output");
    const rate = num(form, "rate", "the discount rate") / 100;
    const life = num(form, "life", "the lifetime");
    if (life < 1 || !Number.isInteger(life)) throw new RangeError("Lifetime must be a whole number of years, at least 1.");
    const value = levelisedCost({ capex, annualOpex: opex, annualOutput: output, rate, lifetimeYears: life, annualFuel: fuel });
    return [
      ["Levelised cost", `${fmt(value)} per unit of annual output`],
      ["Capital recovery factor", fmt(capitalRecoveryFactor(rate, life))],
    ];
  },
};

/** Smallest diameter for a 50 kPa drop, used as a design aid in the pipe calculator. */
function minDiameterText({ flow, length, density, viscosity, roughness, elbows, gates, elevation }) {
  try {
    const d = diameterForPressureDrop(50_000, {
      flow,
      length,
      density,
      viscosity,
      roughness,
      fittings: { elbow_90: elbows, gate_valve_open: gates },
      elevationChange: elevation,
    });
    return `${fmt(d * 1000)} mm`;
  } catch {
    return "not reachable between 5 mm and 5 m";
  }
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

const HEADINGS = {
  "heat-exchanger": "Result: heat exchanger",
  pipe: "Result: pipe and pump",
  flash: "Result: flash",
  distillation: "Result: distillation column",
  capex: "Result: scaled cost",
  lcoe: "Result: levelised cost",
};

for (const form of document.querySelectorAll("form.calc")) {
  const name = form.dataset.calc;
  const calc = calculators[name];
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      const rows = calc(form);
      showResult(form, rows, HEADINGS[name]);
    } catch (err) {
      showError(form, err instanceof RangeError ? err.message : "Something went wrong. Check the values and try again.");
    }
  });
}
