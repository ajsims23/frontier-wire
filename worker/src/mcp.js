// Frontier Wire's MCP server (Model Context Protocol, streamable HTTP, stateless, read-only).
// Any MCP client (Claude, ChatGPT, Gemini CLI, Claude Code, an internal agent) can connect to POST /mcp and get
// our fact-checked AI news, the DPA lens, the AI Radar, the task bench and our accuracy numbers, with links.
// The data comes from the site's own static files (data/search.json and api/v1/*.json), cached for ten minutes.

export const PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"];
const SERVER = { name: "frontier-wire", title: "Frontier Wire", version: "1.0.0" };
const INSTRUCTIONS = `Frontier Wire is an AI news agent. Every story is checked against its sources (an official source or two
independent outlets) and a second model audits a sample daily. Each story also carries a "DPA lens": what it means for
DPA, a data and process automation firm (document extraction, data QA, investor reporting, research, data pipelines,
agents), with a move (trial / assess / watch / caution) and a first test. Cite the story pages you use. The DPA lens and
the radar are the agent's recommendations, not decisions: people approve anything that is adopted.`;

const ro = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
const str = (description, extra = {}) => ({ type: "string", description, ...extra });
export const TOOLS = [
  { name: "search_news", title: "Search verified AI news",
    description: "Search Frontier Wire's fact-checked archive of AI news. Returns the best-matching stories with date, summary, why it matters, the DPA so-what and move, and the story page (which lists every source).",
    inputSchema: { type: "object", properties: { query: str("What to search for, e.g. 'document extraction model', 'Anthropic', 'EU AI Act'"),
      limit: { type: "integer", minimum: 1, maximum: 10, description: "How many stories (default 6)" } }, required: ["query"] }, annotations: ro },
  { name: "what_changed", title: "What changed since a date",
    description: "Everything since a date: new stories (newest first), AI Radar moves, and the latest calls for DPA. Use it to catch up.",
    inputSchema: { type: "object", properties: { since: str("A date, YYYY-MM-DD (default: 3 days ago)") } }, annotations: ro },
  { name: "dpa_brief", title: "This week's calls for DPA",
    description: "The intelligence agent's calls for DPA this week and the developments to act on, each with a so-what, a move and a first test. Optionally for one role or capability.",
    inputSchema: { type: "object", properties: {
      role: str("Optional role id", { enum: ["leadership", "delivery", "extraction", "quality", "analysts", "engineers", "champions"] }),
      capability: str("Optional capability id", { enum: ["doc_extraction", "data_qa", "reporting", "research", "data_pipelines", "agents", "productivity", "governance"] }) } },
    annotations: ro },
  { name: "get_radar", title: "The DPA AI Radar",
    description: "AI models, tools, techniques and rules placed for DPA's work on Adopt / Trial / Assess / Hold, with the agent's rationale and evidence. Only a person can move something into Adopt.",
    inputSchema: { type: "object", properties: { ring: str("Optional ring", { enum: ["adopt", "trial", "assess", "hold"] }),
      quadrant: str("Optional quadrant", { enum: ["models", "tools", "techniques", "policy"] }),
      query: str("Optional name to look for, e.g. 'Gemini'") } }, annotations: ro },
  { name: "best_model_for", title: "Best free model for a DPA task",
    description: "Results of the DPA Task Bench: every free model the agent can reach, tested weekly on synthetic DPA-style documents and scored automatically against known answers.",
    inputSchema: { type: "object", properties: { task_type: str("Which kind of work (default: overall)", { enum: ["overall", "extraction", "quality", "research", "routing"] }) } },
    annotations: ro },
  { name: "ask_wire", title: "Ask the Wire",
    description: "A short answer to a question about AI news, written from the fact-checked archive with numbered citations to story pages. Prefer search_news when you want to read the stories yourself.",
    inputSchema: { type: "object", properties: { question: str("The question") }, required: ["question"] }, annotations: { ...ro, idempotentHint: false } },
  { name: "system_status", title: "How far to trust Frontier Wire",
    description: "The pipeline's numbers for the last 7 days (items read, published, dropped and why), verification rates, the accuracy audit and the corrections log.",
    inputSchema: { type: "object", properties: {} }, annotations: ro },
];

