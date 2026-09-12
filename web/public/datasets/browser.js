import { matches } from "./search.js";

const form = document.querySelector("#filters");
const query = document.querySelector("#query");
const provider = document.querySelector("#provider");
const availability = document.querySelector("#availability");
const status = document.querySelector("#result-status");
const results = document.querySelector("#results");
let catalog;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function link(text, href) {
  const node = element("a", text);
  node.href = href;
  return node;
}

function datasetRow(dataset) {
  const row = element("article", null, "dataset");
  const heading = element("div", null, "dataset-heading");
  const title = element("h2");
  title.append(link(dataset.title, dataset.reference));
  heading.append(title, element("span", dataset.availability, "badge"));
  row.append(heading, element("p", `${dataset.provider} · ${dataset.domain} · ${dataset.id}`, "dataset-meta"));
  if (dataset.availability === "Planned") {
    row.append(element("p", dataset.description), element("p", "Not implemented. This entry cannot download data; no release is promised.", "catalog-note"));
    row.append(link("View planned coverage", dataset.reference));
    return row;
  }
  const facts = element("dl");
  for (const [label, value] of [["Files", dataset.formats.join(", ")], ["What you get", dataset.selection], ["Required inputs", dataset.inputs]]) {
    facts.append(element("dt", label), element("dd", value));
  }
  row.append(facts);
  const links = element("div", null, "dataset-links");
  links.append(link("Usage & limits", dataset.guide));
  for (const example of dataset.examples) links.append(link(`${example.title} example`, example.url));
  row.append(links);
  const details = element("details");
  details.append(element("summary", "Inspect in your terminal"));
  const install = dataset.availability === "Source only" ? null : `python -m pip install "usdata${dataset.reader_extra ? `[${dataset.reader_extra}]` : ""}"`;
  const command = [install, `usdata info ${dataset.id}`].filter(Boolean).join("\n");
  if (!install) details.append(link("Install from source first", "https://docs.usdata.dev/project/#source-installation"));
  else details.append(element("p", `Included since usdata ${dataset.since}. Use Python 3.11 or newer.`, "catalog-note"));
  const pre = element("pre");
  pre.append(element("code", command));
  const copy = element("button", "Copy commands");
  copy.type = "button";
  const feedback = element("span", "", "catalog-note");
  feedback.setAttribute("role", "status");
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(command);
      feedback.textContent = " Commands copied.";
    } catch {
      feedback.textContent = " Select and copy the commands above.";
    }
  });
  details.append(pre, copy, feedback, element("p", "The example links above show how to fetch and analyze this dataset. Downloads contact the upstream agency.", "catalog-note"));
  row.append(details);
  return row;
}

function readUrl() {
  const params = new URLSearchParams(location.search);
  query.value = params.get("q") ?? "";
  provider.value = params.get("provider") ?? "";
  availability.value = params.get("availability") ?? "implemented";
  if (provider.selectedIndex < 0) provider.value = "";
  if (availability.selectedIndex < 0) availability.value = "implemented";
}

function render(updateUrl = true) {
  const state = { query: query.value, provider: provider.value, availability: availability.value };
  const visible = catalog.datasets.filter(dataset => matches(dataset, state));
  results.replaceChildren(...visible.map(datasetRow));
  status.textContent = `${visible.length} ${visible.length === 1 ? "dataset" : "datasets"} found`;
  if (!visible.length) results.append(element("p", "No matching datasets. Try a broader topic, another agency, or include planned entries."));
  if (updateUrl) {
    const params = new URLSearchParams();
    if (state.query) params.set("q", state.query);
    if (state.provider) params.set("provider", state.provider);
    if (state.availability !== "implemented") params.set("availability", state.availability);
    history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}${location.hash}`);
  }
}

async function load() {
  try {
    const response = await fetch("/datasets/catalog.json");
    if (!response.ok) throw new Error("Catalog request failed");
    catalog = await response.json();
    if (!catalog.version || !Array.isArray(catalog.datasets) || !catalog.datasets.length) throw new Error("Invalid catalog");
    for (const agency of [...new Set(catalog.datasets.map(dataset => dataset.provider))].sort()) {
      const option = element("option", agency);
      option.value = agency;
      provider.append(option);
    }
    readUrl();
    render(false);
    for (const control of form.elements) control.disabled = false;
    document.querySelector("#catalog-note").textContent = `Catalog for usdata ${catalog.version}. “Released” is included in this version; “Source only” needs a source installation; “Planned” cannot fetch data. Coverage varies by station, product, and date. This searches curated metadata, not live agency inventories.`;
  } catch {
    status.textContent = "The dataset catalog could not load.";
    results.replaceChildren(link("Browse the documentation catalog", "https://docs.usdata.dev/generated/catalog/"));
    const retry = element("button", "Try again");
    retry.type = "button";
    retry.addEventListener("click", () => location.reload());
    results.append(element("p", "Check your connection, then try again."), retry);
  }
}

form.addEventListener("submit", event => event.preventDefault());
form.addEventListener("input", () => { if (catalog) render(); });
form.addEventListener("reset", () => { setTimeout(() => { if (catalog) render(); }, 0); });
window.addEventListener("popstate", () => { if (catalog) { readUrl(); render(false); } });
load();
