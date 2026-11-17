import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { sourcePairs } from "../public/replay-charts.js";

test("Repeated site records do not inflate the company count", () => {
  const row = { a: { source_id: "a" }, b: { source_id: "b" }, canonical_entity_key: "company" };
  const [pair] = sourcePairs([row, row, { ...row, canonical_entity_key: "other" }]);
  assert.equal(pair.links, 3);
  assert.equal(pair.companies, 2);
});

test("Real source-pair totals distinguish records from businesses", () => {
  const data = JSON.parse(readFileSync(new URL("../data/raw-identity.json", import.meta.url)));
  const pairs = sourcePairs(data.links);
  const dewr = pairs.find(p => p.a === "acnc_charities" && p.b === "dewr_employment_providers");
  assert.equal(dewr.links, 304);
  assert.equal(dewr.companies, 45);
  assert.equal(pairs.reduce((n, p) => n + p.links, 0), data.links.length);
});

test("Profile pair filter counts are limited to the displayed sample", () => {
  const data = JSON.parse(readFileSync(new URL("../data/raw-profiles.json", import.meta.url)));
  for (const pair of sourcePairs(data.profiles, true)) {
    assert.equal(pair.companies, data.profiles.filter(p => p.sources.includes(pair.a) && p.sources.includes(pair.b)).length);
    assert.ok(pair.companies <= 50);
  }
});
