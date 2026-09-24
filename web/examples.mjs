// One example folder (a walkthrough or a study) rendered into a page directory (ADR 0041).
import { readFile, readdir, mkdir, copyFile } from "node:fs/promises";
import { join } from "node:path";
import { renderNotebook, renderMarkdown, withoutTitle } from "./notebook.mjs";

const REPOSITORY = "https://github.com/jakeryderv/usdata/tree/main/examples";

/**
 * Copy the example's downloads into `output` and render its notebook, or its
 * README while a walkthrough still has no notebook. `kind` is "datasets" or
 * "studies"; `folder` is the example folder's name.
 */
export async function renderExample(root, kind, folder, output, {title, pinned = false, codeOpen = false, strictPreview = false}) {
  const source = join(root, "examples", kind, folder);
  const files = await readdir(source);
  const notebooks = files.filter(name => name.endsWith(".ipynb"));
  if (notebooks.length > 1 || (notebooks.length === 1 && notebooks[0] !== `${folder}.ipynb`)) {
    throw new Error(`examples/${kind}/${folder}: hold one notebook, named ${folder}.ipynb`);
  }
  const notebook = notebooks[0] ?? null;
  if (!notebook && !files.includes("README.md")) throw new Error(`examples/${kind}/${folder}: no notebook or README`);
  if (pinned && !files.includes("dataset.lock.json")) throw new Error(`examples/${kind}/${folder}: pinned example has no committed lockfile`);
  await mkdir(output, {recursive: true});
  const labels = {[`${folder}.ipynb`]: "Notebook", "dataset.yaml": "Manifest", "dataset.lock.json": "Lockfile"};
  const downloads = [];
  for (const name of [notebook, "dataset.yaml", pinned ? "dataset.lock.json" : null].filter(name => name && files.includes(name))) {
    await copyFile(join(source, name), join(output, name));
    downloads.push(`<a class="button small" href="${name}" download>${labels[name]} <span aria-hidden="true">↓</span></a>`);
  }
  downloads.push(`<a class="button small ghost" href="${REPOSITORY}/${kind}/${folder}">Source <span aria-hidden="true">↗</span></a>`);
  const readme = files.includes("README.md") ? await readFile(join(source, "README.md"), "utf8") : null;
  let article;
  let preview = null;
  if (notebook) {
    const rendered = await renderNotebook(JSON.parse(await readFile(join(source, notebook), "utf8")), output, title, {codeOpen, strictPreview});
    preview = rendered.preview;
    const guide = readme ? `<details class="run-guide"><summary>Run this ${kind === "studies" ? "study" : "walkthrough"}: instructions and limitations</summary><div class="prose">${renderMarkdown(withoutTitle(readme))}</div></details>` : "";
    article = `${guide}<article class="prose notebook">${rendered.html}</article>`;
  } else {
    article = `<article class="prose">${renderMarkdown(withoutTitle(readme))}</article>`;
  }
  return {
    downloads: `<div class="downloads" aria-label="Downloads">${downloads.join("")}</div>`,
    article,
    preview,
    notebook: Boolean(notebook),
  };
}
