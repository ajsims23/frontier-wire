// The community feedback system end to end: the real worker against a real SQLite database (Node's built-in
// node:sqlite standing in for Cloudflare D1), with outside calls (email, AI) replaced by fakes.
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import worker from "../src/index.js";
import { screen, similar, titleFrom, weekKey, parseJson, adminToken } from "../src/feedback.js";

const SCHEMA = readFileSync(new URL("../schema.sql", import.meta.url), "utf8");

function d1() {   // the parts of the D1 API the worker uses
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  const stmt = (sql, args = []) => ({
    bind: (...a) => stmt(sql, a),
    first: async () => { const r = db.prepare(sql).get(...args); return r ? { ...r } : null; },
    all: async () => ({ results: db.prepare(sql).all(...args).map((r) => ({ ...r })) }),
    run: async () => { const r = db.prepare(sql).run(...args); return { meta: { changes: r.changes, last_row_id: Number(r.lastInsertRowid) } }; },
  });
  return { prepare: (sql) => stmt(sql), batch: async (list) => { const out = []; for (const s of list) out.push(await s.run()); return out; }, raw: db };
}

const SITE = "https://ajsims23.github.io/frontier-wire/";
let env, mail, aiReplies;
beforeEach(() => {
  env = { DB: d1(), SITE_URL: SITE, API_URL: "https://api.example.dev", DISPATCH_SECRET: "s3cret-for-tests", ADMIN_EMAIL: "editor@example.com",
    BREVO_API_KEY: "k", SENDER_EMAIL: "news@example.com" };
  mail = []; aiReplies = [];
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url);
    if (u.includes("brevo.com")) { const b = JSON.parse(init.body); mail.push({ to: b.to[0].email, subject: b.subject, html: b.htmlContent }); return new Response("{}", { status: 201 }); }
    if (u.includes("generativelanguage") && aiReplies.length) return Response.json({ choices: [{ message: { content: aiReplies.shift() } }] });
    return new Response("no", { status: 503 });
  };
});

const V1 = "visitor-one-aaaaaaaaaaaa", V2 = "visitor-two-bbbbbbbbbbbb", V3 = "visitor-three-cccccccccc";
async function call(path, body, { ip = "1.1.1.1", auth, method } = {}) {
  const headers = { "content-type": "application/json", origin: "https://ajsims23.github.io", "cf-connecting-ip": ip };
  if (auth) headers.authorization = auth;
  const r = await worker.fetch(new Request(`https://api.example.dev${path}`, { method: method || (body ? "POST" : "GET"), headers, body: body ? JSON.stringify(body) : undefined }), env);
  return { status: r.status, body: await r.json(), headers: r.headers };
}
const suggest = (title, extra = {}) => call("/api/feedback/suggest", { title, body: "", category: "feature", v: V1, hp: "", ms: 5000, ...extra });
const admin = () => `Bearer ${env.DISPATCH_SECRET}`;

test("a visitor posts an idea; it's on the board with their own vote, and CORS allows the site", async () => {
  const r = await suggest("Dark mode for the weekly email", { body: "Reading at night is hard.", name: "Priya" });
  assert.equal(r.status, 200);
  assert.equal(r.body.item.votes, 1);
  assert.equal(r.headers.get("access-control-allow-origin"), "https://ajsims23.github.io");
  const list = await call(`/api/feedback/list?v=${V1}`);
  assert.equal(list.body.items.length, 1);
  assert.equal(list.body.items[0].name, "Priya");
  assert.deepEqual(list.body.voted, [r.body.item.id]);
  assert.deepEqual(list.body.mine, [r.body.item.id]);
  assert.equal(list.body.counts.open, 1);
  assert.equal(JSON.stringify(list.body).includes("1.1.1.1"), false);   // no IPs or visitor ids leave the server
  assert.equal(JSON.stringify(list.body).includes(V1), false);
});

