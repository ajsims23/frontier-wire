import { test } from "node:test";
import assert from "node:assert/strict";
import { buildIndex, rank, tokens } from "../../site/search.js";

const docs = [
  { id: "a", h: "DeepSeek raises $15 billion", s: "Chinese AI startup DeepSeek raised funds from CATL and Tencent.", d: "2026-10-22", l: "DeepSeek" },
  { id: "b", h: "EU AI Act enforcement begins", s: "The EU starts enforcing rules for general-purpose models.", d: "2026-10-10", l: "" },
  { id: "c", h: "Anthropic launches Claude Duet", s: "An agent for professionals.", d: "2026-10-21", l: "Anthropic" },
];

test("tokens drop stop words and keep money", () => {
  assert.deepEqual(tokens("What did DeepSeek raise? $15 billion"), ["deepseek", "raise", "$15", "billion"]);
});

test("rank finds the right story", () => {
  const idx = buildIndex(docs);
  assert.equal(rank(idx, "how much did deepseek raise")[0].doc.id, "a");
  assert.equal(rank(idx, "EU regulation AI Act")[0].doc.id, "b");
  assert.deepEqual(rank(idx, "the of and"), []);
});
