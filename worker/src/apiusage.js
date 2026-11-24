// API usage and limits for the admin dashboard's "Usage & limits" tab.
//
// Two feeds land in the same tables:
//   - GitHub Actions runs (newsroom, breaking-news check, DPA lens, recap, footage) POST their per-run totals to
//     /api/usage/report (agent/usage.py), authorised with DISPATCH_SECRET.
//   - The worker meters its own calls: Ask the Wire's AI, Workers AI (voice, images, fallback chat), Brevo emails
//     and the GitHub scheduler token.
// api_usage holds daily counts per service/model/source; api_state holds the latest rate-limit headers and notes
// (e.g. Groq's remaining daily requests, when the scheduler token expires). Live checks (Brevo credits) run when
// the tab is opened.

const KEEP_DAYS = 35;
const OUTCOMES = ["ok", "limited", "busy", "failed"];
const istDay = (ms = Date.now()) => new Date(ms + 5.5 * 3600 * 1000).toISOString().slice(0, 10);   // the site runs on IST

// Free-tier limits as documented by each provider when this was written (Nov 2026). They change without notice,
// so live figures (rate-limit headers, a 429's own quota value, Brevo's credits) are shown first where they exist.
export const SERVICES = {
  gemini:       { label: "Google Gemini", what: "Newsroom AI (main), Ask the Wire, search answers", limit: "Free tier, per model: about 10-15 requests/min and a few hundred to 1,000 requests/day", key: "GEMINI_API_KEY" },
  groq:         { label: "Groq", what: "Newsroom AI (backup), Ask the Wire", limit: "Free tier, per model: about 8k tokens/min and 200k tokens/day; live figures below", key: "GROQ_API_KEY" },
  nvidia:       { label: "NVIDIA NIM", what: "Newsroom AI (backup)", limit: "Free for NVIDIA Developer members: about 40 requests/min", key: "NVIDIA_API_KEY" },
  cerebras:     { label: "Cerebras", what: "Last-resort AI", limit: "No free tier since Jul 2026: answers 402 until billing is added", key: "CEREBRAS_API_KEY" },
  openrouter:   { label: "OpenRouter", what: "Last-resort AI", limit: "Free models: about 50 requests/day without credit", key: "OPENROUTER_API_KEY" },
  mistral:      { label: "Mistral", what: "Optional AI (unused without a key)", limit: "Free Experiment plan: about 1 request/second", key: "MISTRAL_API_KEY" },
  "gemini-tts": { label: "Gemini voice", what: "Recap narration (main voice)", limit: "Free tier: about 10 requests/day", daily: 10, key: "GEMINI_API_KEY" },
  "workers-ai": { label: "Cloudflare Workers AI", what: "Backup voice, recap images, last-resort chat", limit: "Free: 10,000 neurons/day (about 60 per image; a voice clip or chat answer uses more)", key: "Cloudflare binding" },
  brevo:        { label: "Brevo email", what: "Digests, alerts, recap emails, sign-in links", limit: "Free plan: 300 emails/day (the worker stops at 280)", daily: 300, key: "BREVO_API_KEY" },
  pexels:       { label: "Pexels", what: "Recap B-roll search", limit: "200 requests/hour, 20,000/month", key: "PEXELS_API_KEY" },
  pixabay:      { label: "Pixabay", what: "Recap B-roll search", limit: "100 requests/minute", key: "PIXABAY_API_KEY" },
  github:       { label: "GitHub scheduler token", what: "Starts runs GitHub's own cron misses", limit: "5,000 API requests/hour; expires on the date you set", key: "SCHEDULER_TOKEN" },
};

