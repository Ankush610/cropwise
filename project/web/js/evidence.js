// Cards for the tool results behind a reply, so the farmer can see where each number came from.
import { api } from "./api.js";
import { h, s } from "./dom.js";
import { cropName, featureValue, money, number, pct, priceSource, YIELD_SOURCE } from "./format.js";

export const TOOL_LABELS = {
  recommend_crops: "crop ranking", check_crop: "crop check", get_weather: "weather data",
  get_price_forecast: "price forecast", get_area_soil: "district soil data",
};

// ctx: { useSoil(result) } for the "put these on my soil card" action
export function evidence(call, ctx) {
  const r = call.result;
  if (!r || r.error) return null; // the advisor fixes the call or asks the farmer; nothing to show
  if (call.tool === "recommend_crops") return cropList(r, call.farm);
  if (call.tool === "check_crop") return cropCheck(r, call.farm);
  if (call.tool === "get_weather") return weather(r);
  if (call.tool === "get_price_forecast") return priceForecast(r);
  if (call.tool === "get_area_soil") return areaSoil(r, ctx);
  return null;
}

const head = (title, text) => h("header", { class: "ev-head" }, h("h3", {}, title), text && h("p", {}, text));

export function cropList(r, farm) {
  return h("section", { class: "ev", "aria-label": `Best crops for ${r.district}` },
    head(`Best crops for ${r.district}, ${r.season} season`,
      "Ranked by how well each crop fits your soil and weather. Close calls go to the crop that earns more."),
    h("ol", { class: "crops" }, r.crops.map((c, i) => cropRow(c, i + 1, farm))),
    r.warning && h("p", { class: "ev-note" }, r.warning),
    r.note && h("p", { class: "ev-note" }, r.note));
}

function cropCheck(r, farm) {
  const standing = r.offered_this_season
    ? `Ranks ${r.rank} of ${r.out_of} crops for the ${r.season} season on your farm.`
    : `Few districts grow it in the ${r.season} season, so it isn't offered then.`;
  return h("section", { class: "ev" },
    head(`${cropName(r.crop)} on your farm`, standing),
    h("ul", { class: "crops" }, cropRow(r, r.rank ?? "–", farm)),
    h("p", { class: "ev-note" }, r.reason));
}

function cropRow(c, rank, farm) {
  const hasMoney = c.net_rs_acre != null;
  return h("li", { class: "crop" },
    h("span", { class: "crop-rank", "aria-hidden": "true" }, String(rank)),
    h("div", { class: "crop-main" },
      h("h4", { class: "crop-name" }, cropName(c.crop)),
      h("div", { class: "suit" },
        h("span", { class: "suit-label" }, `Suitability ${pct(c.suitability)}`),
        h("span", { class: "suit-track", "aria-hidden": "true" },
          h("span", { class: "suit-fill", style: `width:${Math.max(2, c.suitability * 100).toFixed(1)}%` }))),
      h("p", { class: "crop-facts" }, facts(c))),
    h("div", { class: `crop-money${hasMoney && c.net_rs_acre < 0 ? " is-loss" : ""}` },
      h("strong", {}, hasMoney ? money(c.net_rs_acre) : "–"),
      h("span", {}, hasMoney ? "net per acre" : "no price data"),
      hasMoney && h("span", { class: "crop-month" },
        `≈ ${money(c.net_rs_acre_month)} a month · ${c.grow_months ? `${c.grow_months}-month crop` : "yearly crop"}`)),
    whyToggle(c.crop, farm));
}

function facts(c) {
  const parts = [];
  if (c.yield_q_acre != null) {
    parts.push(`Yield ${number(c.yield_q_acre, 1)} quintals an acre${c.yield_source ? ` (${YIELD_SOURCE[c.yield_source] ?? c.yield_source})` : ""}.`);
  }
  if (c.price_rs_q != null) {
    const error = c.price_mape != null ? `, usually within ±${Math.round(c.price_mape)}%` : "";
    parts.push(`Harvest price ${money(c.price_rs_q)} a quintal, ${priceSource(c.price_source)}${error}.`);
  }
  return parts.join(" ");
}

function whyToggle(crop, farm) {
  if (!farm || farm.N == null || !farm.district) return null;
  const panel = h("div", { class: "why", hidden: true });
  const button = h("button", { type: "button", class: "btn-link", "aria-expanded": "false" },
    `Why ${cropName(crop, true).toLowerCase()}?`);
  button.addEventListener("click", async () => {
    const open = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", String(!open));
    panel.hidden = open;
    if (open || panel.dataset.loaded) return;
    panel.replaceChildren(h("p", { class: "why-status" }, "Working out what helps and what holds it back…"));
    try {
      panel.replaceChildren(shapChart(await api.explain(farm, crop)));
      panel.dataset.loaded = "1";
    } catch (err) {
      panel.replaceChildren(h("p", { class: "why-status is-error" }, `The reasons didn't load: ${err.message}`));
    }
  });
  return h("div", { class: "crop-why" }, button, panel);
}

