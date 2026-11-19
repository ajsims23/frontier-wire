// Frontier Wire feedback dashboard (for the team). Sign-in is by emailed link: the link carries a 30-day key, kept in
// this browser only. Everything here talks to the worker's /api/admin/* endpoints.
const el = document.querySelector("[data-admin]");
const api = (el?.dataset.api || "").replace(/\/$/, "");
const root = el?.dataset.root ?? "/";
const KEY = "fw-admin";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STATUS = { open: "Open", under_consideration: "Under consideration", planned: "Planned", in_progress: "In progress", implemented: "Implemented", declined: "Not planned" };
const CATS = { feature: "Feature", coverage: "Coverage", design: "Design", ask: "Ask the Wire", bug: "Bug", other: "Other" };
const pl = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const day = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "");
const when = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");

let key = "";
function keyFromLink() {   // the emailed link carries the key after "#k=": keep it, then take it out of the address bar
  const m = location.hash.match(/k=(\d{10}\.[0-9a-f]{32})/);
  if (!m) return false;
  key = m[1];
  try { localStorage.setItem(KEY, key); } catch (e) { /* private mode: this visit only */ }
  history.replaceState(null, "", location.pathname);
  return true;
}
keyFromLink();
try { key = key || localStorage.getItem(KEY) || ""; } catch (e) { /* private mode */ }
addEventListener("hashchange", () => { if (el && keyFromLink()) load(); });

let data = null, tab = "overview", filter = { status: "", source: "", vis: "", q: "" };
const openRows = new Set();

async function call(path, body) {
  const r = await fetch(`${api}${path}`, { method: body ? "POST" : "GET", headers: { "Content-Type": "application/json", Authorization: `Admin ${key}` }, body: body ? JSON.stringify(body) : undefined });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) { signOut(); throw new Error(j.error || "Please sign in again."); }
  if (!r.ok || j.error) throw new Error(j.error || `Error ${r.status}`);
  return j;
}
function signOut() { try { localStorage.removeItem(KEY); } catch (e) { /* ok */ } key = ""; signIn(); }
function toast(msg, bad) {
  const t = document.createElement("div"); t.className = `fb-toast ${bad ? "bad" : ""}`; t.setAttribute("role", "status"); t.textContent = msg;
  document.body.append(t); setTimeout(() => t.remove(), 4200);
}

if (!el) { /* not the admin page */ } else if (!api) el.innerHTML = `<p class="muted">The API isn't configured yet.</p>`;
else if (!key) signIn(); else load();

