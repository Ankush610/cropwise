// The conversation with the advisor: send, wait, show the reply with its evidence, recover from errors.
import { api } from "./api.js";
import { h } from "./dom.js";
import { cropList, evidence, TOOL_LABELS } from "./evidence.js";
import { modelName } from "./format.js";
import { markdown } from "./markdown.js";

const ID_KEY = "fasal-salah.farmer-id";
const SLOW_AFTER_MS = 15000;

let els;
let farm;
let farmerId;
let busy = false;

const store = {
  get: (key) => { try { return localStorage.getItem(key); } catch { return null; } },
  set: (key, value) => { try { localStorage.setItem(key, value); } catch { /* private mode: id lasts this visit */ } },
};

function newId() {
  const raw = globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
  return `f-${raw.replace(/[^A-Za-z0-9]/g, "").slice(0, 20)}`;
}

export function init(elements, farmPanel) {
  els = elements;
  farm = farmPanel;
  farmerId = store.get(ID_KEY) ?? newId();
  store.set(ID_KEY, farmerId);

  els.composer.addEventListener("submit", (e) => { e.preventDefault(); send(els.input.value); });
  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(els.input.value); }
  });
  els.input.addEventListener("input", autosize);
  for (const chip of els.welcome.querySelectorAll(".chip")) {
    chip.addEventListener("click", () => send(chip.textContent));
  }
  restore();
}

function autosize() {
  els.input.style.height = "auto";
  els.input.style.height = `${els.input.scrollHeight}px`;
}

const smooth = () => (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

export function send(text) {
  text = text.trim();
  if (!text || busy) return;
  els.input.value = "";
  autosize();
  els.welcome.hidden = true;
  const mine = farmerMessage(text);
  els.thread.append(mine);
  mine.scrollIntoView({ block: "end", behavior: smooth() });
  ask(text);
}

async function ask(text) {
  busy = true;
  els.send.disabled = true;
  const pending = pendingMessage();
  els.thread.append(pending.el);
  try {
    const card = farm.values();  // the soil card is the source of truth for the farm
    const res = await api.chat(farmerId, text, card.district ? card : null);
    const reply = advisorMessage(res);
    pending.el.replaceWith(reply);
    reply.scrollIntoView({ block: "start", behavior: smooth() });
    const lastFarm = res.tool_calls.map((c) => c.farm).filter((f) => f && Object.keys(f).length).at(-1);
    if (lastFarm) farm.sync(lastFarm);
  } catch (err) {
    pending.el.replaceWith(errorMessage(err, text));
  } finally {
    clearTimeout(pending.timer);
    busy = false;
    els.send.disabled = false;
    if (matchMedia("(pointer: fine)").matches) els.input.focus();
  }
}

function farmerMessage(text) {
  return h("div", { class: "msg msg-farmer" }, h("p", {}, text));
}

function pendingMessage() {
  const status = h("span", {}, "Checking soil, weather and prices…");
  const el = h("div", { class: "msg msg-pending", role: "status" },
    h("span", { class: "dots", "aria-hidden": "true" }, h("i"), h("i"), h("i")), status);
  const timer = setTimeout(() => {
    status.textContent = "Still working. If the online model is busy, the offline one can take a few minutes.";
  }, SLOW_AFTER_MS);
  return { el, timer };
}

function advisorMessage(res) {
  const reply = h("div", { class: "reply" });
  reply.innerHTML = markdown(res.reply || "The advisor didn't write a reply. Try asking again.");  // markdown() escapes
  const cards = res.tool_calls.map((call) => evidence(call, { useSoil: farm.applySoil }));
  const used = [...new Set(res.tool_calls.filter((c) => !c.result?.error).map((c) => TOOL_LABELS[c.tool]))];
  const model = modelName(res.model);
  const byline = model && `Answered by ${model}${used.length ? `, from the app's ${used.join(" and ")}` : ""}.`;
  return h("article", { class: "msg msg-advisor" }, reply, cards, byline && h("p", { class: "byline" }, byline));
}

function errorMessage(err, text) {
  const what = err.status === 503
    ? "The advisor isn't reachable: the online model and the offline model both failed."
    : err.message;
  const retry = h("button", { type: "button", class: "btn-quiet" }, "Try again");
  const el = h("div", { class: "msg msg-error", role: "alert" },
    h("p", {}, what),
    h("div", { class: "actions" }, retry, farm.complete() && withoutChat()));
  retry.addEventListener("click", () => { el.remove(); ask(text); });
  return el;
}

// The crop ranking doesn't need the chat model: offer it straight from the soil card
function withoutChat() {
  const button = h("button", { type: "button", class: "btn-quiet" }, "Show crops without the advisor");
  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Ranking crops…";
    const values = farm.values();
    try {
      const { inputs, crops } = await api.recommend(values);
      const warning = inputs.season_share < 0.1
        ? `Little is sown in ${inputs.district} in the ${inputs.season} season, so these picks rest on other districts.`
        : null;
      const note = crops.length < values.top
        ? `Only ${crops.length} of the ${values.top} crops asked for are shown: the others are below 5% suitability, too poor a fit to suggest.`
        : null;
      const card = cropList({ district: inputs.district, season: inputs.season, crops, warning, note }, values);
      const msg = h("article", { class: "msg msg-advisor" }, card,
        h("p", { class: "byline" }, "From the app's crop ranking, without the advisor."));
      button.closest(".msg").after(msg);
      msg.scrollIntoView({ block: "start", behavior: smooth() });
    } catch (err) {
      button.textContent = `Ranking failed: ${err.message}`;
    }
  });
  return button;
}

async function restore() {
  try {
    const profile = await api.profile(farmerId);
    farm.sync(profile.farm);
    if (!profile.history.length) return;
    els.welcome.hidden = true;
    for (const m of profile.history) {
      els.thread.append(m.role === "user" ? farmerMessage(m.content) : advisorMessage({ reply: m.content, tool_calls: [] }));
    }
    els.thread.scrollTop = els.thread.scrollHeight;
  } catch {
    // no saved chat: start fresh
  }
}

export function newChat() {
  if (busy) return;
  farmerId = newId();
  store.set(ID_KEY, farmerId);
  els.thread.replaceChildren(els.welcome);
  els.welcome.hidden = false;
  els.input.focus();
}
