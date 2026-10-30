import { test } from "node:test";
import assert from "node:assert/strict";
import { coverText, digestSubject, imageFor, renderEmail, tidy } from "../src/email.js";

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

test("covers are drawn in HTML from the story's key fact", () => {
  assert.equal(coverText({ cover: "$15 billion" }), "$15 billion");
  assert.equal(coverText({ title: "DeepSeek raises $15 billion in funding" }), "$15B");
  assert.equal(coverText({ title: "AI tools find bugs in 70% of websites" }), "70%");
  const html = renderEmail({ site, api: "x", events: [{ key: "story:a1", title: "Lab ships Nova 2", summary: "s", url: `${site}story/a1/`, lab: "Example Lab", category: "models" }], kind: "alert" });
  assert.ok(html.includes("EXAMPLE LAB") && html.includes(">Nova<") === false && !html.includes("<img"));
});

test("welcome emails open with an introduction", () => {
  const html = renderEmail({ site, api: "x", events: events.slice(0, 1), kind: "welcome", intro: { title: "You're in.", text: "Following OpenAI." } });
  assert.ok(html.includes("You&#39;re in.") && html.includes("Following OpenAI.") && html.includes(">Welcome<"));
});

import { recapSubject, renderRecap } from "../src/email.js";

const recap = {
  date: "2026-10-30", human: "30 October 2026", hook: "Chip financing, a $15B buyout <b>", seconds: 30,
  summary: ["One.", "Two.", "Three."], page_url: `${site}videos/2026-10-30/`, gif_url: `${site}videos/2026-10-30/teaser.gif`,
  poster_url: `${site}videos/2026-10-30/poster.jpg`,
  entries: [{ line: "Line one", detail: "Detail one", source: "Bloomberg", category: "industry", url: `${site}story/a/` },
            { line: "Line two", detail: "Detail two", source: "Mistral AI", category: "models", url: "" }],
};

test("recap email: poster links to the video, five lines, button, unsubscribe; escaped", () => {
  const html = renderRecap({ site, api: "https://api.example", recap, unsub: "tok" });
  assert.ok(html.includes(`href="${site}videos/2026-10-30/"><img src="${site}videos/2026-10-30/teaser.gif"`));
  assert.ok(html.includes("Line one") && html.includes("Source: Mistral AI") && html.includes(`href="${site}story/a/"`));
  assert.ok(html.includes("Read on Frontier Wire") && html.includes("api.example/api/unsubscribe?t=tok"));
  assert.ok(!html.includes("<b>") && html.includes("&lt;b&gt;"));
  assert.ok(!html.includes("Approve and send"));
  assert.equal(recapSubject(recap), "Today in AI: Chip financing, a $15B buyout <b>");
});

test("recap preview carries the approve button and no unsubscribe link", () => {
  const html = renderRecap({ site, api: "https://api.example", recap, approveUrl: "https://api.example/api/recap/approve?d=2026-10-30&s=ab", audience: 3 });
  assert.ok(html.includes("Approve and send to subscribers") && html.includes("3 subscribers") && !html.includes("/api/unsubscribe"));
});
