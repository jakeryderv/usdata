import { cp, mkdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { buildExamples } from "./render-examples.mjs";

const output = new URL("./dist/", import.meta.url);
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(new URL("./public/", import.meta.url), output, { recursive: true });
await cp(new URL("./_headers", import.meta.url), new URL("_headers", output));
const count = await buildExamples(fileURLToPath(new URL("../", import.meta.url)), fileURLToPath(output));
console.log(`Built homepage and ${count} examples in web/dist/`);
