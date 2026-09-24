// The dataset grid at /datasets/ and one page per implemented dataset (ADR 0041).
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { escape, page } from "./layout.mjs";
import { renderExample } from "./examples.mjs";

const DOCS = "https://docs.usdata.dev/";
export const implemented = dataset => dataset.availability !== "Planned";
export const pagePath = dataset => new URL(dataset.page).pathname;
export const walkthroughFolder = dataset => dataset.walkthrough?.split("/")[2] ?? null;

/** The first sentence of a registry description, for a lede. */
export function firstSentence(text) {
  const match = text.match(/^(.+?[.!?])(\s+[A-Z(]|$)/s);
  return (match ? match[1] : text).trim();
}

/** A stable hue per topic, so a dataset without a preview still gets a recognisable tile. */
export function hue(topic) {
  let hash = 0;
  for (const char of topic) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  return hash % 360;
}

const tile = (dataset, label = "") => `<div class="tile" style="--hue: ${hue(dataset.domain)}" aria-hidden="true">${label ? `<span>${escape(label)}</span>` : ""}</div>`;

function card(dataset, preview) {
  const planned = !implemented(dataset);
  const href = planned ? `${DOCS}generated/catalog/${dataset.provider_id}/` : pagePath(dataset);
  const image = preview ? `<img src="${pagePath(dataset)}${preview}" alt="" loading="lazy">` : tile(dataset);
  const chips = [
    ...(planned ? [`<span class="chip muted">Planned</span>`] : dataset.formats.map(format => `<span class="chip">${escape(format)}</span>`)),
    ...(dataset.credentials ? [`<span class="chip key">Key required</span>`] : []),
  ];
  return `<article class="dataset-card${planned ? " planned" : ""}" data-id="${escape(dataset.id)}" data-agency="${escape(dataset.provider)}" data-topic="${escape(dataset.domain)}"${planned ? " data-planned" : ""}>
<div class="card-media">${image}</div>
<div class="card-body"><p class="eyebrow">${escape(dataset.provider)} · ${escape(dataset.domain)}</p>
<h3><a href="${href}">${escape(dataset.title)}</a></h3>
<p class="card-product">${escape(dataset.product)}</p>
<div class="chips">${chips.join("")}</div></div></article>`;
}

function glance(dataset) {
  const rows = [
    ["Spatial", dataset.resolution?.spatial],
    ["Time step", dataset.resolution?.temporal],
    ["Updates", dataset.update_frequency],
    ["Latency", dataset.latency],
    ["Files", dataset.formats.join(", ")],
    ["Selection", dataset.selection],
    ["You provide", dataset.inputs],
    ["Longest request", dataset.max_window],
    ["Key", dataset.credentials ? dataset.credentials.variables.map(name => `<code>${escape(name)}</code>`).join(", ") + ` · <a href="${escape(dataset.credentials.signup)}">request one</a>` : null],
  ].filter(([, value]) => value);
  return `<dl class="glance">${rows.map(([label, value]) => `<div><dt>${label}</dt><dd>${label === "Key" ? value : escape(value)}</dd></div>`).join("")}</dl>`;
}

function quickStart(dataset) {
  const extra = dataset.reader_extra ? `usdata[${dataset.reader_extra}]` : "usdata";
  const install = `python -m pip install "${extra}"`;
  const key = dataset.credentials ? `<p class="note">Set ${dataset.credentials.variables.map(name => `<code>${escape(name)}</code>`).join(" and ")} in the environment first; <a href="${escape(dataset.guide)}">the guide</a> says how to get a key.</p>` : "";
  if (!dataset.quickstart) {
    return `<pre class="code"><code>${escape(install)}\nusdata info ${escape(dataset.id)}</code></pre>${key}`;
  }
  const panels = [
    ["Terminal", `${install}\n${dataset.quickstart.cli}`],
    ["Python", dataset.quickstart.python],
    ["Manifest", `# dataset.yaml, then: usdata pull dataset.yaml\n${dataset.quickstart.manifest}`],
  ];
  const id = dataset.id.replace(/[^a-z0-9]+/g, "-");
  const tabs = panels.map(([label], index) => `<button type="button" role="tab" id="tab-${id}-${index}" aria-controls="panel-${id}-${index}" aria-selected="${index === 0}">${label}</button>`).join("");
  const bodies = panels.map(([label, code], index) => `<div class="tab-panel" role="tabpanel" id="panel-${id}-${index}" aria-labelledby="tab-${id}-${index}"><p class="panel-label">${label}</p><pre class="code"><code>${escape(code)}</code></pre></div>`).join("");
  return `<div class="tabs" data-tabs><div class="tab-list" role="tablist" aria-label="Quick start">${tabs}</div>${bodies}</div>
<p class="note">The same query the walkthrough below ran. ${dataset.reader_extra ? `The <code>${escape(dataset.reader_extra)}</code> extra opens the files.` : "No bundled reader opens these files; use the tools named in the guide."}</p>${key}`;
}

function studyCards(dataset, studies) {
  const used = dataset.studies.map(slug => studies.get(slug));
  if (!used.length) return "";
  return `<section class="section" id="studies" aria-labelledby="studies-title"><h2 id="studies-title">Used in these studies</h2><div class="study-grid compact">${used.map(study => study.card).join("")}</div></section>`;
}

/**
 * Render /datasets/ and every implemented dataset's page. `studies` maps each
 * study slug to its title, card HTML, and preview, from render-studies.mjs.
 * Returns each implemented dataset's preview path, for the homepage and tests.
 */
export async function buildDatasets(root, output, catalog, examples, studies) {
  const pinned = new Set(examples.pinned);
  const previews = new Map();
  for (const dataset of catalog.datasets.filter(implemented)) {
    const directory = join(output, pagePath(dataset));
    await mkdir(directory, {recursive: true});
    // Every implemented dataset has a walkthrough (ADR 0041); the registry check enforces it.
    const folder = walkthroughFolder(dataset);
    if (!folder) throw new Error(`${dataset.id}: no walkthrough`);
    const walkthrough = await renderExample(root, "datasets", folder, directory, {title: dataset.title, pinned: pinned.has(`datasets/${folder}`), codeOpen: true});
    previews.set(dataset.id, walkthrough.preview);
    const hero = `<figure class="hero-figure"><img src="${walkthrough.preview}" alt="The walkthrough's first look at ${escape(dataset.title.toLowerCase())}" width="960" height="540"></figure>`;
    const chips = [
      ...dataset.formats.map(format => `<span class="chip">${escape(format)}</span>`),
      ...(dataset.credentials ? [`<span class="chip key">Key required</span>`] : []),
      `<span class="chip muted">${dataset.availability === "Released" ? `Since v${escape(dataset.since)}` : "Source only"}</span>`,
    ];
    const content = `<nav class="crumbs" aria-label="Breadcrumb"><a href="/datasets/">Datasets</a><span aria-hidden="true">/</span><a href="/datasets/?agency=${encodeURIComponent(dataset.provider)}">${escape(dataset.provider)}</a><span aria-hidden="true">/</span><a href="/datasets/?topic=${encodeURIComponent(dataset.domain)}">${escape(dataset.domain)}</a></nav>
<header class="dataset-hero"><div class="hero-text"><p class="eyebrow">${escape(dataset.provider)} · ${escape(dataset.product)}</p><h1>${escape(dataset.title)}</h1><p class="lede">${escape(firstSentence(dataset.description))}</p><div class="chips">${chips.join("")}</div>
<div class="actions"><a class="button primary" href="#quick-start">Quick start</a><a class="button" href="#walkthrough">Walkthrough</a><a class="button ghost" href="${escape(dataset.guide)}">Guide <span aria-hidden="true">↗</span></a></div></div>${hero}</header>
<section class="section" aria-labelledby="glance-title"><h2 id="glance-title">At a glance</h2>${glance(dataset)}<details class="about"><summary>Full description</summary><p>${escape(dataset.description)}</p></details></section>
<section class="section" id="quick-start" aria-labelledby="quick-title"><h2 id="quick-title">Quick start</h2>${quickStart(dataset)}</section>
<section class="section" id="walkthrough" aria-labelledby="walkthrough-title"><div class="section-head"><h2 id="walkthrough-title">Walkthrough</h2>${walkthrough.downloads}</div><p class="note">Saved results from a run against the live service; the notebook records when it ran and the checksums of what it read. <a href="/studies/#run">Run it yourself</a>.</p>${walkthrough.article}</section>
${studyCards(dataset, studies)}
<section class="section" id="reference" aria-labelledby="reference-title"><h2 id="reference-title">Reference</h2><ul class="link-list"><li><a href="${escape(dataset.guide)}">Usage guide</a>: selection rules, what arrives, and what the service does not say</li><li><a href="${escape(dataset.reference)}">Reference</a>: parameters, variables, coverage, and terms, at the end of the guide</li>${dataset.homepage ? `<li><a href="${escape(dataset.homepage)}">Upstream documentation</a> from ${escape(dataset.provider)}</li>` : ""}</ul>${dataset.citation ? `<p class="citation"><span>Cite as</span> ${escape(dataset.citation)}</p>` : ""}</section>`;
    await writeFile(join(directory, "index.html"), page({
      title: dataset.title,
      description: firstSentence(dataset.description),
      canonical: pagePath(dataset),
      content,
      current: "/datasets/",
      styles: ["/pages.css"],
      scripts: ["/tabs.js"],
      mainClass: "page",
    }));
  }

  const topics = [...new Set(catalog.datasets.map(dataset => dataset.domain))];
  const agencies = [...new Set(catalog.datasets.map(dataset => dataset.provider))];
  const released = catalog.datasets.filter(implemented);
  const groups = topics.map(topic => {
    const members = catalog.datasets.filter(dataset => dataset.domain === topic);
    const empty = members.every(dataset => !implemented(dataset));
    return `<section class="topic-group" data-topic="${escape(topic)}"${empty ? " data-planned-only" : ""}><h2>${escape(topic)}</h2><div class="card-grid">${members.map(dataset => card(dataset, previews.get(dataset.id))).join("\n")}</div></section>`;
  }).join("\n");
  // A value with no implemented dataset is offered only once planned datasets are shown.
  const plannedOnly = (field, value) => released.every(dataset => dataset[field] !== value);
  const chipRow = (name, field, label, values) => `<div class="filter-group" role="group" aria-label="${label}"><span class="filter-label">${label}</span><button type="button" class="filter" data-filter="${name}" data-value="" aria-pressed="true">All</button>${values.map(value => `<button type="button" class="filter" data-filter="${name}" data-value="${escape(value)}" aria-pressed="false"${plannedOnly(field, value) ? " data-planned-only" : ""}>${escape(value)}</button>`).join("")}</div>`;
  const releasedAgencies = [...new Set(released.map(dataset => dataset.provider))];
  const agencyList = releasedAgencies.length > 1 ? `${releasedAgencies.slice(0, -1).join(", ")}, and ${releasedAgencies.at(-1)}` : releasedAgencies[0];
  const content = `<header class="page-heading"><h1>Datasets</h1><p class="lede">${released.length} datasets from ${escape(agencyList)}, each with a page, a quick start, and a walkthrough. Search, or browse by topic.</p></header>
<form class="finder" id="finder" role="search" aria-label="Find datasets">
<label class="visually-hidden" for="q">Search datasets</label><input id="q" name="q" type="search" placeholder="Try rainfall, hurricanes, streamflow, or air quality" autocomplete="off">
${chipRow("agency", "provider", "Agency", agencies)}
${chipRow("topic", "domain", "Topic", topics)}
<label class="toggle"><input type="checkbox" id="planned" name="planned"> Include ${catalog.datasets.length - released.length} planned datasets</label>
</form>
<p class="status" id="status" role="status" aria-live="polite">${released.length} datasets</p>
<div id="groups">${groups}</div>
<p class="empty" id="empty" hidden>No dataset matches. Try a broader word, or <a href="/datasets/">clear the filters</a>.</p>
<p class="note">This searches usdata's curated catalog, not live agency inventories. Coverage varies by station, product, and date.</p>`;
  await mkdir(join(output, "datasets"), {recursive: true});
  await writeFile(join(output, "datasets/index.html"), page({
    title: "Datasets",
    description: `${released.length} U.S. public science datasets from ${agencyList}, each with a page, a quick start, and a walkthrough.`,
    canonical: "/datasets/",
    content,
    current: "/datasets/",
    styles: ["/pages.css"],
    scripts: ["/datasets/finder.js"],
    type: "website",
    mainClass: "page",
  }));
  return previews;
}
