import { test } from "node:test";
import assert from "node:assert/strict";
import { digestSubject, imageFor, renderEmail, tidy } from "../src/email.js";

const site = "https://example.github.io/fw/";
const events = [
  { key: "story:abc123", title: "Big model launch", summary: "Details.", url: `${site}story/abc123/`, tag: "Model release", because: "OpenAI" },
  { key: "tracker:copyright:2026-10-22T10", title: "Where things stand: AI and copyright", summary: "Old.", url: `${site}tracker/copyright/` },
  { key: "tracker:copyright:2026-10-22T14", title: "Where things stand: AI and copyright", summary: "New.", url: `${site}tracker/copyright/` },
  { key: "story:def456", title: "Big model launch", summary: "Same story twice.", url: `${site}story/def456/` },
  { key: "story:ghi789", title: "Second story <script>", summary: "x", url: `${site}story/ghi789/`, image: "https://img.example/p.jpg" },
];

test("one entry per tracker and no repeated headlines", () => {
  const t = tidy(events);
  assert.equal(t.filter((e) => e.key.startsWith("tracker:copyright")).length, 1);
  assert.equal(t.find((e) => e.key.startsWith("tracker:")).summary, "New.");
  assert.equal(t.filter((e) => e.title === "Big model launch").length, 1);
});

test("pictures: the story's own image, else its preview card", () => {
  assert.equal(imageFor(events[0], site), `${site}og/abc123.png`);
  assert.equal(imageFor(events[4], site), "https://img.example/p.jpg");
});

test("subject leads with the top story; html is escaped and complete", () => {
  assert.equal(digestSubject(tidy(events)), "Big model launch + 2 more");
  const html = renderEmail({ site, api: "https://api.example", events, briefing: { one_line: "Busy day.", themes: [] }, unsub: "tok", kind: "digest" });
  assert.ok(html.includes("Today in AI") && html.includes("Where things stand") && html.includes("api.example/api/unsubscribe?t=tok"));
  assert.ok(!html.includes("<script>") && html.includes("&lt;script&gt;"));
});
