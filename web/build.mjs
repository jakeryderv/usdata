import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { buildDatasets, implemented, pagePath } from "./render-datasets.mjs";
import { buildStudies } from "./render-studies.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const SETUP = "## Run a notebook yourself";

/** The user-facing run instructions from examples/README.md, without their heading. */
export async function runInstructions(base = root) {
  const readme = await readFile(join(base, "examples/README.md"), "utf8");
  const start = readme.indexOf(SETUP);
  if (start < 0) throw new Error(`examples/README.md has no "${SETUP}" section`);
  const body = readme.slice(start + SETUP.length);
  const end = body.search(/\n## /);
  return (end < 0 ? body : body.slice(0, end)).trim();
}

/** Cloudflare `_redirects` lines for the retired /examples/ pages, each to a page that exists. */
export async function redirects(output) {
  const table = JSON.parse(await readFile(new URL("./redirects.json", import.meta.url), "utf8"));
  const lines = [];
  for (const [from, to] of Object.entries(table)) {
    const built = join(output, to, "index.html");
    await readFile(built).catch(() => { throw new Error(`redirect ${from} -> ${to}: no such page`); });
    lines.push(`${from} ${to} 301`, `${from.slice(0, -1)} ${to} 301`);
    if (from !== "/examples/") lines.push(`${from}* ${to} 301`);
  }
  return `${lines.join("\n")}\n/examples/* /studies/ 301\n`;
}

/** Build the whole website into `output`, a disposable directory. Returns page counts. */
export async function buildSite(output, base = root) {
  await rm(output, { recursive: true, force: true });
  await mkdir(output, { recursive: true });
  await cp(new URL("./public/", import.meta.url), output, { recursive: true });
  await cp(new URL("./_headers", import.meta.url), join(output, "_headers"));
  // One copy of the design tokens, shared with the docs (ADR 0041).
  await cp(join(base, "docs/assets/tokens.css"), join(output, "tokens.css"));
  const catalog = JSON.parse(await readFile(join(base, "web/public/datasets/catalog.json"), "utf8"));
  const examples = JSON.parse(await readFile(join(base, "examples/catalog.json"), "utf8"));
  const studies = await buildStudies(base, output, catalog, examples, await runInstructions(base));
  const previews = await buildDatasets(base, output, catalog, examples, studies);
  await writeFile(join(output, "_redirects"), await redirects(output));
  return { datasets: catalog.datasets.filter(implemented).length, studies: studies.size, previews, pagePath };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const built = await buildSite(fileURLToPath(new URL("./dist", import.meta.url)));
  console.log(`Built the homepage, ${built.datasets} dataset pages, and ${built.studies} studies in web/dist/`);
}
