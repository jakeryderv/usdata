import { env } from "cloudflare:test";
import { expect, it } from "vitest";
import worker from "../src/worker";

const request = (path: string, host = "usdata.dev", method = "GET") =>
  worker.fetch(new Request(`https://${host}${path}`, { method }), env);

it("serves the integrated home, docs, search index, and frozen archive", async () => {
  for (const path of [
    "/",
    "/start/",
    "/search/search_index.json",
    "/0.10.0/",
  ]) {
    const response = await request(path);
    expect(response.status, path).toBe(200);
  }
  expect(await (await request("/")).text()).toContain("Public science.");
  expect(await (await request("/0.10.0/")).text()).toContain(
    "Archived documentation",
  );
  expect((await request("/0.10.0/absent/")).status).toBe(404);
  expect((await request("/absent/")).status).toBe(404);
});

it("preserves old release paths and queries when redirecting the docs hostname", async () => {
  const response = await request(
    "/0.10.0/docs/reference/api/?q=test",
    "docs.usdata.dev",
  );
  expect(response.status).toBe(301);
  expect(response.headers.get("Location")).toBe(
    "https://usdata.dev/0.10.0/docs/reference/api/?q=test",
  );
  expect((await request("/", "docs.usdata.dev")).headers.get("Location")).toBe(
    "https://usdata.dev/start/",
  );
});

it("maps the latest alias to current docs without redirect loops", async () => {
  for (const host of ["usdata.dev", "docs.usdata.dev"]) {
    expect((await request("/latest/", host)).headers.get("Location")).toBe(
      "https://usdata.dev/start/",
    );
    const target = (
      await request("/latest/docs/reference/readers/", host)
    ).headers.get("Location");
    expect(target).toBe("https://usdata.dev/docs/reference/readers/");
    expect((await worker.fetch(new Request(target!), env)).status).toBe(200);
  }
});

it("keeps the archive compatibility catalog explicit, rejects writes, and handles HEAD", async () => {
  expect(await (await request("/versions.json")).json()).toEqual({
    current: "0.10.0",
    versions: ["0.10.0"],
    archived: true,
  });
  expect((await request("/", "usdata.dev", "POST")).status).toBe(405);
  expect(await (await request("/", "usdata.dev", "HEAD")).text()).toBe("");
});
