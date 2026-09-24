import assert from "node:assert/strict";
import { readFile, mkdtemp, rm, access } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { buildSite } from "../build.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const exists = async path => access(path).then(() => true, () => false);

test("the homepage only links to and embeds files that exist on the built site", async () => {
  const output = await mkdtemp(join(tmpdir(), "usdata-home-"));
  try {
    await buildSite(output);
    const html = await readFile(join(root, "web/public/index.html"), "utf8");
    assert.equal((html.match(/<h1[ >]/g) ?? []).length, 1);
    assert.match(html, /<img[^>]+src="\/examples\/[^"]+\.png"/);
    for (const match of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
      const url = new URL(match[1], "https://usdata.dev/");
      if (url.origin !== "https://usdata.dev") continue;
      const path = url.pathname.slice(1) + (url.pathname.endsWith("/") ? "index.html" : "");
      const built = join(output, path);
      const target = await exists(built) ? built : join(root, "web/public", path);
      assert.ok(await exists(target), `homepage: missing ${url.href}`);
    }
  } finally { await rm(output, {recursive:true, force:true}); }
});
