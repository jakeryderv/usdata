import { env } from "cloudflare:test";
import { expect, it } from "vitest";
import worker from "../src/worker";

it("serves the independent homepage and real missing-page responses", async () => {
  const home = await worker.fetch(new Request("https://usdata.dev/"), env);
  expect(home.status).toBe(200);
  expect(await home.text()).toContain("Public science.");
  for (const path of ["/absent/", "/versions.json", "/startling/"]) {
    expect(
      (await worker.fetch(new Request(`https://usdata.dev${path}`), env))
        .status,
    ).toBe(404);
  }
  const head = await worker.fetch(
    new Request("https://usdata.dev/", { method: "HEAD" }),
    env,
  );
  expect(await head.text()).toBe("");
  expect(
    (
      await worker.fetch(
        new Request("https://usdata.dev/", { method: "POST" }),
        env,
      )
    ).status,
  ).toBe(405);
});

it("redirects former docs URLs without losing paths or queries", async () => {
  for (const path of [
    "/start/",
    "/docs/reference/api/",
    "/latest/docs/reference/readers/",
    "/0.10.0/docs/reference/readers/",
    "/examples/",
    "/CHANGELOG/",
    "/project/",
  ]) {
    const response = await worker.fetch(
      new Request(`https://usdata.dev${path}?q=test`),
      env,
    );
    expect(response.status).toBe(302);
    expect(response.headers.get("Location")).toBe(
      `https://docs.usdata.dev${path}?q=test`,
    );
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  }
});
