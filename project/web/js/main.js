// Wires the page together: farm panel, chat, and the farm sheet on small screens.
import * as chat from "./chat.js";
import * as farm from "./farm.js";

const $ = (id) => document.getElementById(id);
const sheet = $("farm");
const toggle = $("farm-toggle");
const scrim = $("scrim");
const small = matchMedia("(max-width: 959px)");

function openSheet(open) {
  sheet.classList.toggle("open", open);
  scrim.hidden = !open;
  toggle.setAttribute("aria-expanded", String(open));
  if (open) $("state").focus({ preventScroll: true });
  else if (small.matches) toggle.focus();
}

const soil = Object.fromEntries(["N", "P", "K", "ph"].map((k) => [k, $(k)]));

farm.init({
  form: $("farm-form"),
  state: $("state"),
  district: $("district"),
  month: $("month"),
  top: $("top"),
  season: $("season"),
  useTypical: $("use-typical"),
  source: $("soil-source"),
  hint: $("form-hint"),
  soil,
  cells: Object.fromEntries(Object.entries(soil).map(([k, input]) => [k, input.closest(".soil-cell")])),
}, {
  onAsk(message) {
    if (small.matches) openSheet(false);
    chat.send(message);
  },
  onChange(summary) {
    $("farm-summary").textContent = summary;
  },
});

chat.init({
  thread: $("thread"),
  welcome: $("welcome"),
  composer: $("composer"),
  input: $("message"),
  send: $("send"),
}, farm);

$("new-chat").addEventListener("click", chat.newChat);
toggle.addEventListener("click", () => openSheet(!sheet.classList.contains("open")));
$("farm-close").addEventListener("click", () => openSheet(false));
scrim.addEventListener("click", () => openSheet(false));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && sheet.classList.contains("open")) openSheet(false);
});
small.addEventListener("change", () => openSheet(false));
