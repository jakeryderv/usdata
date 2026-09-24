// Progressive filtering for the server-rendered dataset grid; without it every
// released dataset is still listed. Filter state lives in the URL.
import { matches } from "./search.js";

const form = document.getElementById("finder");
const query = document.getElementById("q");
const planned = document.getElementById("planned");
const status = document.getElementById("status");
const empty = document.getElementById("empty");
const cards = [...document.querySelectorAll(".dataset-card")];
const groups = [...document.querySelectorAll(".topic-group")];
const state = { query: "", agency: "", topic: "", planned: false };

function readUrl() {
  const params = new URLSearchParams(location.search);
  state.query = params.get("q") ?? "";
  state.agency = params.get("agency") ?? "";
  state.topic = params.get("topic") ?? "";
  state.planned = params.get("planned") === "1";
}

function writeUrl() {
  const params = new URLSearchParams();
  if (state.query.trim()) params.set("q", state.query.trim());
  if (state.agency) params.set("agency", state.agency);
  if (state.topic) params.set("topic", state.topic);
  if (state.planned) params.set("planned", "1");
  const search = params.toString();
  history.replaceState(null, "", search ? `?${search}` : location.pathname);
}

function render(records) {
  query.value = state.query;
  planned.checked = state.planned;
  for (const button of form.querySelectorAll("button[data-filter]")) {
    button.setAttribute("aria-pressed", String(state[button.dataset.filter] === button.dataset.value));
  }
  const visible = new Set(records.filter(record => matches(record, state)).map(record => record.id));
  for (const card of cards) card.hidden = !visible.has(card.dataset.id);
  for (const group of groups) group.hidden = !group.querySelector(".dataset-card:not([hidden])");
  document.body.classList.toggle("show-planned", state.planned);
  const count = visible.size;
  status.textContent = `${count} ${count === 1 ? "dataset" : "datasets"}`;
  empty.hidden = count > 0;
}

async function start() {
  const response = await fetch("/datasets/catalog.json");
  if (!response.ok) throw new Error(`catalog: HTTP ${response.status}`);
  const { datasets } = await response.json();
  readUrl();
  const update = () => { writeUrl(); render(datasets); };
  query.addEventListener("input", () => { state.query = query.value; update(); });
  planned.addEventListener("change", () => { state.planned = planned.checked; update(); });
  form.addEventListener("submit", event => event.preventDefault());
  form.addEventListener("click", event => {
    const button = event.target.closest("button[data-filter]");
    if (!button) return;
    state[button.dataset.filter] = button.dataset.value;
    update();
  });
  render(datasets);
}

start().catch(error => {
  status.textContent = "Filtering is unavailable; every released dataset is listed below.";
  console.error(error);
});
