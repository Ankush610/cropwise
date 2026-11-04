// How numbers, crops, sources and models are written for a farmer.

export const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
  "October", "November", "December"];

// Season by sowing month, as in recommend.SEASON_MONTHS
export const SEASONS = { kharif: "June to September", rabi: "October to January", summer: "February to May" };
export const seasonOf = (month) => (month >= 6 && month <= 9 ? "kharif" : month >= 10 || month === 1 ? "rabi" : "summer");

const CROPS = {
  bajra: "Bajra (pearl millet)", blackgram: "Black gram (urad)", chickpea: "Chickpea (chana)",
  jowar: "Jowar (sorghum)", kidneybeans: "Kidney beans (rajma)", lentil: "Lentil (masoor)",
  mothbeans: "Moth bean", mungbean: "Mung bean (moong)", mustard: "Mustard (sarson)",
  pigeonpeas: "Pigeon pea (arhar)", ragi: "Ragi (finger millet)", sesamum: "Sesame (til)",
  rice: "Rice (paddy)",
};

export function cropName(crop, short = false) {
  const name = CROPS[crop] ?? crop.charAt(0).toUpperCase() + crop.slice(1);
  return short ? name.replace(/\s*\(.*\)$/, "") : name;
}

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
export const money = (v) => (v < 0 ? `−${inr.format(-v)}` : inr.format(v));
export const number = (v, digits = 0) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(v);
export const pct = (v) => `${Math.round(v * 100)}%`;

export function priceSource(source) {
  if (!source || source === "no price data") return "no price data";
  if (source.startsWith("MSP")) return `government MSP ${source.slice(4)}`;
  return source === "All India" ? "all-India mandi prices" : `${source} mandi prices`;
}

export const YIELD_SOURCE = { district: "district average", "state median": "state average", "India median": "India average" };

export function modelName(id) {
  if (!id) return null;
  const [provider, model] = id.split("/");
  if (provider === "ollama") return "Qwen3 4B on this computer (offline)";
  return model.replace(/^gemini-/, "Gemini ").replace(/-flash/, " Flash").replace(/-lite/, " Lite");
}

// Units for the SHAP feature names from api.explain (recommend.FEATURE_NAMES)
export function featureValue(feature, value) {
  if (feature === "Season") return ["kharif", "rabi", "summer"][value] ?? "";
  if (feature === "Soil pH") return `pH ${number(value, 2)}`;
  if (["Nitrogen", "Phosphorus", "Potassium"].includes(feature)) return `${number(value)} kg/ha`;
  if (feature.includes("emperature")) return `${number(value, 1)} °C`;
  if (feature.includes("ainfall")) return `${number(value)} mm a month`;
  if (feature === "Humidity") return `${number(value)}%`;
  return number(value, 1);
}
