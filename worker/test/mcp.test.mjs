import { test } from "node:test";
import assert from "node:assert/strict";
import { buildIndex, rank } from "../../site/search.js";
import { handleMcp, TOOLS } from "../src/mcp.js";

const index = buildIndex([
  { id: "a", h: "Example Lab releases DocParse 2", s: "Open-source PDF table extraction.", d: "2026-11-20", x: "Could cut manual table capture.", m: "trial" },
  { id: "b", h: "EU AI Act enforcement begins", s: "Rules for general-purpose models.", d: "2026-11-10" },
]);
const env = { SITE_URL: "https://example.github.io/frontier-wire/" };
const files = {
  "api/v1/radar.json": { updated_at: "2026-11-21", rings: [], entries: [{ name: "DocParse 2", ring: "trial", proposed: "adopt", quadrant: "tools", cap_name: "Extraction",
    rationale: "Free and fits.", history: [{ date: "2026-11-21", from: "", to: "trial", why: "New." }], evidence: [{ id: "a" }] }] },
  "api/v1/dpa.json": { org: "DPA", brief: { headline: "Try one thing." }, act_on: [{ id: "a", capabilities: ["doc_extraction"] }, { id: "b", capabilities: ["governance"] }],
    roles: [{ id: "extraction", name: "Extraction", items: [] }] },
  "api/v1/bench.json": { tasks: [{ title: "T1", type: "extraction" }], latest: { date: "2026-11-22", models: [
    { model: "m1", provider: "p", available: true, score: 70, by_type: { extraction: 90 } }, { model: "m2", provider: "p", available: true, score: 80, by_type: { extraction: 60 } },
    { model: "m3", provider: "p", available: false }] } },
  "api/v1/system.json": { pipeline: { written: 10 }, corrections_log: [] },
};
globalThis.fetch = async (url) => {
  const path = String(url).replace(env.SITE_URL, "");
  return files[path] ? new Response(JSON.stringify(files[path])) : new Response("no", { status: 404 });
};
const deps = { getIndex: async () => index, rank, answer: async (e, q) => ({ answer: "DocParse 2 [1].", sources: [{ n: 1, id: "a", headline: "x", date: "d" }] }) };
const rpc = async (body) => {
  const r = await handleMcp(new Request("https://api/mcp", { method: "POST", body: JSON.stringify(body) }), env, deps);
  return { status: r.status, body: r.status === 202 ? null : await r.json() };
};

test("initialize, notifications and listing", async () => {
  const init = await rpc({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "t", version: "1" } } });
  assert.equal(init.body.result.protocolVersion, "2025-06-18");
  assert.ok(init.body.result.capabilities.tools);
  const odd = await rpc({ jsonrpc: "2.0", id: 2, method: "initialize", params: { protocolVersion: "1999-01-01" } });
  assert.equal(odd.body.result.protocolVersion, "2025-11-25");
  assert.equal((await rpc({ jsonrpc: "2.0", method: "notifications/initialized" })).status, 202);
  const list = await rpc({ jsonrpc: "2.0", id: 3, method: "tools/list" });
  assert.equal(list.body.result.tools.length, TOOLS.length);
  assert.ok(list.body.result.tools.every((t) => t.inputSchema.type === "object" && t.annotations.readOnlyHint));
  assert.equal((await rpc({ jsonrpc: "2.0", id: 4, method: "nope" })).body.error.code, -32601);
  const get = await handleMcp(new Request("https://api/mcp"), env, deps);
  assert.equal(get.status, 405);
});

test("tools answer from the site's data", async () => {
  const call = async (name, args) => (await rpc({ jsonrpc: "2.0", id: 9, method: "tools/call", params: { name, arguments: args } })).body.result;
  const s = await call("search_news", { query: "table extraction" });
  assert.equal(s.structuredContent.results[0].id, "a");
  assert.equal(s.structuredContent.results[0].dpa.move, "trial");
  assert.equal(s.structuredContent.results[0].page, "https://example.github.io/frontier-wire/story/a/");
  assert.ok(JSON.parse(s.content[0].text).results);
  const w = await call("what_changed", { since: "2026-11-15" });
  assert.equal(w.structuredContent.new_stories, 1);
  assert.equal(w.structuredContent.radar_moves[0].item, "DocParse 2");
  const r = await call("get_radar", { ring: "trial" });
  assert.equal(r.structuredContent.entries[0].proposed_for_adopt, true);
  const b = await call("best_model_for", { task_type: "extraction" });
  assert.deepEqual(b.structuredContent.ranking.map((x) => x.model), ["m1", "m2"]);
  const d = await call("dpa_brief", { capability: "governance" });
  assert.deepEqual(d.structuredContent.act_on.map((x) => x.id), ["b"]);
  const a = await call("ask_wire", { question: "what is docparse" });
  assert.equal(a.structuredContent.sources[0].page, "https://example.github.io/frontier-wire/story/a/");
  const bad = await call("search_news", {});
  assert.equal(bad.isError, true);
  const unknown = await rpc({ jsonrpc: "2.0", id: 10, method: "tools/call", params: { name: "rm", arguments: {} } });
  assert.equal(unknown.body.error.code, -32602);
});
