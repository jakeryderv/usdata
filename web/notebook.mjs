// Render saved notebook content and Markdown into safe HTML. Nothing here executes code.
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import MarkdownIt from "markdown-it";
import sanitize from "sanitize-html";
import { escape } from "./layout.mjs";

const markdown = new MarkdownIt({ html: false });
markdown.renderer.rules.heading_open = (tokens, index, options, env, renderer) => {
  const label = tokens[index + 1].children.map(token => token.content).join("");
  tokens[index].attrSet("id", label.toLowerCase().replace(/[^a-z0-9\s-]/g, "").trim().replace(/\s+/g, "-"));
  return renderer.renderToken(tokens, index, options);
};
export const text = value => Array.isArray(value) ? value.join("") : value ?? "";
const clean = html => sanitize(html, {
  allowedTags: sanitize.defaults.allowedTags.concat(["img"]),
  allowedAttributes: {a: ["href", "title"], img: ["src", "alt", "title"], code: ["class"], th: ["colspan", "rowspan"], td: ["colspan", "rowspan"], h1: ["id"], h2: ["id"], h3: ["id"], h4: ["id"]},
  allowedSchemes: ["http", "https", "mailto"],
});
export const renderMarkdown = source => clean(markdown.render(source));
export const withoutTitle = source => source.replace(/^# [^\n]*\n+/, "");
export const firstHeading = source => source.match(/^# ([^\n]+)/)?.[1]?.trim() ?? null;
const pre = source => `<pre><code>${escape(source)}</code></pre>`;
const PNG = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

/**
 * Render only saved, supported output types, writing each saved PNG beside the page.
 *
 * Returns the HTML, every PNG written, and the preview: the one PNG from the code
 * cell tagged `preview` (ADR 0041), else the first PNG. `strictPreview` refuses a
 * notebook without exactly one tagged cell holding exactly one PNG.
 */
export async function renderNotebook(notebook, directory, title, {codeOpen = false, strictPreview = false} = {}) {
  const cells = [];
  const images = [];
  let tagged = null;
  let taggedCells = 0;
  for (const [cellIndex, cell] of notebook.cells.entries()) {
    if (cell.cell_type === "markdown") {
      cells.push(`<section class="notebook-text">${renderMarkdown(cellIndex === 0 ? withoutTitle(text(cell.source)) : text(cell.source))}</section>`);
    } else if (cell.cell_type === "code") {
      if (cell.execution_count === null || !cell.outputs?.length) throw new Error(`${title}: missing saved execution in cell ${cellIndex}`);
      const isPreview = (cell.metadata?.tags ?? []).includes("preview");
      const outputs = [];
      const pngs = [];
      for (const [outputIndex, output] of cell.outputs.entries()) {
        if (output.output_type === "error") throw new Error(`${title}: saved error in cell ${cellIndex}`);
        const data = output.data ?? {};
        if (data["image/png"]) {
          const filename = `plot-${cellIndex}-${outputIndex}.png`;
          const bytes = Buffer.from(text(data["image/png"]), "base64");
          if (!bytes.subarray(0, 8).equals(PNG)) throw new Error(`${title}: invalid PNG`);
          await writeFile(join(directory, filename), bytes);
          images.push(filename);
          pngs.push(filename);
          outputs.push(`<figure><img src="${filename}" alt="Saved plot from ${escape(title)}" loading="lazy"></figure>`);
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
      if (isPreview) {
        taggedCells += 1;
        if (strictPreview && pngs.length !== 1) throw new Error(`${title}: the cell tagged preview must save exactly one PNG`);
        tagged ??= pngs[0] ?? null;
      }
      const source = pre(text(cell.source));
      const code = codeOpen ? `<div class="cell-code">${source}</div>` : `<details class="cell-code"><summary>Show code</summary>${source}</details>`;
      cells.push(`<section class="notebook-cell">${code}<div class="cell-output">${outputs.join("\n")}</div></section>`);
    } else {
      throw new Error(`${title}: unsupported cell type ${cell.cell_type}`);
    }
  }
  if (strictPreview && taggedCells !== 1) throw new Error(`${title}: tag exactly one code cell preview (found ${taggedCells})`);
  return {html: cells.join("\n"), images, preview: tagged ?? images[0] ?? null};
}
