// One example folder (a walkthrough or a study) rendered into a page directory (ADR 0041).
import { readFile, readdir, mkdir, copyFile } from "node:fs/promises";
import { join } from "node:path";
import { renderNotebook } from "./notebook.mjs";

const REPOSITORY = "https://github.com/jakeryderv/usdata/tree/main/examples";
// Beside the notebook: its manifest, a committed lockfile, and dated source metadata it cites.
const ALLOWED = new Set(["dataset.yaml", "dataset.lock.json", "metadata.json"]);

/**
 * Copy the example's downloads into `output` and render its notebook. `kind` is
 * "datasets" or "studies"; `folder` is the example folder's name. The folder
 * holds exactly its notebook, named after it, its manifest, and at most its
 * lockfile; the notebook tags exactly one preview cell.
 */
export async function renderExample(root, kind, folder, output, {title, pinned = false, codeOpen = false}) {
  const source = join(root, "examples", kind, folder);
  const files = (await readdir(source)).filter(name => !name.startsWith("."));
  const notebook = `${folder}.ipynb`;
  const unexpected = files.filter(name => name !== notebook && !ALLOWED.has(name));
  if (!files.includes(notebook) || !files.includes("dataset.yaml") || unexpected.length) {
    throw new Error(`examples/${kind}/${folder}: hold ${notebook} and dataset.yaml (found ${files.join(", ")})`);
  }
  if (pinned && !files.includes("dataset.lock.json")) throw new Error(`examples/${kind}/${folder}: pinned example has no committed lockfile`);
  await mkdir(output, {recursive: true});
  const labels = {[notebook]: "Notebook", "dataset.yaml": "Manifest", "dataset.lock.json": "Lockfile"};
  const downloads = [];
  for (const name of [notebook, "dataset.yaml", pinned ? "dataset.lock.json" : null].filter(Boolean)) {
    await copyFile(join(source, name), join(output, name));
    downloads.push(`<a class="button small" href="${name}" download>${labels[name]} <span aria-hidden="true">↓</span></a>`);
  }
  downloads.push(`<a class="button small ghost" href="${REPOSITORY}/${kind}/${folder}">Source <span aria-hidden="true">↗</span></a>`);
  const rendered = await renderNotebook(JSON.parse(await readFile(join(source, notebook), "utf8")), output, title, {codeOpen, strictPreview: true});
  return {
    downloads: `<div class="downloads" aria-label="Downloads">${downloads.join("")}</div>`,
    article: `<article class="prose notebook">${rendered.html}</article>`,
    preview: rendered.preview,
  };
}
