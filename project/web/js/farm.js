// The Soil Health Card panel: place, soil values with the card's classes, sowing month.
import { api } from "./api.js";
import { MONTHS, SEASONS, seasonOf, number } from "./format.js";

// Class limits printed on the Soil Health Card (SHC Operational Guidelines 2015; N from ICAR), as in project/data.py
const BANDS = {
  N: [280, 560, ["Low", "Medium", "High"]],
  P: [28, 56, ["Low", "Medium", "High"]],
  K: [140, 280, ["Low", "Medium", "High"]],
  ph: [6.5, 8.2, ["Acidic", "Normal", "Alkaline"]],
};
const SOIL = Object.keys(BANDS);

let els;
let handlers;
let ready;
const districtsByState = new Map();

export function init(elements, callbacks) {
  els = elements;
  handlers = callbacks;

  els.month.append(...MONTHS.map((m, i) => new Option(m, i + 1)));
  els.month.value = String(new Date().getMonth() + 1);
  showSeason();

  els.state.addEventListener("change", () => { fillDistricts(); changed(); });
  els.district.addEventListener("change", changed);
  els.month.addEventListener("change", () => { showSeason(); changed(); });
  for (const key of SOIL) {
    els.soil[key].addEventListener("input", () => { setEstimated(key, false); showBand(key); hint(""); });
    showBand(key);
  }
  els.useTypical.addEventListener("click", useTypical);
  els.form.addEventListener("submit", submit);

  ready = api.districts()
    .then((list) => {
      for (const { state, district } of list) {
        if (!districtsByState.has(state)) districtsByState.set(state, []);
        districtsByState.get(state).push(district);
      }
      els.state.replaceChildren(new Option("Choose a state", ""), ...[...districtsByState.keys()].map((s) => new Option(s, s)));
      els.state.disabled = false;
    })
    .catch((err) => hint(`The district list didn't load: ${err.message}. Reload the page to try again.`, true));
  return ready;
}

function fillDistricts(selected = "") {
  const names = districtsByState.get(els.state.value) ?? [];
  els.district.replaceChildren(
    new Option(names.length ? "Choose a district" : "Choose a state first", ""),
    ...names.map((d) => new Option(d, d)));
  els.district.disabled = !names.length;
  els.district.value = names.includes(selected) ? selected : "";
}

function changed() {
  els.useTypical.disabled = !els.district.value;
  hint("");
  handlers.onChange?.(summary());
}

function showSeason() {
  const season = seasonOf(Number(els.month.value));
  els.season.textContent = `Sowing in the ${season} season (${SEASONS[season]}).`;
}

function showBand(key) {
  const band = els.cells[key].querySelector(".band");
  const raw = els.soil[key].value;
  if (raw === "") {
    band.removeAttribute("data-level");
    band.replaceChildren();
    return;
  }
  const [low, high, names] = BANDS[key];
  const value = Number(raw);
  const level = value < low ? 0 : value <= high ? 1 : 2;
  band.dataset.level = String(level);
  const scale = document.createElement("span");
  scale.className = "band-scale";
  scale.setAttribute("aria-hidden", "true");
  scale.append(document.createElement("i"), document.createElement("i"), document.createElement("i"));
  const text = document.createElement("span");
  text.className = "band-text";
  text.textContent = names[level];
  band.replaceChildren(scale, text);
}

function setEstimated(key, on) {
  els.cells[key].toggleAttribute("data-estimated", on);
  if (!SOIL.some((k) => els.cells[k].hasAttribute("data-estimated"))) els.source.hidden = true;
}

function hint(text, isError = false) {
  els.hint.textContent = text;
  els.hint.classList.toggle("is-error", isError);
}

async function useTypical() {
  const label = els.useTypical.textContent;
  els.useTypical.disabled = true;
  els.useTypical.textContent = "Looking up typical soil…";
  try {
    applySoil(await api.soil(els.district.value, els.state.value));
  } catch (err) {
    hint(`Typical soil didn't load: ${err.message}`, true);
  } finally {
    els.useTypical.textContent = label;
    els.useTypical.disabled = !els.district.value;
  }
}

// Typical soil for the area (from /soil or the advisor's get_area_soil): filled in and marked as an estimate
export function applySoil(soil) {
  for (const key of SOIL) {
    els.soil[key].value = String(soil[key]);
    setEstimated(key, true);
    showBand(key);
  }
  els.source.textContent = `Estimated: ${soil.source}. Replace them with your card's values if you have one.`;
  els.source.hidden = false;
  hint("");
}

export function values() {
  const read = (key) => (els.soil[key].value === "" ? null : Number(els.soil[key].value));
  return {
    N: read("N"), P: read("P"), K: read("K"), ph: read("ph"),
    district: els.district.value || null, state: els.state.value || null, month: Number(els.month.value),
  };
}

export function complete() {
  const v = values();
  return Boolean(v.district) && SOIL.every((k) => v[k] != null);
}

export function summary() {
  const v = values();
  return v.district ? `${v.district}, ${MONTHS[v.month - 1]}` : "Not set";
}

function submit(event) {
  event.preventDefault();
  const v = values();
  if (!v.district) {
    hint("Choose your state and district.", true);
    (els.state.value ? els.district : els.state).focus();
    return;
  }
  const missing = SOIL.find((k) => v[k] == null);
  if (missing) {
    hint("Enter all four values from your soil card, or use typical soil for your district.", true);
    els.soil[missing].focus();
    return;
  }
  if (v.ph < 3 || v.ph > 10 || ["N", "P", "K"].some((k) => v[k] < 0)) {
    hint("Check the values: pH is between 3 and 10, and N, P and K can't be negative.", true);
    return;
  }
  const soil = `N ${number(v.N)}, P ${number(v.P, 1)}, K ${number(v.K)} kg/ha and pH ${number(v.ph, 2)}`;
  const estimated = SOIL.some((k) => els.cells[k].hasAttribute("data-estimated"));
  handlers.onAsk(
    `My farm is in ${v.district}, ${v.state}. ` +
    (estimated ? `I don't have a soil card, so use typical soil for my district: ${soil}. ` : `My soil card says ${soil}. `) +
    `I will sow in ${MONTHS[v.month - 1]}. What should I grow?`);
}

// Fill the card from what the advisor saved (profile farm, or a tool call's farm values)
export async function sync(farm) {
  if (!farm || !Object.keys(farm).length) return;
  await ready;
  const state = farm.state && districtsByState.has(farm.state)
    ? farm.state
    : [...districtsByState].find(([, names]) => names.includes(farm.district))?.[0];
  if (state) {
    els.state.value = state;
    fillDistricts(farm.district);
  }
  for (const key of SOIL) {
    if (farm[key] != null && String(farm[key]) !== els.soil[key].value) {
      els.soil[key].value = String(farm[key]);
      setEstimated(key, false);
      showBand(key);
    }
  }
  if (farm.month) {
    els.month.value = String(farm.month);
    showSeason();
  }
  changed();
}