const cache = new Map();
async function siteJson(env, path) {
  const hit = cache.get(path);
  if (hit && Date.now() - hit.at < 10 * 60 * 1000) return hit.data;
  const r = await fetch(new URL(path, env.SITE_URL), { cf: { cacheTtl: 600 } });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  const data = await r.json();
  cache.set(path, { at: Date.now(), data });
  return data;
}

const page = (env, id) => new URL(`story/${id}/`, env.SITE_URL).href;
function storyOut(env, d) {
  return { id: d.id, date: d.d, headline: d.h, summary: d.s, why_it_matters: d.w || "", lab: d.l || "", page: page(env, d.id),
    ...(d.x ? { dpa: { so_what: d.x, move: d.m || "" } } : {}) };
}

export async function callTool(name, args, env, deps, ip = "unknown") {
  args = args && typeof args === "object" ? args : {};
  switch (name) {
    case "search_news": {
      const q = String(args.query || "").trim().slice(0, 200);
      if (!q) throw new ToolError("query is required");
      const n = Math.max(1, Math.min(10, parseInt(args.limit, 10) || 6));
      const hits = deps.rank(await deps.getIndex(env), q, n);
      return { query: q, results: hits.map((h) => storyOut(env, h.doc)), note: "Open a story page for its sources." };
    }
    case "what_changed": {
      const since = /^\d{4}-\d{2}-\d{2}$/.test(String(args.since || "")) ? args.since : new Date(Date.now() - 3 * 86400000).toISOString().slice(0, 10);
      const index = await deps.getIndex(env);
      const docs = (index.docs || []).filter((d) => d.d >= since).sort((a, b) => (a.d < b.d ? 1 : -1));
      const radar = await siteJson(env, "api/v1/radar.json").catch(() => ({ entries: [] }));
      const moves = radar.entries.flatMap((e) => (e.history || []).filter((h) => h.date >= since).map((h) => ({ item: e.name, from: h.from || "new", to: h.to, date: h.date, why: h.why })));
      const dpa = await siteJson(env, "api/v1/dpa.json").catch(() => ({}));
      return { since, new_stories: docs.length, stories: docs.slice(0, 25).map((d) => storyOut(env, d)), radar_moves: moves, dpa_calls: dpa.brief || null };
    }
    case "dpa_brief": {
      const dpa = await siteJson(env, "api/v1/dpa.json");
      let act = dpa.act_on || [];
      if (args.capability) act = act.filter((x) => (x.capabilities || []).includes(args.capability));
      const role = args.role ? (dpa.roles || []).find((r) => r.id === args.role) : null;
      return { org: dpa.org, calls: dpa.brief || null, act_on: act.slice(0, 10), ...(role ? { for_role: role } : {}),
        note: "These are the agent's recommendations; a person approves any pilot or adoption." };
    }
    case "get_radar": {
      const radar = await siteJson(env, "api/v1/radar.json");
      const q = String(args.query || "").toLowerCase();
      const entries = radar.entries.filter((e) => (!args.ring || e.ring === args.ring) && (!args.quadrant || e.quadrant === args.quadrant)
        && (!q || e.name.toLowerCase().includes(q)));
      return { updated_at: radar.updated_at, rings: radar.rings, count: entries.length,
        entries: entries.map((e) => ({ name: e.name, ring: e.ring, proposed_for_adopt: e.proposed === "adopt", set_by_person: !!e.human, quadrant: e.quadrant,
          capability: e.cap_name, rationale: e.rationale, updated: e.updated, evidence: (e.evidence || []).slice(0, 3) })),
        page: new URL("radar/", env.SITE_URL).href };
    }
    case "best_model_for": {
      const b = await siteJson(env, "api/v1/bench.json");
      const t = ["extraction", "quality", "research", "routing"].includes(args.task_type) ? args.task_type : "overall";
      const run = b.latest;
      if (!run) return { note: "The bench hasn't run yet." };
      const rows = run.models.filter((m) => m.available).map((m) => ({ model: m.model, provider: m.provider, score: t === "overall" ? m.score : (m.by_type || {})[t],
        overall: m.score, median_latency_s: m.median_latency_s })).sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
      return { task_type: t, run_date: run.date, tasks: b.tasks.filter((x) => t === "overall" || x.type === t).map((x) => x.title), ranking: rows,
        method: "Synthetic DPA-style documents, scored automatically against known answers; free models only.", page: new URL("bench/", env.SITE_URL).href };
    }
    case "ask_wire": {
      const q = String(args.question || "").trim().slice(0, 300);
      if (q.length < 3) throw new ToolError("question is required");
      if (deps.bump && (!(await deps.bump(env, "ask", ip, 25)) || !(await deps.bump(env, "ask", "all", 600)))) throw new ToolError("Daily question limit reached. Try search_news instead.");
      const r = await deps.answer(env, q, await deps.getIndex(env));
      return { answer: r.answer, sources: (r.sources || []).map((s) => ({ n: s.n, headline: s.headline, date: s.date, page: s.id ? page(env, s.id) : s.url })), general: !!r.general };
    }
    case "system_status": {
      const s = await siteJson(env, "api/v1/system.json");
      return { ...s, corrections_log: (s.corrections_log || []).slice(0, 10), page: new URL("system/", env.SITE_URL).href };
    }
    default:
      throw new RpcError(-32602, `Unknown tool: ${name}`);
  }
}

