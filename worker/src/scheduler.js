// A reliable clock for the GitHub Actions jobs.
//
// GitHub's own cron drops scheduled runs under load. From 20 Nov 2026 it fired about 4 of the 96 daily
// breaking-news checks and 2-3 of the 8 newsroom runs, so the site went 8-12 hours without new stories.
// Cloudflare's cron is reliable, so every 10 minutes the worker checks each job's current time slot and,
// if nothing has run in it yet, starts the workflow through the GitHub API. GitHub's cron stays on as a
// second clock; a late GitHub run whose slot already ran skips itself (see the gate job in the workflows).
//
// Needs the worker secret SCHEDULER_TOKEN: a fine-grained GitHub token for this repository only, with
// "Actions: read and write". Without it this does nothing and GitHub's cron is the only clock.

import { record } from "./apiusage.js";

const MIN = 60 * 1000;

// every / offset / grace in minutes (UTC). offset = where the slot starts within each period.
export const JOBS = [
  // 00:17, 03:17, 06:17 ... UTC (05:47, 08:47, 11:47 ... IST): the full newsroom
  { workflow: "newsroom.yml", every: 180, offset: 17, grace: 25 },
  // every 15 minutes: the labs' announcement channels; never while a newsroom run is waiting or running,
  // because both share one queue and a newly queued run cancels the one already waiting
  { workflow: "watch.yml", every: 15, offset: 0, grace: 5, notWhile: ["newsroom.yml"] },
  // 90 minutes after each newsroom slot: the DPA lens (radar, assessments) on the fresh stories
  { workflow: "dpa.yml", every: 180, offset: 107, grace: 25, notWhile: ["newsroom.yml"] },
];

const ALIVE = new Set(["queued", "in_progress", "waiting", "pending", "requested"]);

export function slotStart(nowMs, every, offset) {
  const p = every * MIN, o = offset * MIN;
  return nowMs - ((((nowMs - o) % p) + p) % p);
}

// What to do for one job, given its recent runs (newest first, as the API returns them).
//   "running": a run is queued or in progress  |  "done": a run already counts for this slot
//   "early": still inside GitHub's grace period  |  "blocked": a job it must not overlap is busy  |  "start"
export function decide(job, nowMs, runs, busy = new Set()) {
  if (runs.some((r) => ALIVE.has(r.status))) return "running";
  const slot = slotStart(nowMs, job.every, job.offset);
  // a cancelled run did nothing (it was bumped from the queue), so it doesn't count
  const ran = runs.some((r) => r.conclusion !== "cancelled" && Date.parse(r.created_at) >= slot);
  if (ran) return "done";
  if (nowMs < slot + job.grace * MIN) return "early";
  if ((job.notWhile || []).some((w) => busy.has(w))) return "blocked";
  return "start";
}

function gh(env, path, init = {}) {
  return fetch(`https://api.github.com/repos/${env.GITHUB_REPO}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${env.SCHEDULER_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "frontier-wire-scheduler",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
    },
  });
}

// when the token expires and how much of this hour's API allowance is left, for the Usage & limits tab
async function noteToken(env, r) {
  try {
    const exp = r.headers.get("github-authentication-token-expiration");
    const state = [["expires", exp], ["x-ratelimit-limit", r.headers.get("x-ratelimit-limit")], ["x-ratelimit-remaining", r.headers.get("x-ratelimit-remaining")]]
      .filter(([, v]) => v).map(([k, v]) => ({ service: "github", k: `scheduler token|${k}`, v }));
    await record(env, "worker", [{ service: "github", model: "scheduler token", requests: 1, ok: 1 }], state);
  } catch (e) { /* never block the scheduler */ }
}

export async function tick(env, nowMs = Date.now(), log = async () => {}) {
  if (!env.SCHEDULER_TOKEN || !env.GITHUB_REPO) return [];
  const runs = {};
  for (const job of JOBS) {
    const r = await gh(env, `/actions/workflows/${job.workflow}/runs?per_page=10`);
    if (!r.ok) {
      await log("error", "scheduler", `couldn't read ${job.workflow} runs: HTTP ${r.status}${r.status === 401 ? " (SCHEDULER_TOKEN expired or revoked)" : ""}`);
      return [];
    }
    if (job === JOBS[0]) await noteToken(env, r);
    runs[job.workflow] = ((await r.json()).workflow_runs || []).map((x) => ({ status: x.status, conclusion: x.conclusion, created_at: x.created_at }));
  }
  const busy = new Set(JOBS.filter((j) => runs[j.workflow].some((r) => ALIVE.has(r.status))).map((j) => j.workflow));
  const out = [];
  for (const job of JOBS) {
    const what = decide(job, nowMs, runs[job.workflow], busy);
    out.push([job.workflow, what]);
    if (what !== "start") continue;
    const r = await gh(env, `/actions/workflows/${job.workflow}/dispatches`, { method: "POST", body: JSON.stringify({ ref: "main" }) });
    if (r.ok) {
      busy.add(job.workflow);
      if (job.workflow !== "watch.yml") {   // the 15-minute check would flood the log
        const at = new Date(slotStart(nowMs, job.every, job.offset)).toISOString().slice(11, 16);
        await log("info", "scheduler", `started ${job.workflow}: GitHub missed the ${at} UTC run`);
      }
    } else {
      await log("error", "scheduler", `couldn't start ${job.workflow}: HTTP ${r.status}`);
    }
  }
  return out;
}