test("similar ideas are suggested before posting, and exact duplicates are refused", async () => {
  await suggest("Dark mode for the weekly email");
  await suggest("Podcast speed controls", { v: V2, ip: "2.2.2.2" });
  const sim = await call("/api/feedback/similar?q=" + encodeURIComponent("email in dark mode please"));
  assert.equal(sim.body.items.length, 1);
  assert.match(sim.body.items[0].title, /Dark mode/);
  assert.equal((await call("/api/feedback/similar?q=quantum")).body.items.length, 0);
  await suggest("I'd love a weekly summary of new open-source models", { v: V3, ip: "3.3.3.3" });
  const os = await call("/api/feedback/similar?q=" + encodeURIComponent("Weekly open source model roundup"));
  assert.match(os.body.items[0].title, /open-source models/);
  assert.equal((await call("/api/feedback/similar?q=" + encodeURIComponent("weekly podcast"))).body.items.length, 0);   // one shared word isn't enough
  const dupe = await suggest("dark mode for the weekly email", { v: V2 });
  assert.equal(dupe.status, 409);
  assert.ok(dupe.body.id);
});

test("votes toggle, count once per visitor, and one network can't stuff the box", async () => {
  const { body: { item } } = await suggest("Add a jobs board for AI roles");
  let r = await call("/api/feedback/vote", { id: item.id, v: V2 }, { ip: "9.9.9.9" });
  assert.deepEqual([r.body.voted, r.body.votes], [true, 2]);
  r = await call("/api/feedback/vote", { id: item.id, v: V2 }, { ip: "9.9.9.9" });
  assert.deepEqual([r.body.voted, r.body.votes], [false, 1]);
  for (const v of [V2, V3, "visitor-four-dddddddddddd"]) await call("/api/feedback/vote", { id: item.id, v }, { ip: "9.9.9.9" });
  r = await call("/api/feedback/vote", { id: item.id, v: "visitor-five-eeeeeeeeeeee" }, { ip: "9.9.9.9" });
  assert.equal(r.status, 429);
});

test("comments post, and links or abuse wait for review instead of going live", async () => {
  const { body: { item } } = await suggest("Weekly model leaderboard");
  let r = await call("/api/feedback/comment", { id: item.id, body: "Yes please, with prices too", name: "Sam", v: V2, hp: "", ms: 4000 });
  assert.equal(r.body.held, false);
  r = await call("/api/feedback/comment", { id: item.id, body: "see my site https://example.org", v: V3, hp: "", ms: 4000 });
  assert.equal(r.body.held, true);
  const got = await call(`/api/feedback/item?id=${item.id}`);
  assert.deepEqual(got.body.comments.map((c) => c.name), ["Sam"]);
  assert.equal(got.body.item.comments, 1);
});

test("spam is turned away: honeypot, instant bots, spam words, and too many posts", async () => {
  const bot = await suggest("Cheap followers here now", { hp: "http://spam" });
  assert.equal(bot.status, 200);                                     // the bot is told it worked...
  assert.equal((await call("/api/feedback/list")).body.items.length, 0);   // ...but nothing was stored
  assert.equal((await suggest("Something typed instantly", { ms: 200 })).status, 200);
  assert.equal((await call("/api/feedback/list")).body.items.length, 0);
  assert.equal((await suggest("Best casino bonus codes")).status, 400);
  assert.equal(screen("BUY NOW THIS IS THE BEST SITE EVER AMAZING"), "hold");
  assert.equal(screen("A calendar of AI conferences would help"), "ok");
  for (let i = 0; i < 6; i++) await suggest(`Idea number ${i} for the site`, { ip: "5.5.5.5" });
  assert.equal((await suggest("One idea too many today", { ip: "5.5.5.5" })).status, 429);
});

test("the welcome card's feedback is private unless the visitor shares it", async () => {
  await call("/api/feedback/popup", { text: "I'd love a section on AI in healthcare.", public: false, v: V1, hp: "", ms: 3000 });
  let list = await call("/api/feedback/list");
  assert.equal(list.body.items.length, 0);
  const shared = await call("/api/feedback/popup", { text: "More coverage of Indian AI startups please", public: true, v: V2, hp: "", ms: 3000 }, { ip: "3.3.3.3" });
  list = await call("/api/feedback/list");
  assert.equal(list.body.items.length, 1);
  assert.equal(list.body.items[0].id, shared.body.id);
  const ov = await call("/api/admin/overview", null, { auth: admin() });
  assert.equal(ov.body.stats.private, 1);
  assert.equal(titleFrom("Short one. And more after it."), "Short one.");
});

