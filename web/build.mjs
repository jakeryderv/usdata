import { cp, mkdir, rm } from "node:fs/promises";

const output = new URL("./dist/", import.meta.url);
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(new URL("./public/", import.meta.url), output, { recursive: true });
await cp(new URL("./_headers", import.meta.url), new URL("_headers", output));
console.log("Built homepage in web/dist/");
