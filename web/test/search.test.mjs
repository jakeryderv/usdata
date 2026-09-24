import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { matches } from "../public/datasets/search.js";

const catalog = JSON.parse(await readFile(new URL("../public/datasets/catalog.json", import.meta.url)));
const search = state => catalog.datasets.filter(dataset => matches(dataset, state));

test("familiar search words find usable scientific datasets", () => {
  for (const [query, id] of [["rainfall", "noaa:ghcn-daily"], ["hurricanes", "noaa:hurdat2"], ["streamflow", "usgs:water-daily"], ["  NOAA temperature  ", "noaa:gsom"]]) {
    assert.ok(search({ query }).some(dataset => dataset.id === id), query);
  }
});

test("planned entries appear only when asked for", () => {
  assert.ok(search({}).length > 0);
  assert.ok(search({}).every(dataset => dataset.availability !== "Planned"));
  assert.equal(search({ agency: "NASA" }).length, 0);
  assert.ok(search({ agency: "NASA", planned: true }).length > 0);
  assert.equal(search({ planned: true }).length, catalog.datasets.length);
});

test("combined filters and empty queries have predictable results", () => {
  assert.ok(search({ agency: "USGS" }).every(dataset => dataset.provider === "USGS"));
  assert.equal(search({ agency: "USGS", query: "hurricanes" }).length, 0);
  assert.ok(search({ topic: "Weather radar" }).every(dataset => dataset.domain === "Weather radar"));
  assert.equal(search({ topic: "Weather radar", query: "streamflow" }).length, 0);
  assert.equal(search({ query: "does-not-exist" }).length, 0);
  assert.deepEqual(search({ query: " \t " }), search({}));
  assert.equal(search({ query: "<script>alert(1)</script>" }).length, 0);
});

test("every implemented dataset has a page, docs destinations, and a quick start or its walkthrough's absence", () => {
  for (const dataset of search({})) {
    assert.ok(dataset.selection && dataset.inputs && dataset.formats.length);
    assert.match(dataset.page, /^https:\/\/usdata\.dev\/datasets\/[a-z]+\/[a-z0-9-]+\/$/);
    assert.ok(dataset.walkthrough || dataset.studies.length);
    if (dataset.walkthrough && dataset.quickstart) assert.ok(dataset.quickstart.cli.startsWith(`usdata fetch ${dataset.id}`));
    for (const url of [dataset.reference, dataset.guide]) {
      assert.equal(new URL(url).origin, "https://docs.usdata.dev");
      assert.ok(url.endsWith("/"));
      assert.ok(!url.endsWith("README/"));
    }
  }
});