test("the admin area needs a valid sign-in, and only the admin's address gets a link", async () => {
  assert.equal((await call("/api/admin/overview")).status, 401);
  assert.equal((await call("/api/admin/overview", null, { auth: "Admin 9999999999.0123456789abcdef0123456789abcdef" })).status, 401);
  await call("/api/admin/login", { email: "someone@else.com" });
  assert.equal(mail.length, 0);
  const r = await call("/api/admin/login", { email: "Editor@Example.com" });
  assert.match(r.body.message, /on its way/);
  assert.equal(mail.length, 1);
  const k = mail[0].html.match(/#k=([0-9]+\.[0-9a-f]+)/)[1];
  assert.ok(mail[0].html.includes(`${SITE}admin/#k=`));
  assert.equal((await call("/api/admin/overview", null, { auth: `Admin ${k}` })).status, 200);
  assert.equal((await call("/api/admin/overview", null, { auth: `Admin ${await adminToken({ DISPATCH_SECRET: "other" })}` })).status, 401);
});

test("weekly analysis: themes, scores and two picks, then a person approves; nothing is repeated next week", async () => {
  const a = (await suggest("Dark mode for the newsletter", { body: "Night reading" })).body.item;
  const b = (await suggest("Newsletter in dark theme", { v: V2, ip: "2.2.2.2" })).body.item;
  const c = (await suggest("Show model prices in a table", { v: V3, ip: "3.3.3.3" })).body.item;
  const d = (await suggest("A jobs board", { v: V3, ip: "3.3.3.4" })).body.item;
  for (const [v, ip] of [[V2, "7.7.7.1"], [V3, "7.7.7.2"], ["visitor-six-ffffffffffff", "7.7.7.3"]]) await call("/api/feedback/vote", { id: c.id, v }, { ip });
  env.GEMINI_API_KEY = "g";
  aiReplies = [
    JSON.stringify({ summary: "Readers want dark mode and price data.", problems: ["Hard to read at night"],
      themes: [{ name: "Dark mode", summary: "Night reading", ids: [a.id, b.id] }, { name: "Model data", summary: "Prices", ids: [c.id] }, { name: "Careers", ids: [d.id] }],
      ratings: { [a.id]: { feasibility: 5, impact: 4, alignment: 4 }, [b.id]: { feasibility: 5, impact: 3, alignment: 3 }, [c.id]: { feasibility: 4, impact: 5, alignment: 5 }, [d.id]: { feasibility: 1, impact: 2, alignment: 1 } } }),
    "```json\n" + JSON.stringify({ [c.id]: "Most-voted idea; fits the model tracker.", [a.id]: "Two separate requests for it; a small CSS change." }) + "\n```",
  ];
  const r = await call("/api/admin/analyze", {}, { auth: admin() });
  assert.equal(r.body.engine, "ai");
  assert.deepEqual(r.body.picks.map((p) => p.id), [c.id, a.id]);
  assert.match(r.body.picks[0].reason, /Most-voted/);
  assert.equal(r.body.themes[0].name, "Dark mode");
  assert.ok(mail.some((m) => m.to === "editor@example.com" && /review needed/.test(m.subject)));
  // the site doesn't change until someone approves
  assert.equal((await call(`/api/feedback/item?id=${c.id}`)).body.item.status, "open");
  await call("/api/admin/decide", { week: r.body.week, sid: c.id, decision: "approve" }, { auth: admin() });
  await call("/api/admin/decide", { week: r.body.week, sid: a.id, decision: "reject" }, { auth: admin() });
  assert.equal((await call(`/api/feedback/item?id=${c.id}`)).body.item.status, "planned");
  assert.equal((await call(`/api/feedback/item?id=${a.id}`)).body.item.status, "open");
  const ov = (await call("/api/admin/overview", null, { auth: admin() })).body;
  assert.equal(ov.reports[0].status, "reviewed");
  assert.deepEqual(ov.picks.map((p) => p.status).sort(), ["approved", "rejected"]);
  assert.equal((await call("/api/admin/analyze", {}, { auth: admin() })).body.error.includes("already been reviewed"), true);
  // next week: earlier picks aren't recommended again
  const { weekly } = await import("../src/feedback.js");
  const next = await weekly(env, { json: Response.json, sendEmail: async () => true, shell: (e, b) => b, esc: (s) => s, llm: async () => "" },
    { at: new Date(Date.now() + 7 * 86400000) });
  assert.equal(next.engine, "rules");
  assert.equal(next.picks.some((p) => [a.id, c.id].includes(p.id)), false);
  assert.ok(next.picks.length >= 1);
});

test("the analysis still works without any AI provider, and runs once a week by itself", async () => {
  await suggest("Add a glossary of AI terms");
  const { weekly } = await import("../src/feedback.js");
  const h = { sendEmail: async () => true, shell: (e, b) => b, esc: (s) => s, llm: async () => "" };
  const first = await weekly(env, h);
  assert.equal(first.engine, "rules");
  assert.equal(first.picks.length, 1);
  assert.match(first.picks[0].reason, /^1 vote \(1 this week\) and 0 comments/);
  assert.match((await weekly(env, h)).skipped, /already exists/);
});

test("marking an idea implemented emails the people who asked, then forgets their address", async () => {
  const { body: { item } } = await suggest("Audio version of stories", { email: "fan@example.com" });
  await call("/api/feedback/watch", { id: item.id, email: "second@example.com" }, { ip: "4.4.4.4" });
  let r = await call("/api/admin/update", { id: item.id, status: "planned", notify: true }, { auth: admin() });
  assert.equal(r.body.notified, 2);
  assert.ok(mail.every((m) => /^Planned:/.test(m.subject)));
  r = await call("/api/admin/update", { id: item.id, status: "planned", notify: true }, { auth: admin() });
  assert.equal(r.body.notified, 0);   // no repeat emails for the same status
  r = await call("/api/admin/update", { id: item.id, status: "implemented", note: "Every story now has a listen button.", notify: true }, { auth: admin() });
  assert.equal(r.body.notified, 2);
  assert.ok(mail.at(-1).html.includes("listen button"));
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) AS n FROM watchers").get().n, 0);
  const pubItem = (await call(`/api/feedback/item?id=${item.id}`)).body.item;
  assert.equal(pubItem.status, "implemented");
  assert.ok(pubItem.done);
});