function shapChart(e) {
  const top = e.pushes.slice(0, 6);
  const max = Math.max(...top.map((p) => Math.abs(p.push)), 0.005);
  const name = cropName(e.crop, true).toLowerCase();
  return h("div", { class: "shap" },
    h("p", { class: "shap-sum" },
      `In a typical district ${name} scores ${pct(e.average)}. Your soil, weather and season take it to ${pct(e.suitability)}.`),
    h("ul", { class: "shap-list" }, top.map((p) =>
      h("li", { class: `shap-row ${p.push >= 0 ? "up" : "down"}` },
        h("span", { class: "shap-label" }, p.feature, h("small", {}, featureValue(p.feature, p.value))),
        h("span", { class: "shap-track", "aria-hidden": "true" },
          h("span", { class: "shap-bar", style: `--w:${((Math.abs(p.push) / max) * 50).toFixed(1)}%` })),
        h("span", { class: "shap-val" }, `${p.push >= 0 ? "+" : "−"}${number(Math.abs(p.push) * 100, 1)} pts`)))),
    h("p", { class: "shap-legend" }, h("span", { class: "key up" }, "Helps"), h("span", { class: "key down" }, "Holds back")));
}

const stat = (label, value) => h("div", { class: "stat" }, h("dt", {}, label), h("dd", {}, value));

function weather(r) {
  return h("section", { class: "ev" },
    head(`Weather in ${r.district}`, "Averages for 2015–2024 from NASA satellite data."),
    h("dl", { class: "stats" },
      stat("Temperature", `${number(r.temperature, 1)} °C`),
      stat("Humidity", `${number(r.humidity)}%`),
      stat("Rain a month, Jun–Sep", `${number(r.rain_kharif)} mm`),
      stat("Rain a month, Nov–Feb", `${number(r.rain_rabi)} mm`)));
}

function areaSoil(r, ctx) {
  const button = h("button", { type: "button", class: "btn-link" }, "Put these on my soil card");
  button.addEventListener("click", () => {
    ctx.useSoil(r);
    button.textContent = "Added to your soil card";
    button.disabled = true;
  });
  return h("section", { class: "ev" },
    head("Typical soil in your district", `${r.source}. A test of your own field gives better advice.`),
    h("dl", { class: "stats" },
      stat("Nitrogen", `${number(r.N)} kg/ha`), stat("Phosphorus", `${number(r.P, 1)} kg/ha`),
      stat("Potassium", `${number(r.K)} kg/ha`), stat("pH", number(r.ph, 2))),
    h("div", { class: "ev-action" }, button));
}

function priceForecast(r) {
  const title = `${cropName(r.crop)} price`;
  if (!r.months) {
    return h("section", { class: "ev" },
      head(title, "In this state the government buys most of the crop at the minimum support price."),
      h("dl", { class: "stats" }, stat(r.source, `${money(r.price_rs_q)} a quintal`)));
  }
  const where = r.source === "All India" ? "all-India mandis" : `${r.source} mandis`;
  const swings = r.forecast_error_pct > 30; // as in the Streamlit app
  return h("section", { class: "ev" },
    head(`${title} forecast, ${where}`,
      `Next 12 months, per quintal. Past forecasts were off by about ${Math.round(r.forecast_error_pct)}%.`),
    h("div", { class: "chart" }, lineChart(r.months)),
    swings && h("p", { class: "ev-note" },
      `${cropName(r.crop, true)} prices swing a lot, so treat this forecast as a rough guide, not a promise.`));
}

function lineChart(months) {
  const W = 640, H = 190, padX = 10, top = 34, bottom = 30;
  const prices = months.map((m) => m.price_rs_q);
  const lo = Math.min(...prices), hi = Math.max(...prices);
  const span = hi - lo || hi * 0.05 || 1;
  const x = (i) => padX + (i * (W - 2 * padX)) / (months.length - 1);
  const y = (v) => top + (1 - (v - (lo - span * 0.25)) / (span * 1.5)) * (H - top - bottom);
  const points = prices.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  const iLo = prices.indexOf(lo), iHi = prices.indexOf(hi);
  const anchor = (i) => (i < 2 ? "start" : i > months.length - 3 ? "end" : "middle");
  const label = (i) => s("text", { x: x(i), y: y(prices[i]) - 12, "text-anchor": anchor(i), class: "value" }, money(prices[i]));

  return s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `${money(prices[0])} in ${months[0].month}, ${money(prices.at(-1))} in ${months.at(-1).month}. ` +
      `Highest ${money(hi)} in ${months[iHi].month}, lowest ${money(lo)} in ${months[iLo].month}.` },
    s("path", { class: "area", d: `M${x(0)},${H - bottom} L${points.join(" L")} L${x(months.length - 1)},${H - bottom} Z` }),
    s("polyline", { class: "line", points: points.join(" ") }),
    s("circle", { class: "dot", cx: x(iLo), cy: y(lo), r: 4.5 }),
    s("circle", { class: "dot high", cx: x(iHi), cy: y(hi), r: 4.5 }),
    label(iHi), iLo !== iHi && label(iLo),
    s("text", { x: x(0), y: H - 8, "text-anchor": "start" }, months[0].month),
    s("text", { x: x(months.length - 1), y: H - 8, "text-anchor": "end" }, months.at(-1).month));
}