function signIn() {
  el.innerHTML = `<div class="ad-signin"><h2>Sign in</h2><p>Enter the admin email address. We'll email you a sign-in link that works for 30 days on this browser.</p>
    <form><label class="sr" for="ad-email">Admin email</label><input id="ad-email" type="email" required placeholder="you@example.com" autocomplete="email">
    <button class="btn fb-primary" type="submit">Email me a link</button></form><p class="ad-msg" role="status"></p></div>`;
  el.querySelector("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = el.querySelector(".ad-msg");
    try {
      const r = await fetch(`${api}/api/admin/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: el.querySelector("input").value }) });
      msg.textContent = (await r.json()).message || "Check your inbox.";
    } catch (ex) { msg.textContent = "Couldn't reach the server. Try again."; }
  });
}

async function load(keepTab) {
  if (!keepTab) el.innerHTML = `<p class="fb-loading">Loading the dashboard…</p>`;
  try { data = await call("/api/admin/overview"); render(); if (tab === "all") openRows.forEach(loadComments); }
  catch (e) { if (key) el.innerHTML = `<p class="fb-err">${esc(e.message)} <button class="fb-link" type="button" onclick="location.reload()">Retry</button></p>`; }
}

function render() {
  const s = data.stats;
  const report = data.reports[0];
  const pending = data.picks.filter((p) => p.status === "pending").length;
  const tabs = [["overview", "Overview"], ["picks", `Weekly picks${pending ? ` <b>${pending}</b>` : ""}`], ["all", `All feedback <span>${s.total}</span>`],
    ["moderation", `Review queue${s.held ? ` <b>${s.held}</b>` : ""}`], ["history", "History"], ["system", "System"]];
  el.innerHTML = `
    <div class="ad-top"><p>Signed in. ${report ? `Latest analysis: week of ${day(report.week)}.` : "No weekly analysis yet."}</p>
      <div><button type="button" class="btn btn-ghost" data-act="refresh">Refresh</button> <button type="button" class="btn btn-ghost" data-act="signout">Sign out</button></div></div>
    <nav class="ad-tabs" role="tablist">${tabs.map(([k, l]) => `<button type="button" role="tab" aria-selected="${k === tab}" data-tab="${k}">${l}</button>`).join("")}</nav>
    <div class="ad-panel">${({ overview, picks: picksTab, all: allTab, moderation, history: historyTab, system })[tab]()}</div>`;
}

// ------------------------------------------------------------------ overview
function tiles() {
  const s = data.stats;
  return `<div class="ad-tiles">${[["Total feedback", s.total], ["Open ideas", s.open], ["New this week", s.thisWeek], ["Votes this week", s.votesThisWeek],
    ["Implemented", s.implemented], ["Awaiting review", s.held], ["Private messages", s.private]].map(([l, n]) => `<div class="ad-tile"><strong>${n}</strong><span>${l}</span></div>`).join("")}</div>`;
}

// one series per chart (bars per week, brand colour, values on hover, a table underneath for exact numbers)
function bars(title, values, weeks) {
  const W = 320, H = 120, pad = 20, n = values.length, max = Math.max(1, ...values);
  const bw = (W - 8) / n, inner = Math.max(4, bw - 4);
  const total = values.reduce((a, b) => a + b, 0);
  return `<figure class="ad-chart"><figcaption><strong>${title}</strong><span>${total} in 12 weeks · ${values.at(-1)} this week</span></figcaption>
    <svg viewBox="0 0 ${W} ${H + pad}" role="img" aria-label="${esc(title)} per week for the last 12 weeks">
      <line x1="0" x2="${W}" y1="${H}" y2="${H}" class="ad-axis"/>
      ${values.map((v, i) => { const h = v ? Math.max(3, (v / max) * (H - 14)) : 0, x = 4 + i * bw + (bw - inner) / 2;
        return `<g class="ad-bar"><rect x="${4 + i * bw}" y="0" width="${bw}" height="${H}" fill="transparent"/>${h ? `<path d="M${x},${H} v${-(h - 4)} q0,-4 4,-4 h${inner - 8} q4,0 4,4 v${h - 4} z"/>` : ""}
          <title>Week of ${day(weeks[i])}: ${v}</title></g>`; }).join("")}
      <text x="4" y="${H + 15}" class="ad-tick">${day(weeks[0])}</text><text x="${W - 4}" y="${H + 15}" text-anchor="end" class="ad-tick">This week</text>
      ${max > 0 ? `<text x="${W - 2}" y="10" text-anchor="end" class="ad-tick">max ${max}</text>` : ""}
    </svg></figure>`;
}

function overview() {
  const t = data.trends;
  const popular = data.items.filter((s) => s.public && !s.held && !["implemented", "declined"].includes(s.status)).sort((a, b) => b.votes - a.votes).slice(0, 8);
  const shipped = data.items.filter((s) => s.status === "implemented").sort((a, b) => (b.done || "").localeCompare(a.done || "")).slice(0, 6);
  return `${tiles()}
    <div class="ad-charts">${bars("New board ideas", t.suggestions, t.weeks)}${bars("Welcome-card messages", t.feedback, t.weeks)}${bars("Votes", t.votes, t.weeks)}${bars("Implemented", t.implemented, t.weeks)}</div>
    <details class="ad-table"><summary>Show the numbers as a table</summary><div class="ad-scroll"><table><thead><tr><th>Week of</th><th>Ideas</th><th>Messages</th><th>Votes</th><th>Comments</th><th>Implemented</th></tr></thead>
      <tbody>${t.weeks.map((w, i) => `<tr><td>${day(w)}</td><td>${t.suggestions[i]}</td><td>${t.feedback[i]}</td><td>${t.votes[i]}</td><td>${t.comments[i]}</td><td>${t.implemented[i]}</td></tr>`).join("")}</tbody></table></div></details>
    <div class="ad-two">
      <section><h3>Most popular open ideas</h3>${popular.length ? `<ol class="ad-pop">${popular.map((s) => `<li><b>${s.votes}</b><div><button type="button" class="fb-link" data-goto="${s.id}">${esc(s.title)}</button><span>${STATUS[s.status]} · ${pl(s.comments, "comment")}</span></div></li>`).join("")}</ol>` : `<p class="muted">No public ideas yet.</p>`}</section>
      <section><h3>Recently implemented</h3>${shipped.length ? `<ul class="ad-pop">${shipped.map((s) => `<li><b>✓</b><div><button type="button" class="fb-link" data-goto="${s.id}">${esc(s.title)}</button><span>${day(s.done)}</span></div></li>`).join("")}</ul>` : `<p class="muted">Nothing marked implemented yet.</p>`}</section>
    </div>`;
}

// ------------------------------------------------------------------ weekly picks
function picksTab() {
  const r = data.reports[0];
  const head = `<div class="ad-note"><p><strong>The AI recommends; you decide.</strong> Approving an idea marks it <em>Planned</em> on the public board. Nothing else on the site changes by itself.</p>
    <button type="button" class="btn btn-ghost" data-act="analyze">Run this week's analysis now</button></div>`;
  if (!r) return `${head}<p class="muted">No analysis yet. It runs every Monday morning, or press the button.</p>`;
  const pickRows = data.picks.filter((p) => p.week === r.week);
  const cand = new Map((r.candidates || []).map((c) => [c.id, c]));
  return `${head}
    <section class="ad-report"><p class="ad-kicker">Week of ${day(r.week)} · ${r.period ? `${day(r.period.from)} to ${day(r.period.to)}` : ""} · ${r.engine === "ai" ? "AI analysis" : "Rule-based (AI was unavailable)"}</p>
      <p class="ad-summary">${esc(r.summary)}</p>
      <p class="ad-stats">${r.stats ? `${pl(r.stats.new_suggestions, "new idea")} · ${pl(r.stats.new_feedback, "welcome-card message")} · ${pl(r.stats.votes, "vote")} · ${pl(r.stats.comments, "comment")}` : ""}</p>
      <div class="ad-picks">${(r.picks || []).length ? r.picks.map((p, i) => { const row = pickRows.find((x) => x.sid === p.id) || {}; const c = cand.get(p.id) || {};
        return `<article class="ad-pick ${row.status || ""}"><p class="ad-rank">Pick ${i + 1} · score ${p.score}/100</p><h3><button type="button" class="fb-link" data-goto="${p.id}">${esc(p.title)}</button></h3>
          <p>${esc(p.reason)}</p>
          ${c.scores ? `<dl class="ad-scores">${Object.entries(c.scores).map(([k, v]) => `<div><dt>${k}</dt><dd><span style="width:${v * 20}%"></span></dd><dd>${v}</dd></div>`).join("")}</dl>` : ""}
          <p class="ad-meta">${pl(c.votes ?? 0, "vote")} (${c.votes_week ?? 0} this week) · ${pl(c.comments ?? 0, "comment")} · ${esc(c.theme || "")}</p>
          ${row.status === "pending" ? `<div class="ad-decide"><button type="button" class="btn fb-primary" data-decide="approve" data-week="${r.week}" data-sid="${p.id}">Approve</button><button type="button" class="btn btn-ghost" data-decide="reject" data-week="${r.week}" data-sid="${p.id}">Reject</button></div>`
            : `<p class="ad-decided">${row.status === "approved" ? "✓ Approved" : "✕ Rejected"} ${when(row.decided)}</p>`}</article>`; }).join("") : `<p class="muted">No eligible ideas this week.</p>`}</div>
    </section>
    <div class="ad-two">
      <section><h3>Themes</h3>${(r.themes || []).length ? `<ul class="ad-themes">${r.themes.map((t) => `<li><strong>${esc(t.name)}</strong> <span>${pl(t.ids.length, "item")} · ${pl(t.votes || 0, "vote")}</span>${t.summary ? `<p>${esc(t.summary)}</p>` : ""}</li>`).join("")}</ul>` : `<p class="muted">None.</p>`}</section>
      <section><h3>Recurring problems</h3>${(r.problems || []).length ? `<ul class="ad-list">${r.problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : `<p class="muted">None flagged.</p>`}
        <h3>Other contenders</h3>${(r.candidates || []).length > 2 ? `<ol class="ad-list">${r.candidates.slice(2, 8).map((c) => `<li><button type="button" class="fb-link" data-goto="${c.id}">${esc(c.title)}</button> <span class="muted">${c.score}</span></li>`).join("")}</ol>` : `<p class="muted">None.</p>`}</section>
    </div>`;
}

// ------------------------------------------------------------------ all feedback
function allTab() {
  let list = data.items;
  if (filter.status) list = list.filter((s) => s.status === filter.status);
  if (filter.source) list = list.filter((s) => s.source === filter.source);
  if (filter.vis === "public") list = list.filter((s) => s.public && !s.held);
  if (filter.vis === "private") list = list.filter((s) => !s.public);
  if (filter.vis === "held") list = list.filter((s) => s.held);
  if (filter.q) { const q = filter.q.toLowerCase(); list = list.filter((s) => `${s.title} ${s.body}`.toLowerCase().includes(q)); }
  const opt = (map, cur) => Object.entries(map).map(([k, v]) => `<option value="${k}" ${k === cur ? "selected" : ""}>${v}</option>`).join("");
  return `<div class="ad-filters">
      <select data-filter="status" aria-label="Status"><option value="">All statuses</option>${opt(STATUS, filter.status)}</select>
      <select data-filter="source" aria-label="Where from"><option value="">Board and welcome card</option>${opt({ board: "Suggestions board", welcome: "Welcome card" }, filter.source)}</select>
      <select data-filter="vis" aria-label="Visibility"><option value="">Any visibility</option>${opt({ public: "Public", private: "Private messages", held: "Awaiting review" }, filter.vis)}</select>
      <input type="search" data-filter="q" placeholder="Search" value="${esc(filter.q)}" aria-label="Search">
      <span class="muted">${list.length} shown</span></div>
    <div class="ad-rows">${list.map(row).join("") || `<p class="muted">Nothing matches.</p>`}</div>`;
}

function row(s) {
  const isOpen = openRows.has(s.id);
  return `<article class="ad-row ${isOpen ? "open" : ""}" id="ad-${s.id}">
    <button type="button" class="ad-rowhead" data-row="${s.id}" aria-expanded="${isOpen}">
      <span class="ad-votes">${s.votes}</span>
      <span class="ad-title">${esc(s.title)}<small>${s.source === "welcome" ? "Welcome card" : "Board"} · ${s.public ? (s.held ? "awaiting review" : "public") : "private"} · ${day(s.created)} · ${pl(s.comments, "comment")}${s.watchers ? ` · ${s.watchers} following` : ""}</small></span>
      <span class="fb-st st-${s.status}">${STATUS[s.status]}</span></button>
    ${isOpen ? `<div class="ad-edit" data-edit="${s.id}">
      ${s.body ? `<p class="ad-body">${esc(s.body)}</p>` : ""}
      <div class="ad-grid">
        <label>Status <select name="status">${Object.entries(STATUS).map(([k, v]) => `<option value="${k}" ${k === s.status ? "selected" : ""}>${v}</option>`).join("")}</select></label>
        <label>Type <select name="category">${Object.entries(CATS).map(([k, v]) => `<option value="${k}" ${k === s.category ? "selected" : ""}>${v}</option>`).join("")}</select></label>
        <label class="ad-check"><input type="checkbox" name="public" ${s.public ? "checked" : ""}> Show on the public board</label>
        <label class="ad-check"><input type="checkbox" name="held" ${s.held ? "checked" : ""}> Hide (awaiting review)</label>
      </div>
      <label>Title <input name="title" value="${esc(s.title)}" maxlength="120"></label>
      <label>Public note from the team <span class="muted">(shown on the board and in emails)</span><textarea name="note" rows="2" maxlength="600">${esc(s.note)}</textarea></label>
      <div class="ad-actions">
        <button type="button" class="btn fb-primary" data-save="${s.id}">Save</button>
        ${s.watchers ? `<button type="button" class="btn btn-ghost" data-save="${s.id}" data-notify="1">Save and email ${s.watchers} follower${s.watchers === 1 ? "" : "s"}</button>` : ""}
        <button type="button" class="btn btn-ghost" data-ship="${s.id}">Mark implemented${s.watchers ? " and notify" : ""}</button>
        <button type="button" class="btn btn-ghost ad-danger" data-del="${s.id}">Delete</button>
      </div>
      <div class="ad-comments" data-comments="${s.id}"><p class="muted">Loading comments…</p></div>
      <form class="ad-reply" data-reply="${s.id}"><label>Reply publicly as the Frontier Wire team<textarea rows="2" maxlength="1200" required></textarea></label><button class="btn btn-ghost" type="submit">Post reply</button></form>
    </div>` : ""}</article>`;
}

async function loadComments(id) {
  const box = el.querySelector(`[data-comments="${id}"]`);
  if (!box) return;
  try {
    const j = await call(`/api/admin/item?id=${id}`);
    box.innerHTML = j.comments.length ? `<h4>Comments</h4><ul>${j.comments.map((c) => `<li class="${c.held ? "held" : ""}"><p><strong>${esc(c.team ? "Frontier Wire team" : c.name || "Reader")}</strong> · ${when(c.created)}${c.held ? " · <em>awaiting review</em>" : ""}</p><p>${esc(c.body)}</p>
      <p class="ad-cact">${c.held ? `<button type="button" class="fb-link" data-cmod="approve" data-cid="${c.id}">Approve</button> · ` : ""}<button type="button" class="fb-link ad-danger" data-cmod="delete" data-cid="${c.id}">Delete</button></p></li>`).join("")}</ul>` : `<p class="muted">No comments.</p>`;
  } catch (e) { box.innerHTML = `<p class="fb-err">${esc(e.message)}</p>`; }
}

// ------------------------------------------------------------------ review queue, history, system
function moderation() {
  const held = data.items.filter((s) => s.held);
  return `<p class="muted">Posts with links, rude words or all-caps wait here instead of going live. Obvious spam is never stored.</p>
    <h3>Ideas (${held.length})</h3>${held.length ? `<ul class="ad-queue">${held.map((s) => `<li><div><strong>${esc(s.title)}</strong>${s.body ? `<p>${esc(s.body)}</p>` : ""}<span class="muted">${when(s.created)}</span></div>
      <div><button type="button" class="btn fb-primary" data-approve="${s.id}">Publish</button> <button type="button" class="btn btn-ghost ad-danger" data-del="${s.id}">Delete</button></div></li>`).join("")}</ul>` : `<p class="muted">Nothing waiting.</p>`}
    <h3>Comments (${data.held_comments.length})</h3>${data.held_comments.length ? `<ul class="ad-queue">${data.held_comments.map((c) => `<li><div><p>${esc(c.body)}</p><span class="muted">${esc(c.name || "Reader")} on “${esc(c.title)}” · ${when(c.created)}</span></div>
      <div><button type="button" class="btn fb-primary" data-cmod="approve" data-cid="${c.id}">Publish</button> <button type="button" class="btn btn-ghost ad-danger" data-cmod="delete" data-cid="${c.id}">Delete</button></div></li>`).join("")}</ul>` : `<p class="muted">Nothing waiting.</p>`}`;
}

function historyTab() {
  return data.picks.length ? `<p class="muted">Every idea the weekly analysis has recommended, and what happened to it. Ideas picked in the last 12 weeks, or ever approved, aren't recommended again.</p>
    <div class="ad-scroll"><table class="ad-hist"><thead><tr><th>Week of</th><th>#</th><th>Idea</th><th>Score</th><th>Decision</th><th>Now</th></tr></thead><tbody>
    ${data.picks.map((p) => `<tr><td>${day(p.week)}</td><td>${p.rank}</td><td>${p.title ? `<button type="button" class="fb-link" data-goto="${p.sid}">${esc(p.title)}</button>` : "<em>deleted</em>"}</td><td>${Math.round(p.score)}</td>
      <td>${p.status === "pending" ? "Waiting" : p.status === "approved" ? "✓ Approved" : "✕ Rejected"}</td><td>${p.sstatus ? `<span class="fb-st st-${p.sstatus}">${STATUS[p.sstatus]}</span>` : ""}</td></tr>`).join("")}</tbody></table></div>
    ${data.reports.length > 1 ? `<h3>Earlier weekly summaries</h3><ul class="ad-list">${data.reports.slice(1).map((r) => `<li><strong>${day(r.week)}:</strong> ${esc(r.summary)}</li>`).join("")}</ul>` : ""}`
    : `<p class="muted">No recommendations yet.</p>`;
}

function system() {
  return `<p class="muted">The weekly analysis runs on the API every Monday at 09:05 IST (and retries the next mornings if it fails). It reads the past week's ideas, welcome-card messages, votes and comments,
    groups them with AI (free providers, with a rule-based fallback), scores each open idea (popularity 30%, frequency 15%, feasibility 20%, impact 20%, fit 15%) and emails you the top two.
    Spam protection: hidden honeypot field, a minimum typing time, per-address daily limits, a cap on votes from one network, and a review queue for links or rude words.</p>
    <h3>Recent activity and errors</h3><div class="ad-scroll"><table class="ad-log"><tbody>${data.log.map((l) => `<tr class="${l.level}"><td>${when(l.at)}</td><td>${esc(l.level)}</td><td>${esc(l.kind)}</td><td>${esc(l.msg)}</td></tr>`).join("") || `<tr><td>No activity yet.</td></tr>`}</tbody></table></div>`;
}

// ------------------------------------------------------------------ actions
el.addEventListener("click", async (e) => {
  const b = e.target.closest("button");
  if (!b || !data) return;
  try {
    if (b.dataset.tab) { tab = b.dataset.tab; render(); return; }
    if (b.dataset.act === "refresh") return load(true);
    if (b.dataset.act === "signout") return signOut();
    if (b.dataset.act === "analyze") {
      b.disabled = true; b.textContent = "Analysing… (up to a minute)";
      const r = await call("/api/admin/analyze", {});
      toast(r.skipped || `Done: ${(r.picks || []).length} picks.`); return load(true);
    }
    if (b.dataset.goto) { tab = "all"; filter = { status: "", source: "", vis: "", q: "" }; openRows.add(+b.dataset.goto); render(); loadComments(+b.dataset.goto); document.getElementById(`ad-${b.dataset.goto}`)?.scrollIntoView({ block: "center" }); return; }
    if (b.dataset.row) {
      const id = +b.dataset.row; openRows.has(id) ? openRows.delete(id) : openRows.add(id); render(); if (openRows.has(id)) loadComments(id); return;
    }
    if (b.dataset.decide) {
      if (b.dataset.decide === "approve" && !confirm("Approve this idea? It will show as Planned on the public board.")) return;
      await call("/api/admin/decide", { week: b.dataset.week, sid: +b.dataset.sid, decision: b.dataset.decide });
      toast(b.dataset.decide === "approve" ? "Approved and marked Planned." : "Rejected."); return load(true);
    }
    if (b.dataset.save || b.dataset.ship) {
      const id = +(b.dataset.save || b.dataset.ship), f = el.querySelector(`[data-edit="${id}"]`);
      const body = { id, status: b.dataset.ship ? "implemented" : f.querySelector("[name=status]").value, category: f.querySelector("[name=category]").value,
        public: f.querySelector("[name=public]").checked, held: f.querySelector("[name=held]").checked, title: f.querySelector("[name=title]").value,
        note: f.querySelector("[name=note]").value, notify: !!(b.dataset.notify || b.dataset.ship) };
      b.disabled = true;
      const r = await call("/api/admin/update", body);
      toast(`Saved.${r.notified ? ` Emailed ${r.notified}.` : ""}${r.remaining ? ` ${r.remaining} still to email: press again.` : ""}`); return load(true);
    }
    if (b.dataset.approve) { await call("/api/admin/update", { id: +b.dataset.approve, held: false }); toast("Published."); return load(true); }
    if (b.dataset.del) { if (!confirm("Delete this idea with its votes and comments? This can't be undone.")) return; await call("/api/admin/delete", { id: +b.dataset.del }); toast("Deleted."); return load(true); }
    if (b.dataset.cmod) { await call("/api/admin/comment", { cid: +b.dataset.cid, action: b.dataset.cmod }); toast(b.dataset.cmod === "delete" ? "Comment deleted." : "Comment published."); return load(true); }
  } catch (ex) { b.disabled = false; toast(ex.message, true); }
});
el.addEventListener("change", (e) => { const f = e.target.dataset.filter; if (f && f !== "q") { filter[f] = e.target.value; render(); } });
el.addEventListener("input", (e) => {
  if (e.target.dataset.filter === "q") {
    filter.q = e.target.value; const pos = e.target.selectionStart; render();
    const s = el.querySelector("[data-filter=q]"); s.focus(); s.setSelectionRange(pos, pos);
  }
});
el.addEventListener("submit", async (e) => {
  const f = e.target.closest("[data-reply]"); if (!f) return;
  e.preventDefault();
  try { await call("/api/admin/reply", { id: +f.dataset.reply, body: f.querySelector("textarea").value }); toast("Reply posted."); load(true); }
  catch (ex) { toast(ex.message, true); }
});
