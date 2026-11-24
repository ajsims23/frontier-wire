import { test } from "node:test";
import assert from "node:assert/strict";
import { JOBS, decide, slotStart, tick } from "../src/scheduler.js";

const job = (wf) => JOBS.find((j) => j.workflow === wf);
const at = (iso) => Date.parse(iso);
const run = (created_at, status = "completed", conclusion = "success") => ({ created_at, status, conclusion });

test("slots line up with the newsroom, watch and DPA schedules", () => {
  assert.equal(new Date(slotStart(at("2026-11-24T09:50:00Z"), 180, 17)).toISOString(), "2026-11-24T09:17:00.000Z");
  assert.equal(new Date(slotStart(at("2026-11-24T09:10:00Z"), 180, 17)).toISOString(), "2026-11-24T06:17:00.000Z");
  assert.equal(new Date(slotStart(at("2026-11-24T00:05:00Z"), 180, 17)).toISOString(), "2026-11-23T21:17:00.000Z");
  assert.equal(new Date(slotStart(at("2026-11-24T09:50:00Z"), 15, 0)).toISOString(), "2026-11-24T09:45:00.000Z");
  assert.equal(new Date(slotStart(at("2026-11-24T11:00:00Z"), 180, 107)).toISOString(), "2026-11-24T10:47:00.000Z");
});

test("a missed newsroom slot is started once GitHub's grace period is over", () => {
  const n = job("newsroom.yml");
  const runs = [run("2026-11-24T01:56:00Z"), run("2026-11-23T21:28:00Z")];
  assert.equal(decide(n, at("2026-11-24T09:30:00Z"), runs), "early");
  assert.equal(decide(n, at("2026-11-24T09:50:00Z"), runs), "start");
  assert.equal(decide(n, at("2026-11-24T09:50:00Z"), [run("2026-11-24T09:31:00Z"), ...runs]), "done");
  assert.equal(decide(n, at("2026-11-24T09:50:00Z"), [run("2026-11-24T09:54:00Z", "in_progress", null)]), "running");
});

test("a cancelled run doesn't count, a failed one does", () => {
  const n = job("newsroom.yml");
  assert.equal(decide(n, at("2026-11-24T09:50:00Z"), [run("2026-11-24T09:20:00Z", "completed", "cancelled")]), "start");
  assert.equal(decide(n, at("2026-11-24T09:50:00Z"), [run("2026-11-24T09:20:00Z", "completed", "failure")]), "done");
});

test("the breaking-news check never queues behind a newsroom run", () => {
  const w = job("watch.yml");
  assert.equal(decide(w, at("2026-11-24T09:50:00Z"), [run("2026-11-24T09:30:00Z")]), "start");
  assert.equal(decide(w, at("2026-11-24T09:50:00Z"), [run("2026-11-24T09:30:00Z")], new Set(["newsroom.yml"])), "blocked");
});

test("tick reads every job, starts what's due and logs newsroom starts", async () => {
  const calls = [];
  const lists = {
    "newsroom.yml": [run("2026-11-24T01:56:00Z")],
    "watch.yml": [run("2026-11-24T09:46:00Z")],
    "dpa.yml": [run("2026-11-24T08:00:00Z")],
  };
  globalThis.fetch = async (url, init = {}) => {
    calls.push([init.method || "GET", url.replace("https://api.github.com/repos/o/r", "")]);
    const wf = url.match(/workflows\/([a-z]+\.yml)/)[1];
    if (init.method === "POST") return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ workflow_runs: lists[wf] }), { status: 200 });
  };
  const logs = [];
  const out = await tick({ SCHEDULER_TOKEN: "t", GITHUB_REPO: "o/r" }, at("2026-11-24T09:50:00Z"), async (...a) => logs.push(a));
  assert.deepEqual(out, [["newsroom.yml", "start"], ["watch.yml", "done"], ["dpa.yml", "done"]]);
  assert.deepEqual(calls.filter((c) => c[0] === "POST"), [["POST", "/actions/workflows/newsroom.yml/dispatches"]]);
  assert.match(logs[0][2], /GitHub missed the 09:17 UTC run/);
});

test("tick does nothing without a token, and reports a revoked one", async () => {
  assert.deepEqual(await tick({ GITHUB_REPO: "o/r" }), []);
  globalThis.fetch = async () => new Response("{}", { status: 401 });
  const logs = [];
  assert.deepEqual(await tick({ SCHEDULER_TOKEN: "bad", GITHUB_REPO: "o/r" }, Date.now(), async (...a) => logs.push(a)), []);
  assert.match(logs[0][2], /expired or revoked/);
});
