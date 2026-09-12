import assert from "node:assert/strict";
import { readFile, readdir, mkdtemp, rm, access } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { buildExamples, renderNotebook, renderMarkdown } from "../render-examples.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const exists = async path => access(path).then(() => true, () => false);

test("all examples keep their saved content, exact downloads, and valid website links", async () => {
  const output = await mkdtemp(join(tmpdir(), "usdata-examples-"));
  try {
    const catalog = JSON.parse(await readFile(join(root, "examples/catalog.json"), "utf8"));
    assert.equal(await buildExamples(root, output), catalog.length);
    const files = ["examples/index.html"];
    for (const example of catalog) {
      const directory = join(root, "examples", example.slug);
      const generated = join(output, "examples", example.slug);
      const sourceFiles = await readdir(directory);
      files.push(`examples/${example.slug}/index.html`);
      for (const download of ["example.ipynb", "dataset.yaml"].filter(name => sourceFiles.includes(name))) {
        assert.deepEqual(await readFile(join(generated, download)), await readFile(join(directory, download)));
      }
      if (sourceFiles.includes("example.ipynb")) {
        const notebook = JSON.parse(await readFile(join(directory, "example.ipynb"), "utf8"));
        for (const [cellIndex, cell] of notebook.cells.entries()) {
          for (const [outputIndex, result] of (cell.outputs ?? []).entries()) {
            if (result.data?.["image/png"]) {
              const encoded = result.data["image/png"];
              assert.deepEqual(await readFile(join(generated, `plot-${cellIndex}-${outputIndex}.png`)), Buffer.from(Array.isArray(encoded) ? encoded.join("") : encoded, "base64"));
            }
          }
        }
      }
    }
    for (const file of files) {
      const html = await readFile(join(output, file), "utf8");
      const base = `https://usdata.dev/${file.replace(/index\.html$/, "")}`;
      assert.equal((html.match(/<h1[ >]/g) ?? []).length, 1, file);
      assert.ok(!html.includes("https://docs.usdata.dev/examples/"), file);
      for (const match of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
        const url = new URL(match[1].replaceAll("&amp;", "&"), base);
        if (url.origin !== "https://usdata.dev") continue;
        const path = decodeURIComponent(url.pathname).slice(1) + (url.pathname.endsWith("/") ? "index.html" : "");
        const target = await exists(join(output, path)) ? join(output, path) : join(root, "web/public", path);
        assert.ok(await exists(target), `${file}: missing ${url.href}`);
        if (url.hash && path.endsWith(".html")) {
          const content = await readFile(target, "utf8");
          assert.ok(content.includes(`id="${decodeURIComponent(url.hash.slice(1))}"`), `${file}: missing anchor ${url.href}`);
        }
      }
    }
    const event = await readFile(join(output, "examples/event-context/index.html"), "utf8");
    for (const id of ["noaa:storm-events", "noaa:nexrad-level2", "noaa:goes-abi"]) assert.ok(event.includes(encodeURIComponent(id)));
    const climate = await readFile(join(output, "examples/climate-anomalies/index.html"), "utf8");
    assert.match(climate, /10 of 12 months/);
    assert.match(climate, /Checksum:/);
    assert.match(climate, /<table>/);
  } finally { await rm(output, {recursive:true, force:true}); }
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