test("admin moderation: approve held comments, hide ideas, reply as the team, delete", async () => {
  const { body: { item } } = await suggest("Better search on mobile");
  await call("/api/feedback/comment", { id: item.id, body: "details at www.example.org", v: V2, hp: "", ms: 3000 });
  const ov = (await call("/api/admin/overview", null, { auth: admin() })).body;
  assert.equal(ov.held_comments.length, 1);
  await call("/api/admin/comment", { cid: ov.held_comments[0].id, action: "approve" }, { auth: admin() });
  await call("/api/admin/reply", { id: item.id, body: "Good idea, we're looking at it." }, { auth: admin() });
  const got = (await call(`/api/feedback/item?id=${item.id}`)).body;
  assert.equal(got.comments.length, 2);
  assert.equal(got.comments[1].name, "Frontier Wire team");
  await call("/api/admin/update", { id: item.id, held: true }, { auth: admin() });
  assert.equal((await call("/api/feedback/list")).body.items.length, 0);
  await call("/api/admin/delete", { id: item.id }, { auth: admin() });
  assert.equal((await call("/api/admin/overview", null, { auth: admin() })).body.items.length, 0);
});

test("helpers", () => {
  assert.equal(weekKey(new Date("2026-11-19T10:00:00Z")), "2026-11-16");
  assert.equal(weekKey(new Date("2026-11-16T00:10:00Z")), "2026-11-16");
  assert.equal(weekKey(new Date("2026-11-22T23:00:00Z")), "2026-11-16");
  assert.deepEqual(parseJson('Sure! {"a": 1} hope that helps'), { a: 1 });
  assert.equal(parseJson("no json"), null);
  assert.equal(similar([], "x").length, 0);
});
