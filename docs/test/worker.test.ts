import { env } from "cloudflare:test";
import { expect, it } from "vitest";
import worker from "../hosting/worker";

it("serves current MkDocs content with no archive or version catalog", async () => {
  for (const path of [
    "/",
    "/docs/reference/api/",
    "/docs/generated/cli/",
    "/search/search_index.json",
  ]) {
    const response = await worker.fetch(
      new Request(`https://docs.usdata.dev${path}`),
      env,
    );
    expect(response.status, path).toBe(200);
    expect(await response.text()).not.toContain("Archived documentation");
  }
  expect(
    (
      await worker.fetch(
        new Request("https://docs.usdata.dev/versions.json"),
        env,
      )
    ).status,
  ).toBe(404);
  expect(
    (await worker.fetch(new Request("https://docs.usdata.dev/absent/"), env))
      .status,
  ).toBe(404);
});

it("resolves retired aliases to a current page in one hop without a loop", async () => {
  for (const [path, target] of [
    ["/start/", "/"],
    ["/start", "/"],
    ["/docs/index.html", "/"],
    ["/0.10.0", "/"],
    ["/0.10.0/index.html", "/"],
    ["/latest/", "/"],
    ["/0.10.0/docs/reference/readers/", "/docs/reference/readers/"],
    ["/latest/docs/reference/readers/", "/docs/reference/readers/"],
  ]) {
    const response = await worker.fetch(
      new Request(`https://docs.usdata.dev${path}?q=test`),
      env,
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("Location")).toBe(
      `https://docs.usdata.dev${target}?q=test`,
    );
    const current = await worker.fetch(
      new Request(response.headers.get("Location")!),
      env,
    );
    expect(current.status).toBe(200);
    expect(current.headers.has("Location")).toBe(false);
  }
});

it("redirects repository policies to their canonical files, including old versions", async () => {
  for (const [path, file] of [
    ["/CONTRIBUTING/", "CONTRIBUTING.md"],
    ["/latest/SECURITY/index.html", "SECURITY.md"],
    ["/0.10.0/LICENSE", "LICENSE"],
    ["/changes/", "changes/README.md"],
  ]) {
    const response = await worker.fetch(
      new Request(`https://docs.usdata.dev${path}?q=test`),
      env,
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("Location")).toBe(
      `https://github.com/jakeryderv/usdata/blob/main/${file}?q=test`,
    );
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  }
});
