import { cp, mkdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { buildExamples } from "./render-examples.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));

/** Build the whole website into `output`, a disposable directory. Returns the number of examples. */
export async function buildSite(output) {
  await rm(output, { recursive: true, force: true });
  await mkdir(output, { recursive: true });
  await cp(new URL("./public/", import.meta.url), output, { recursive: true });
  await cp(new URL("./_headers", import.meta.url), `${output}/_headers`);
  // One copy of the design tokens, shared with the docs (ADR 0041).
  await cp(new URL("../docs/assets/tokens.css", import.meta.url), `${output}/tokens.css`);
  return buildExamples(root, output);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const count = await buildSite(fileURLToPath(new URL("./dist", import.meta.url)));
  console.log(`Built homepage and ${count} examples in web/dist/`);
}
