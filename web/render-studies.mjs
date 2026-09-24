// The studies index at /studies/ and one page per study (ADR 0041).
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { escape, page } from "./layout.mjs";
import { renderExample } from "./examples.mjs";
import { renderMarkdown } from "./notebook.mjs";
import { pagePath } from "./render-datasets.mjs";

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const datasetChips = datasets => `<div class="chips">${datasets.map(dataset => `<a class="chip link" href="${pagePath(dataset)}">${escape(dataset.title)}</a>`).join("")}</div>`;

/**
 * Render /studies/ and every study page. Returns a map from slug to the study's
 * title, preview path, and card, which dataset pages reuse.
 */
export async function buildStudies(root, output, catalog, examples, setup) {
  const pinned = new Set(examples.pinned);
  const studies = new Map();
  for (const study of examples.studies) {
    if (!SLUG.test(study.slug) || !study.title?.trim() || !study.summary?.trim()) throw new Error(`Invalid study entry: ${JSON.stringify(study)}`);
    const datasets = catalog.datasets.filter(dataset => dataset.studies.includes(study.slug));
    if (!datasets.length) throw new Error(`${study.slug}: no dataset lists this study`);
    const url = `/studies/${study.slug}/`;
    const directory = join(output, url);
    const rendered = await renderExample(root, "studies", study.slug, directory, {title: study.title, pinned: pinned.has(`studies/${study.slug}`)});
    const preview = rendered.preview ? `${url}${rendered.preview}` : null;
    const content = `<nav class="crumbs" aria-label="Breadcrumb"><a href="/studies/">Studies</a></nav>
<header class="study-hero"><p class="eyebrow">Study</p><h1>${escape(study.title)}</h1><p class="lede">${escape(study.summary)}</p>
<div class="study-data"><span class="filter-label">Data</span>${datasetChips(datasets)}</div>${rendered.downloads}</header>
${rendered.notebook ? `<p class="note">Saved results from a run against the live services; the notebook records when it ran and the checksums of what it read. <a href="/studies/#run">Run it yourself</a>.</p>` : ""}
${rendered.article}`;
    await writeFile(join(directory, "index.html"), page({title: study.title, description: study.summary, canonical: url, content, current: "/studies/", styles: ["/pages.css"], mainClass: "page"}));
    const media = preview ? `<img src="${preview}" alt="" loading="lazy">` : `<div class="tile" style="--hue: 215" aria-hidden="true"><span>Study</span></div>`;
    const card = `<article class="study-card"><div class="card-media">${media}</div><div class="card-body"><h3><a href="${url}">${escape(study.title)}</a></h3><p>${escape(study.summary)}</p><p class="card-sources">${datasets.map(dataset => escape(dataset.title)).join(" · ")}</p></div></article>`;
    studies.set(study.slug, {title: study.title, preview, card, datasets});
  }

  const [first, ...rest] = examples.studies.map(study => ({...study, ...studies.get(study.slug)}));
  const feature = `<article class="study-feature"><div class="card-media">${first.preview ? `<img src="${first.preview}" alt="">` : ""}</div><div class="card-body"><p class="eyebrow">Start here</p><h2><a href="/studies/${first.slug}/">${escape(first.title)}</a></h2><p>${escape(first.summary)}</p>${datasetChips(first.datasets)}</div></article>`;
  const content = `<header class="page-heading"><h1>Studies</h1><p class="lede">Questions answered end to end with real data: the sources, the analysis, the saved results, and pinned inputs anyone can restore. Each dataset's own walkthrough is on its <a href="/datasets/">dataset page</a>.</p></header>
${feature}
<div class="study-grid">${rest.map(study => study.card).join("\n")}</div>
<section class="section prose run-setup" id="run"><h2>Run a study yourself</h2>${renderMarkdown(setup)}</section>`;
  await mkdir(join(output, "studies"), {recursive: true});
  await writeFile(join(output, "studies/index.html"), page({title: "Studies", description: "Questions answered end to end with U.S. public science data, with saved results and pinned inputs.", canonical: "/studies/", content, current: "/studies/", styles: ["/pages.css"], type: "website", mainClass: "page"}));
  return studies;
}