const ready = new WeakSet();   // per database (schema.sql also creates these on deploy)
async function ensure(env) {
  if (!env.DB || ready.has(env.DB)) return;
  await env.DB.batch([
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS api_usage (day TEXT NOT NULL, service TEXT NOT NULL, model TEXT NOT NULL, source TEXT NOT NULL,
      requests INTEGER NOT NULL DEFAULT 0, ok INTEGER NOT NULL DEFAULT 0, limited INTEGER NOT NULL DEFAULT 0, busy INTEGER NOT NULL DEFAULT 0,
      failed INTEGER NOT NULL DEFAULT 0, tokens INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, service, model, source))`),
    env.DB.prepare("CREATE TABLE IF NOT EXISTS api_state (service TEXT NOT NULL, k TEXT NOT NULL, v TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (service, k))"),
  ]);
  ready.add(env.DB);
}

const clip = (s, n) => String(s ?? "").slice(0, n);
const num = (x) => Math.max(0, Math.min(1e9, Math.round(+x || 0)));

// rows: [{service, model, requests, ok, limited, busy, failed, tokens}], state: [{service, k, v}]
export async function record(env, source, rows = [], state = [], day = istDay()) {
  if (!env.DB) return;
  await ensure(env);
  const stmts = [];
  for (const r of rows.slice(0, 200)) {
    if (!r || !r.service) continue;
    const v = [num(r.requests), num(r.ok), num(r.limited), num(r.busy), num(r.failed), num(r.tokens)];
    if (!v.some(Boolean)) continue;
    stmts.push(env.DB.prepare(`INSERT INTO api_usage (day, service, model, source, requests, ok, limited, busy, failed, tokens)
      VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
      ON CONFLICT (day, service, model, source) DO UPDATE SET requests = requests + ?5, ok = ok + ?6, limited = limited + ?7,
      busy = busy + ?8, failed = failed + ?9, tokens = tokens + ?10`)
      .bind(day, clip(r.service, 40), clip(r.model || "-", 80), clip(source || "-", 60), ...v));
  }
  const at = new Date().toISOString();
  for (const s of state.slice(0, 300)) {
    if (!s || !s.service || !s.k) continue;
    stmts.push(env.DB.prepare("INSERT OR REPLACE INTO api_state (service, k, v, at) VALUES (?1, ?2, ?3, ?4)")
      .bind(clip(s.service, 40), clip(s.k, 120), clip(s.v, 240), at));
  }
  if (stmts.length) await env.DB.batch(stmts);
}

// One call made by the worker itself. outcome from the HTTP status (null = no answer).
export function outcomeFor(status) {
  if (status == null || status >= 500) return "busy";
  if (status === 429 || status === 402) return "limited";
  return status >= 400 ? "failed" : "ok";
}

export async function meter(env, service, model, status, { tokens = 0, headers = null, note = "" } = {}) {
  try {
    const o = outcomeFor(status);
    const state = [];
    if (headers) for (const [k, v] of headers) if (/^x-ratelimit-|^ratelimit-|^retry-after$/i.test(k)) state.push({ service, k: `${model}|${k.toLowerCase()}`, v });
    if (o === "limited" && note) state.push({ service, k: `${model}|last limit`, v: note });
    await record(env, "worker", [{ service, model, requests: 1, [o]: 1, tokens }], state);
  } catch (e) { /* metering never breaks a request */ }
}

export async function report(req, env) {
  if (!env.DISPATCH_SECRET || req.headers.get("authorization") !== `Bearer ${env.DISPATCH_SECRET}`) return { status: 403, body: { error: "forbidden" } };
  let body;
  try { body = await req.json(); } catch { return { status: 400, body: { error: "bad json" } }; }
  await record(env, clip(body.source, 60), Array.isArray(body.rows) ? body.rows : [], Array.isArray(body.state) ? body.state : []);
  return { status: 200, body: { ok: true } };
}

async function brevoLive(env) {
  if (!env.BREVO_API_KEY) return null;
  try {
    const r = await fetch("https://api.brevo.com/v3/account", { headers: { "api-key": env.BREVO_API_KEY, accept: "application/json" } });
    if (!r.ok) return { error: `HTTP ${r.status}` };
    const j = await r.json();
    const plan = (j.plan || []).find((p) => p.creditsType === "sendLimit") || (j.plan || [])[0] || {};
    return { plan: plan.type || "", credits: plan.credits ?? null, creditsType: plan.creditsType || "" };
  } catch (e) { return { error: "unreachable" }; }
}

// Everything the tab needs: 7 days of counts per service, the latest limit headers, live checks.
export async function usageOverview(env, now = Date.now()) {
  await ensure(env);
  const days = Array.from({ length: 7 }, (_, i) => istDay(now - (6 - i) * 86400000));
  const rows = (await env.DB.prepare("SELECT * FROM api_usage WHERE day >= ?1 ORDER BY day").bind(days[0]).all()).results;
  const state = (await env.DB.prepare("SELECT service, k, v, at FROM api_state ORDER BY service, k").all()).results;
  // the worker's own daily caps (usage table: emails sent, images, voices, Ask the Wire questions)
  const caps = (await env.DB.prepare("SELECT kind, n FROM usage WHERE day = ?1 AND who = 'all'").bind(days[6]).all().catch(() => ({ results: [] }))).results;
  const errors = (await env.DB.prepare("SELECT at, kind, msg FROM log WHERE level = 'error' AND kind IN ('scheduler', 'usage') ORDER BY id DESC LIMIT 10").all().catch(() => ({ results: [] }))).results;
  // housekeeping: drop old days
  await env.DB.prepare("DELETE FROM api_usage WHERE day < ?1").bind(istDay(now - KEEP_DAYS * 86400000)).run().catch(() => {});
  // keys the worker itself holds; Pexels/Pixabay keys live only in GitHub secrets, so the worker can't tell (null)
  const configured = Object.fromEntries(Object.entries(SERVICES).map(([k, s]) => [k, s.key === "Cloudflare binding" ? !!env.AI
    : ["PEXELS_API_KEY", "PIXABAY_API_KEY"].includes(s.key) ? null : !!env[s.key]]));
  return { days, today: days[6], services: SERVICES, rows, state, caps, errors, configured, brevo: await brevoLive(env) };
}
