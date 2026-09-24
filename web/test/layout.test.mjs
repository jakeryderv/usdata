import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { NAV, nav } from "../layout.mjs";

const links = html => [...html.matchAll(/<nav aria-label="Main navigation">([\s\S]*?)<\/nav>/g)].map(match => [...match[1].matchAll(/<a href="([^"]+)"[^>]*>([^<]+)<\/a>/g)].map(link => [link[2], link[1]]));

test("handwritten pages share the generated pages' navigation, tokens, and fonts", async () => {
  for (const name of ["index.html", "404.html"]) {
    const html = await readFile(new URL(`../public/${name}`, import.meta.url), "utf8");
    assert.deepEqual(links(html), [NAV], name);
    assert.match(html, /href="\/tokens\.css"/, `${name}: tokens.css`);
    assert.match(html, /fonts\.googleapis\.com\/css2\?family=Inter/, `${name}: fonts`);
  }
  assert.deepEqual(links(nav("/datasets/")), [NAV]);
  assert.match(nav("/datasets/"), /href="\/datasets\/" aria-current="page"/);
});

test("the docs load the same token file and link back to the same sections", async () => {
  const mkdocs = await readFile(new URL("../../mkdocs.yml", import.meta.url), "utf8");
  assert.match(mkdocs, /extra_css:\n- assets\/tokens\.css\n/);
  const header = await readFile(new URL("../../docs/overrides/partials/header.html", import.meta.url), "utf8");
  for (const [label, href] of NAV.filter(([label]) => !["Docs", "GitHub"].includes(label))) {
    assert.ok(header.includes(`<a href="https://usdata.dev${href}">${label}</a>`), `docs header: ${label}`);
  }
});