class ToolError extends Error {}
class RpcError extends Error { constructor(code, message) { super(message); this.code = code; } }

const HEADERS = { "content-type": "application/json", "access-control-allow-origin": "*", "access-control-allow-methods": "POST, GET, OPTIONS, DELETE",
  "access-control-allow-headers": "content-type, mcp-protocol-version, mcp-session-id, authorization, accept", "access-control-expose-headers": "mcp-session-id" };
const reply = (body, status = 200) => new Response(body === null ? null : JSON.stringify(body), { status, headers: HEADERS });
const ok = (id, result) => reply({ jsonrpc: "2.0", id, result });
const fail = (id, code, message) => reply({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });

export async function handleMcp(req, env, deps) {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: HEADERS });
  if (req.method !== "POST") return new Response(JSON.stringify({ error: "This MCP server speaks streamable HTTP: send JSON-RPC with POST." }), { status: 405, headers: { ...HEADERS, allow: "POST, OPTIONS" } });
  let msg;
  try { msg = await req.json(); } catch (e) { return fail(null, -32700, "Parse error"); }
  if (Array.isArray(msg)) return fail(null, -32600, "Batches are not supported");
  if (!msg || msg.jsonrpc !== "2.0" || typeof msg.method !== "string") return fail(msg && msg.id, -32600, "Invalid request");
  const { id, method, params } = msg;
  if (id === undefined || id === null) return reply(null, 202);  // a notification (e.g. notifications/initialized)
  try {
    if (method === "initialize") {
      const asked = params && params.protocolVersion;
      return ok(id, { protocolVersion: PROTOCOL_VERSIONS.includes(asked) ? asked : PROTOCOL_VERSIONS[0],
        capabilities: { tools: { listChanged: false } }, serverInfo: SERVER, instructions: INSTRUCTIONS });
    }
    if (method === "ping") return ok(id, {});
    if (method === "tools/list") return ok(id, { tools: TOOLS });
    if (method === "resources/list") return ok(id, { resources: [] });
    if (method === "prompts/list") return ok(id, { prompts: [] });
    if (method === "tools/call") {
      const name = params && params.name;
      if (!TOOLS.some((t) => t.name === name)) return fail(id, -32602, `Unknown tool: ${name}`);
      const ip = deps.sha ? await deps.sha(req.headers.get("cf-connecting-ip") || "unknown") : "unknown";
      try {
        const data = await callTool(name, params.arguments, env, deps, ip);
        return ok(id, { content: [{ type: "text", text: JSON.stringify(data, null, 1) }], structuredContent: data });
      } catch (e) {
        if (e instanceof RpcError) return fail(id, e.code, e.message);
        return ok(id, { content: [{ type: "text", text: e instanceof ToolError ? e.message : `Frontier Wire couldn't complete that: ${e.message}` }], isError: true });
      }
    }
    return fail(id, -32601, `Method not found: ${method}`);
  } catch (e) {
    return fail(id, -32603, "Internal error");
  }
}
