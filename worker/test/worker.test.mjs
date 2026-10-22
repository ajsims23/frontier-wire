import { test } from "node:test";
import assert from "node:assert/strict";
import { buildIndex } from "../../site/search.js";
import { answer, matchSubscriber } from "../src/index.js";

const index = buildIndex([
  { id: "a", h: "DeepSeek raises $15 billion", s: "From CATL and Tencent.", d: "2026-10-22" },
  { id: "b", h: "EU AI Act enforcement begins", s: "Rules for general-purpose models.", d: "2026-10-10" },
]);

test("answers keep only real citations", async () => {
  const fake = async () => "DeepSeek raised about $15 billion [1]. Something else [7]. Both [1, 9].";
  const r = await answer({}, "how much did deepseek raise", index, fake);
  assert.equal(r.answer, "DeepSeek raised about $15 billion [1]. Something else . Both [1].");
  assert.equal(r.sources[0].id, "a");
  assert.equal(r.sources[0].cited, true);
});

test("no matching stories means no AI call", async () => {
  let called = false;
  const r = await answer({}, "quantum knitting", index, async () => { called = true; return "x"; });
  assert.equal(called, false);
  assert.equal(r.sources.length, 0);
});

test("subscribers only get events they follow", () => {
  const events = [{ key: "story:a", title: "A", follows: ["lab:DeepSeek", "deals"] }, { key: "story:b", title: "B", follows: ["tracker:ai-regulation"] }];
  const got = matchSubscriber(["deals"], events, { deals: "AI deals" });
  assert.deepEqual(got.map((e) => [e.key, e.because]), [["story:a", "AI deals"]]);
});
