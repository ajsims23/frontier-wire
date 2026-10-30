import { test } from "node:test";
import assert from "node:assert/strict";
import { buildIndex } from "../../site/search.js";
import { answer, matchSubscriber, parseNewsRss, searchTerms } from "../src/index.js";

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

test("questions our archive doesn't cover get a labelled general answer", async () => {
  const noWeb = async () => [];
  const r = await answer({}, "quantum knitting", index, async (env, msgs) => (msgs[0].content.includes("general knowledge") ? "Background." : "x"), noWeb);
  assert.equal(r.general, true);
  assert.equal(r.answer, "Background.");
  assert.equal(r.sources.length, 0);
  const r2 = await answer({}, "deepseek board members", index, async (env, msgs) => (msgs[0].content.includes("general knowledge") ? "General." : "NOT_COVERED"), noWeb);
  assert.equal(r2.general, true);
  assert.equal(r2.answer, "General.");
});

test("subscribers only get events they follow", () => {
  const events = [{ key: "story:a", title: "A", follows: ["lab:DeepSeek", "deals"] }, { key: "story:b", title: "B", follows: ["tracker:ai-regulation"] }];
  const got = matchSubscriber(["deals"], events, { deals: "AI deals" });
  assert.deepEqual(got.map((e) => [e.key, e.because]), [["story:a", "AI deals"]]);
});

test("full-width citations are normalised", async () => {
  const r = await answer({}, "deepseek", index, async () => "Raised $15 billion【1】 and more【1，2】.");
  assert.equal(r.answer, "Raised $15 billion[1] and more[1].");  // [2] wasn't among the stories it was given
  assert.equal(r.sources[0].cited, true);
});

test("news RSS parsing unwraps Bing links and cleans text", () => {
  const bing = parseNewsRss('<item><title>Bing story</title><link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fexample.com%2fa&amp;c=1</link><description>Snip &lt;b&gt;x&lt;/b&gt; &amp; more</description><pubDate>Thu, 22 Oct 2026 10:00:00 GMT</pubDate><News:Source>Example</News:Source></item>', "bing");
  assert.deepEqual(bing, [{ title: "Bing story", url: "https://example.com/a", publisher: "Example", date: "2026-10-22", snippet: "Snip x & more" }]);
  const g = parseNewsRss('<item><title>Big launch - Reuters</title><link>https://news.google.com/rss/articles/abc</link><pubDate>Wed, 21 Oct 2026 10:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>', "google");
  assert.equal(g[0].title, "Big launch");
  assert.equal(g[0].publisher, "Reuters");
});

test("uncovered questions use live news first, with real result citations", async () => {
  const web = async () => [{ title: "Tesla does a big thing", url: "https://example.com/t", publisher: "Example", date: "2026-10-22", snippet: "Details." }];
  const r = await answer({}, "tesla latest", index, async (env, msgs) => (msgs[0].content.includes("LIVE news") ? "Tesla did a big thing [1] and more [4]. Range [1‑1]." : "NOT_COVERED"), web);
  assert.equal(r.web, true);
  assert.equal(r.answer, "Tesla did a big thing [1] and more . Range [1].");
  assert.equal(r.sources[0].url, "https://example.com/t");
});

test("question words are dropped before searching the news", () => {
  assert.equal(searchTerms("what's going on with tesla?"), "tesla");
  assert.equal(searchTerms("Latest news about OpenAI GPT-7"), "openai gpt-7");
});

import { mergeFollows, signRecap } from "../src/index.js";

test("recap approval links are signed per date", async () => {
  const a = await signRecap("secret", "2026-10-30");
  assert.match(a, /^[0-9a-f]{32}$/);
  assert.equal(a, await signRecap("secret", "2026-10-30"));
  assert.notEqual(a, await signRecap("secret", "2026-10-31"));
  assert.notEqual(a, await signRecap("other", "2026-10-30"));
});

test("signing up for the recap adds to what a subscriber already follows", () => {
  const m = mergeFollows(["lab:OpenAI", "deals"], { "lab:OpenAI": "OpenAI" }, ["recap"], { recap: "the daily recap" });
  assert.deepEqual(m.follows, ["lab:OpenAI", "deals", "recap"]);
  assert.deepEqual(m.labels, { "lab:OpenAI": "OpenAI", recap: "the daily recap" });
});
