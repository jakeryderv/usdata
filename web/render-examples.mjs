import { readFile, readdir, mkdir, writeFile, copyFile } from "node:fs/promises";
import { join } from "node:path";
import MarkdownIt from "markdown-it";
import sanitize from "sanitize-html";

const markdown = new MarkdownIt({ html: false });
markdown.renderer.rules.heading_open = (tokens, index, options, env, renderer) => {
  const label = tokens[index + 1].children.map(token => token.content).join("");
  tokens[index].attrSet("id", label.toLowerCase().replace(/[^a-z0-9\s-]/g, "").trim().replace(/\s+/g, "-"));
  return renderer.renderToken(tokens, index, options);
};
const text = value => Array.isArray(value) ? value.join("") : value ?? "";
export const escape = value => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[char]);
const clean = html => sanitize(html, {
  allowedTags: sanitize.defaults.allowedTags.concat(["img"]),
  allowedAttributes: {a: ["href", "title"], img: ["src", "alt", "title"], code: ["class"], th: ["colspan", "rowspan"], td: ["colspan", "rowspan"], h1: ["id"], h2: ["id"], h3: ["id"], h4: ["id"]},
  allowedSchemes: ["http", "https", "mailto"],
});
export const renderMarkdown = source => clean(markdown.render(source));
const withoutTitle = source => source.replace(/^# [^\n]*\n+/, "");
const pre = source => `<pre><code>${escape(source)}</code></pre>`;

function page(title, description, content, canonical) {
  return `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="${escape(description)}"><meta name="color-scheme" content="dark light">
<title>${escape(title)} · usdata</title><link rel="canonical" href="https://usdata.dev${canonical}">
<link rel="icon" href="/logo.svg" type="image/svg+xml"><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/examples.css">
</head><body><a class="skip" href="#main">Skip to content</a>
<header class="header wrap"><a class="brand" href="/" aria-label="usdata home"><img src="/logo.svg" alt="" width="30" height="30"> usdata</a>
<nav aria-label="Main navigation"><a href="/datasets/">Datasets</a><a href="/examples/" aria-current="page">Examples</a><a href="https://docs.usdata.dev/">Docs</a><a href="https://github.com/jakeryderv/usdata">GitHub</a></nav></header>
<main class="wrap examples-main" id="main">${content}</main>
<footer class="wrap"><span>usdata · Public scientific data, with provenance.</span><a href="https://docs.usdata.dev/">Read the documentation</a></footer>
</body></html>\n`;
}

// Render only saved, supported output types. Never execute notebook code or scripts.
export async function renderNotebook(notebook, directory, title) {
  let preview = null;
  const cells = [];
  for (const [cellIndex, cell] of notebook.cells.entries()) {
    if (cell.cell_type === "markdown") {
      cells.push(`<section class="notebook-text">${renderMarkdown(cellIndex === 0 ? withoutTitle(text(cell.source)) : text(cell.source))}</section>`);
    } else if (cell.cell_type === "code") {
      if (cell.execution_count === null || !cell.outputs?.length) throw new Error(`${title}: missing saved execution in cell ${cellIndex}`);
      const outputs = [];
      for (const [outputIndex, output] of cell.outputs.entries()) {
        if (output.output_type === "error") throw new Error(`${title}: saved error in cell ${cellIndex}`);
        const data = output.data ?? {};
        if (data["image/png"]) {
          const filename = `plot-${cellIndex}-${outputIndex}.png`;
          const bytes = Buffer.from(text(data["image/png"]), "base64");
          if (!bytes.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error(`${title}: invalid PNG`);
          await writeFile(join(directory, filename), bytes);
          preview ??= filename;
          outputs.push(`<figure><img src="${filename}" alt="Saved plot from ${escape(title)}" loading="lazy"><figcaption>Saved notebook output; see the surrounding analysis for units and interpretation.</figcaption></figure>`);
        } else if (data["text/html"]) {
          outputs.push(`<div class="table-output" tabindex="0" role="region" aria-label="Notebook table">${clean(text(data["text/html"]))}</div>`);
        } else if (data["text/markdown"]) {
          outputs.push(renderMarkdown(text(data["text/markdown"])));
        } else if (output.output_type === "stream" || data["text/plain"]) {
          outputs.push(pre(text(output.text ?? data["text/plain"])));
        } else {
          throw new Error(`${title}: unsupported saved output in cell ${cellIndex}`);
        }
      }
      cells.push(`<section class="notebook-cell"><details class="cell-code"><summary>Code · cell ${escape(cell.execution_count)}</summary>${pre(text(cell.source))}</details><div class="cell-output">${outputs.join("\n")}</div></section>`);
    } else {
      throw new Error(`${title}: unsupported cell type ${cell.cell_type}`);
    }
  }
  return {html: cells.join("\n"), preview};
}

export async function buildExamples(root, output) {
  const source = join(root, "examples");
  const catalog = JSON.parse(await readFile(join(source, "catalog.json"), "utf8"));
  const datasets = JSON.parse(await readFile(join(root, "web/public/datasets/catalog.json"), "utf8")).datasets;
  const folders = (await readdir(source, {withFileTypes:true})).filter(entry => entry.isDirectory() && !entry.name.startsWith(".")).map(entry => entry.name).sort();
  const slugs = catalog.map(example => example.slug);
  if (new Set(slugs).size !== slugs.length || JSON.stringify([...slugs].sort()) !== JSON.stringify(folders)) throw new Error("Example catalog must include every example folder exactly once");
  const destination = join(output, "examples");
  await mkdir(destination, {recursive:true});
  const cards = [];
  for (const example of catalog) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(example.slug) || !example.title?.trim() || !example.summary?.trim()) throw new Error("Invalid example catalog entry");
    const url = `/examples/${example.slug}/`;
    const directory = join(destination, example.slug);
    await mkdir(directory, {recursive:true});
    const files = await readdir(join(source, example.slug));
    const notebook = files.includes("example.ipynb");
    const related = datasets.filter(dataset => dataset.examples.some(entry => entry.url === `https://usdata.dev${url}`));
    if (!related.length) throw new Error(`${example.slug}: missing dataset catalog relationship`);
    const sources = related.map(dataset => `<a href="/datasets/?q=${encodeURIComponent(dataset.id)}">${escape(dataset.title)}</a>`).join("");
    const downloads = [];
    for (const filename of ["example.ipynb", "dataset.yaml"].filter(filename => files.includes(filename))) {
      await copyFile(join(source, example.slug, filename), join(directory, filename));
      downloads.push(`<a class="button" href="${filename}" download>${filename.endsWith("ipynb") ? "Download notebook" : "Download manifest"}</a>`);
    }
    const readme = renderMarkdown(withoutTitle(await readFile(join(source, example.slug, "README.md"), "utf8")));
    const rendered = notebook ? await renderNotebook(JSON.parse(await readFile(join(source, example.slug, "example.ipynb"), "utf8")), directory, example.title) : null;
    const kind = notebook ? "Notebook · saved results" : "Manifest walkthrough";
    const body = `<a href="/examples/">All examples</a><header class="example-heading"><p class="eyebrow">${kind}</p><h1>${escape(example.title)}</h1><p class="example-intro">${escape(example.summary)}</p></header>
<aside class="example-inputs" aria-label="Source datasets"><strong>Source datasets</strong><div class="source-links">${sources}</div></aside>
<div class="actions">${downloads.join("")}<a class="button" href="https://github.com/jakeryderv/usdata/tree/main/examples/${example.slug}">View source</a></div>
${notebook ? `<p class="snapshot-note">These are saved results, not live data. Execution times, source URLs, and checksums are recorded below. <a href="/examples/#run-examples">Set up and run examples</a>.</p><details class="run-guide"><summary>Run this example · instructions and limitations</summary><div class="prose">${readme}</div></details><article class="prose notebook">${rendered.html}</article>` : `<article class="prose">${readme}</article>`}`;
    await writeFile(join(directory, "index.html"), page(example.title, example.summary, body, url));
    cards.push(`<article class="example-card">${rendered?.preview ? `<a href="${url}" tabindex="-1" aria-hidden="true"><img src="${url}${rendered.preview}" alt="" loading="lazy"></a>` : ""}<div class="card-body"><p class="eyebrow">${kind}</p><h2><a href="${url}">${escape(example.title)}</a></h2><p>${escape(example.summary)}</p><p class="card-sources">${related.map(dataset => escape(dataset.title)).join(" · ")}</p></div></article>`);
  }
  const readme = await readFile(join(source, "README.md"), "utf8");
  const setup = readme.slice(readme.indexOf("## Run interactively"));
  if (!setup.startsWith("## Run interactively")) throw new Error("Missing examples setup instructions");
  const title = "Explore a question with real data";
  const body = `<header class="example-heading"><h1>${title}</h1><p class="example-intro">Follow an analysis from its source datasets to saved results, or start with a small manifest. Every example includes code you can run yourself.</p><a href="#run-examples">Set up and run examples</a></header><div class="example-grid">${cards.join("\n")}</div><section id="run-examples" class="prose examples-setup"><h2>Run the examples yourself</h2>${renderMarkdown(setup)}</section>`;
  await writeFile(join(destination, "index.html"), page(title, "Runnable scientific data examples with saved results, source datasets, and reproducible inputs.", body, "/examples/"));
  return catalog.length;
}
