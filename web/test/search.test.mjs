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

test("planned entries cannot appear as ready to use", () => {
  assert.ok(search({}).length > 0);
  assert.ok(search({}).every(dataset => dataset.availability !== "Planned"));
  assert.equal(search({ provider: "NASA" }).length, 0);
  assert.ok(search({ provider: "NASA", availability: "Planned" }).length > 0);
  assert.equal(search({ availability: "all" }).length, catalog.datasets.length);
});

test("combined filters and empty queries have predictable results", () => {
  assert.ok(search({ provider: "USGS" }).every(dataset => dataset.provider === "USGS"));
  assert.equal(search({ provider: "USGS", query: "hurricanes" }).length, 0);
  assert.equal(search({ query: "does-not-exist" }).length, 0);
  assert.deepEqual(search({ query: " \t " }), search({}));
  assert.equal(search({ query: "<script>alert(1)</script>" }).length, 0);
});

test("every implemented dataset has usable reference and example destinations", () => {
  for (const dataset of search({})) {
    assert.ok(dataset.selection && dataset.inputs && dataset.formats.length);
    assert.ok(dataset.examples.length);
    for (const url of [dataset.reference, dataset.guide, ...dataset.examples.map(example => example.url)]) {
      assert.equal(new URL(url).origin, "https://docs.usdata.dev");
      assert.ok(url.endsWith("/"));
      assert.ok(!url.endsWith("README/"));
    }
  }
});
