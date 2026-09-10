import {
  env,
  createExecutionContext,
  waitOnExecutionContext,
} from "cloudflare:test";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import worker from "../src/worker";
import { KEY, safePath } from "../src/catalog";
const sha = "a".repeat(64),
  commit = "b".repeat(40);
const snapshot = (version: string) => ({
  version,
  revision: sha,
  package_commit: commit,
  docs_commit: commit,
  prefix: `docs/${version}/${sha}/`,
});
beforeEach(async () => {
  const objects = await env.DOCS.list();
  for (const object of objects.objects) await env.DOCS.delete(object.key);
  vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
    throw new Error("Unexpected network request: " + String(input));
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
});
async function request(path: string, init?: RequestInit) {
  const ctx = createExecutionContext();
  const response = await worker.fetch(
    new Request("https://docs.example" + path, init),
    env,
    ctx,
  );
  await waitOnExecutionContext(ctx);
  return response;
}
async function seed(two = false) {
  await env.DOCS.put(
    KEY,
    JSON.stringify({
      schema: 1,
      current: two ? "0.11.0" : "0.10.0",
      versions: two
        ? { "0.10.0": snapshot("0.10.0"), "0.11.0": snapshot("0.11.0") }
        : { "0.10.0": snapshot("0.10.0") },
    }),
  );
  for (const version of ["0.10.0", "0.11.0"]) {
    await env.DOCS.put(
      snapshot(version).prefix + "index.html",
      "<html><body><main><h1>Start</h1></main></body></html>",
      { httpMetadata: { contentType: "text/html" } },
    );
    await env.DOCS.put(
      snapshot(version).prefix + "404.html",
      "<h1>Missing</h1>",
      { httpMetadata: { contentType: "text/html" } },
    );
  }
}
it("serves a useful unavailable state before the first complete publication", async () => {
  expect((await request("/")).status).toBe(503);
});
it("redirects to current docs and hides the single-version selector", async () => {
  await seed();
  expect((await request("/")).headers.get("Location")).toBe("/0.10.0/");
  expect((await request("/latest/docs/")).headers.get("Location")).toBe(
    "/0.10.0/docs/",
  );
  const html = await (await request("/0.10.0/")).text();
  expect(html).toContain("Documentation 0.10.0");
  expect(html).not.toContain("<select");
});
it("shows old-version notices and handles missing pages during version switching", async () => {
  await seed(true);
  expect(await (await request("/0.10.0/")).text()).toContain("Older version");
  expect(await (await request("/0.11.0/")).text()).toContain(
    "Documentation version",
  );
  expect(
    (await request("/0.11.0/absent/?from=0.10.0")).headers.get("Location"),
  ).toBe("/0.11.0/?missing=1");
  expect((await request("/0.11.0/absent/")).status).toBe(404);
  expect((await request("/0.9.0/")).status).toBe(404);
});
it("rejects writes and invalid object paths, and handles HEAD", async () => {
  await seed();
  expect((await request("/0.10.0/", { method: "POST" })).status).toBe(405);
  expect(await (await request("/0.10.0/", { method: "HEAD" })).text()).toBe("");
  for (const p of ["../secret", "/secret", "a//b", "a\\b", "a%2fb"])
    expect(safePath(p)).toBe(false);
});
