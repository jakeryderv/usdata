import assert from "node:assert/strict";
import { readFile, readdir, mkdtemp, rm, access } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import test, { after, before } from "node:test";
import { renderNotebook, renderMarkdown } from "../notebook.mjs";
import { buildSite } from "../build.mjs";
import { firstSentence } from "../render-datasets.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const exists = async path => access(path).then(() => true, () => false);
const catalog = JSON.parse(await readFile(join(root, "web/public/datasets/catalog.json"), "utf8"));
const examples = JSON.parse(await readFile(join(root, "examples/catalog.json"), "utf8"));
const implemented = catalog.datasets.filter(dataset => dataset.availability !== "Planned");
let output;
let built;

before(async () => {
  output = await mkdtemp(join(tmpdir(), "usdata-site-"));
  built = await buildSite(output, root);
});
after(async () => rm(output, {recursive: true, force: true}));

async function htmlFiles(directory, prefix = "") {
  const files = [];
  for (const entry of await readdir(directory, {withFileTypes: true})) {
    const path = join(prefix, entry.name);
    if (entry.isDirectory()) files.push(...await htmlFiles(join(directory, entry.name), path));
    else if (entry.name.endsWith(".html")) files.push(path);
  }
  return files;
}

test("every implemented dataset has a page and every study has one", async () => {
  assert.equal(built.datasets, implemented.length);
  assert.equal(built.studies, examples.studies.length);
  for (const dataset of implemented) {
    const html = await readFile(join(output, new URL(dataset.page).pathname, "index.html"), "utf8");
    assert.ok(html.includes(`<h1>${dataset.title.replaceAll("&", "&amp;").replaceAll("'", "&#39;")}</h1>`), dataset.id);
    assert.match(html, /id="quick-start"/, dataset.id);
    if (dataset.walkthrough) assert.match(html, /id="walkthrough"/, dataset.id);
    for (const slug of dataset.studies) assert.ok(html.includes(`href="/studies/${slug}/"`), `${dataset.id}: ${slug}`);
  }
  for (const study of examples.studies) {
    const html = await readFile(join(output, "studies", study.slug, "index.html"), "utf8");
    for (const dataset of implemented.filter(d => d.studies.includes(study.slug))) {
      assert.ok(html.includes(`href="${new URL(dataset.page).pathname}"`), `${study.slug}: ${dataset.id}`);
    }
  }
});

test("downloads keep their source bytes, and only pinned lockfiles are published", async () => {
  const pinned = new Set(examples.pinned);
  const folders = [
    ...implemented.filter(d => d.walkthrough).map(d => ["datasets", d.walkthrough.split("/")[2], new URL(d.page).pathname]),
    ...examples.studies.map(s => ["studies", s.slug, `/studies/${s.slug}/`]),
  ];
  for (const [kind, folder, url] of folders) {
    const source = join(root, "examples", kind, folder);
    const files = await readdir(source);
    for (const name of [`${folder}.ipynb`, "dataset.yaml", "dataset.lock.json"].filter(n => files.includes(n))) {
      const published = join(output, url, name);
      if (name === "dataset.lock.json" && !pinned.has(`${kind}/${folder}`)) {
        assert.ok(!await exists(published), `${folder}: an unpinned lockfile must not be published`);
        continue;
      }
      assert.deepEqual(await readFile(published), await readFile(join(source, name)), `${folder}/${name}`);
    }
    if (files.includes(`${folder}.ipynb`)) {
      const notebook = JSON.parse(await readFile(join(source, `${folder}.ipynb`), "utf8"));
      for (const [cellIndex, cell] of notebook.cells.entries()) {
        for (const [outputIndex, result] of (cell.outputs ?? []).entries()) {
          const encoded = result.data?.["image/png"];
          if (encoded) assert.deepEqual(await readFile(join(output, url, `plot-${cellIndex}-${outputIndex}.png`)), Buffer.from(Array.isArray(encoded) ? encoded.join("") : encoded, "base64"));
        }
      }
    }
  }
});

