import {
  env,
  createExecutionContext,
  waitOnExecutionContext,
} from "cloudflare:test";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import worker from "../src/worker";
import { KEY, digest, safePath } from "../src/catalog";
import { synchronize } from "../src/import";
const responses = new Map<string, Response>();
const fetchMock = {
  get(origin: string) {
    return {
      intercept({ path }: { path: string }) {
        return {
          reply(status: number, body: unknown) {
            responses.set(
              origin + path,
              body instanceof ArrayBuffer
                ? new Response(body, { status })
                : Response.json(body, { status }),
            );
          },
        };
      },
    };
  },
};
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
  responses.clear();
  vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
    const url = String(input);
    const response = responses.get(url);
    if (!response) throw new Error("Unexpected network request: " + url);
    responses.delete(url);
    return response;
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
  expect([...responses.keys()]).toEqual([]);
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
it("serves a useful unavailable state before the first complete import", async () => {
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
async function mockRelease(corrupt = false) {
  const version = "0.11.0";
  const files = await Promise.all(
    ["index.html", "404.html"].map(async (path) => {
      const body = new TextEncoder().encode("<main>Released</main>");
      return {
        path,
        type: "text/html",
        data: btoa("<main>Released</main>"),
        sha256: await digest(body),
      };
    }),
  );
  const body = new TextEncoder().encode(
    files.map((f) => JSON.stringify(f)).join("\n") + "\n",
  );
  const compressed = new Uint8Array(
    await new Response(
      new Blob([body]).stream().pipeThrough(new CompressionStream("gzip")),
    ).arrayBuffer(),
  );
  const name = `usdata-docs-${commit}`,
    base = "https://github.com/jakeryderv/usdata/releases/download/v0.11.0/";
  const assets = [
    {
      name: name + ".json",
      browser_download_url: base + name + ".json",
      size: 400,
      updated_at: "2026-09-09T00:00:00Z",
    },
    {
      name: name + ".ndjson.gz",
      browser_download_url: base + name + ".ndjson.gz",
      size: compressed.length,
    },
  ];
  fetchMock
    .get("https://pypi.org")
    .intercept({ path: "/pypi/usdata/json" })
    .reply(200, { info: { version } });
  fetchMock
    .get("https://pypi.org")
    .intercept({ path: "/pypi/usdata/0.11.0/json" })
    .reply(200, {});
  fetchMock
    .get("https://api.github.com")
    .intercept({
      path: "/repos/jakeryderv/usdata/releases?per_page=100&page=1",
    })
    .reply(200, [
      { tag_name: "v" + version, draft: false, prerelease: false, assets },
    ]);
  fetchMock
    .get("https://github.com")
    .intercept({
      path: "/jakeryderv/usdata/releases/download/v0.11.0/" + name + ".json",
    })
    .reply(200, {
      schema: 1,
      version,
      package_commit: commit,
      docs_commit: commit,
      files: 2,
      bundle: {
        name: name + ".ndjson.gz",
        size: compressed.length,
        sha256: corrupt ? "f".repeat(64) : await digest(compressed),
      },
    });
  fetchMock
    .get("https://github.com")
    .intercept({
      path:
        "/jakeryderv/usdata/releases/download/v0.11.0/" + name + ".ndjson.gz",
    })
    .reply(200, compressed.buffer);
}
it("imports validated files then advances current while preserving old snapshots", async () => {
  await seed();
  await mockRelease();
  await synchronize(env);
  const catalog = await (await env.DOCS.get(KEY))!.json<any>();
  expect(catalog.current).toBe("0.11.0");
  expect(catalog.versions["0.10.0"]).toBeTruthy();
  expect(
    await (await env.DOCS.get(
      catalog.versions["0.11.0"].prefix + "index.html",
    ))!.text(),
  ).toBe("<main>Released</main>");
});
it("keeps current docs available when an archive fails verification", async () => {
  await seed();
  await mockRelease(true);
  await expect(synchronize(env)).rejects.toThrow("checksum");
  expect((await (await env.DOCS.get(KEY))!.json<any>()).current).toBe("0.10.0");
});