test("every page has one h1, the shared shell, and only links that resolve", async () => {
  for (const file of await htmlFiles(output)) {
    const html = await readFile(join(output, file), "utf8");
    const base = `https://usdata.dev/${file.replace(/index\.html$/, "")}`;
    assert.equal((html.match(/<h1[ >]/g) ?? []).length, 1, file);
    assert.match(html, /href="\/tokens\.css"/, file);
    for (const match of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
      const url = new URL(match[1].replaceAll("&amp;", "&"), base);
      if (url.origin !== "https://usdata.dev") continue;
      const path = decodeURIComponent(url.pathname).slice(1) + (url.pathname.endsWith("/") ? "index.html" : "");
      assert.ok(await exists(join(output, path)), `${file}: missing ${url.href}`);
      if (url.hash && path.endsWith(".html")) {
        const content = await readFile(join(output, path), "utf8");
        assert.ok(content.includes(`id="${decodeURIComponent(url.hash.slice(1))}"`), `${file}: missing anchor ${url.href}`);
      }
    }
  }
});

test("retired /examples/ URLs redirect to pages that exist", async () => {
  const lines = (await readFile(join(output, "_redirects"), "utf8")).trim().split("\n");
  const table = JSON.parse(await readFile(join(root, "web/redirects.json"), "utf8"));
  for (const [from, to] of Object.entries(table)) {
    assert.ok(lines.includes(`${from} ${to} 301`), from);
    assert.ok(await exists(join(output, to, "index.html")), to);
  }
  assert.ok(lines.every(line => /^\/examples(\/\S*)? \/(datasets|studies)\/(\S*\/)? 301$/.test(line)), "redirect syntax");
  // Production applies an exact rule only when no splat rule precedes it.
  const firstSplat = lines.findIndex(line => line.split(" ")[0].endsWith("*"));
  assert.ok(lines.slice(firstSplat).every(line => line.split(" ")[0].endsWith("*")), "exact rules first");
  assert.equal(lines.at(-1), "/examples/* /studies/ 301");
});

test("the grid lists every dataset and hides planned ones until asked", async () => {
  const html = await readFile(join(output, "datasets/index.html"), "utf8");
  for (const dataset of catalog.datasets) assert.ok(html.includes(`data-id="${dataset.id}"`), dataset.id);
  assert.equal((html.match(/class="dataset-card planned"/g) ?? []).length, catalog.datasets.length - implemented.length);
  assert.ok(html.includes(`${implemented.length} datasets from`));
});

test("saved outputs preserve tables and escape code without publishing active HTML", async () => {
  const notebook = {cells: [{cell_type:"code", execution_count:1, source:"<script>not code to run</script>", outputs:[{output_type:"display_data", data:{"text/html":'<style>body {display:none}</style><script>alert(1)</script><table><tr><td>42</td></tr></table><img src="x" onerror="alert(1)">', "text/plain":"fallback"}}]}]};
  const {html} = await renderNotebook(notebook, tmpdir(), "Test");
  assert.match(html, /<td>42<\/td>/);
  assert.match(html, /&lt;script&gt;/);
  assert.ok(!/<script|<style|onerror=/.test(html));
  assert.ok(!html.includes("fallback"));
  assert.ok(!renderMarkdown('[bad](javascript:alert(1))').includes('href="javascript:'));
});

test("missing, failed, and unsupported notebook results stop the build", async () => {
  for (const outputs of [[], [{output_type:"error", traceback:["failed"]}], [{output_type:"display_data", data:{"application/javascript":"alert(1)"}}]]) {
    await assert.rejects(renderNotebook({cells:[{cell_type:"code", execution_count:1, source:"pass", outputs}]}, tmpdir(), "Test"));
  }
});

test("the preview is the one PNG from the cell tagged preview", async () => {
  const png = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, 0]).toString("base64");
  const cell = (tags, images = 1) => ({cell_type: "code", execution_count: 1, metadata: {tags}, source: "plot()", outputs: Array.from({length: images}, () => ({output_type: "display_data", data: {"image/png": png}}))});
  const tagged = await renderNotebook({cells: [cell([]), cell(["preview"])]}, tmpdir(), "Test", {strictPreview: true});
  assert.equal(tagged.preview, "plot-1-0.png");
  assert.equal((await renderNotebook({cells: [cell([]), cell([])]}, tmpdir(), "Test")).preview, "plot-0-0.png");
  await assert.rejects(renderNotebook({cells: [cell([])]}, tmpdir(), "Test", {strictPreview: true}), /exactly one code cell preview/);
  await assert.rejects(renderNotebook({cells: [cell(["preview"], 2)]}, tmpdir(), "Test", {strictPreview: true}), /exactly one PNG/);
});

test("a lede is the description's first sentence", () => {
  assert.equal(firstSentence("NCEI's archive since 1950. Anonymous files."), "NCEI's archive since 1950.");
  assert.equal(firstSentence("Station data, e.g. rain."), "Station data, e.g. rain.");
});
