// Ask the Wire: a conversation with the Frontier Wire Analyst (an AI industry analyst with live research).
// Mounts as a floating chat button on every page, or as the full page on /ask/ (an element with data-chat-page).
// The conversation is kept for this browser tab (sessionStorage), so it survives moving between pages.
const mount = document.getElementById("fw-chat");
const pageEl = document.querySelector("[data-chat-page]");
const host = pageEl || mount;
const api = ((host && host.dataset.api) || (mount && mount.dataset.api) || "").replace(/\/$/, "");
const root = [host, mount].map((el) => el && el.dataset.root).find((r) => r != null) ?? "/";
const KEY = "fw-chat-v1";
const EXAMPLES = ["What are the biggest AI stories this week?", "Compare the latest models from OpenAI, Anthropic and Google",
  "Explain what an AI agent actually is", "What's happening with Nvidia and China?", "Which AI startups raised money recently?"];

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const short = (d) => { const t = new Date(d); return isNaN(t) ? "" : t.toLocaleDateString(undefined, { day: "numeric", month: "short", year: t.getFullYear() === new Date().getFullYear() ? undefined : "numeric" }); };
let state = { turns: [] };   // [{q, a: {answer, sources, followups} | null, error}]
try { state = JSON.parse(sessionStorage.getItem(KEY)) || state; } catch (e) { /* private mode: keep it in memory */ }
const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify({ turns: state.turns.slice(-12) })); } catch (e) { /* ok */ } };

if (host && api) build();

function build() {
  const page = !!pageEl;
  const box = document.createElement("section");
  box.className = `fwc ${page ? "fwc-page" : "fwc-pop"}`;
  box.setAttribute("aria-label", "Ask the Wire");
  box.innerHTML = `
    <header class="fwc-head">
      <div class="fwc-title"><span class="fwc-dot" aria-hidden="true"></span><div><strong>Ask the Wire</strong><span>AI analyst · live research · cited</span></div></div>
      <div class="fwc-actions">
        <button type="button" class="fwc-icon fwc-new" title="New conversation" aria-label="New conversation"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg></button>
        ${page ? "" : `<a class="fwc-icon" href="${root}ask/" title="Open full page" aria-label="Open full page"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 4h6v6M20 4l-8 8M10 4H4v16h16v-6"/></svg></a>
        <button type="button" class="fwc-icon fwc-close" title="Close" aria-label="Close"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>`}
      </div>
    </header>
    <div class="fwc-log" aria-live="polite"></div>
    <form class="fwc-form">
      <label class="sr" for="fwc-q${page ? "-p" : ""}">Ask about anything in AI</label>
      <textarea id="fwc-q${page ? "-p" : ""}" rows="1" maxlength="300" placeholder="Ask about any AI news, model, company or idea…"></textarea>
      <button class="fwc-send" type="submit" aria-label="Send"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
    </form>
    <p class="fwc-foot">AI answers can be wrong. <b class="b-ver">Verified</b> = checked by our newsroom; <b class="b-rep">Reported</b> = news coverage; check the sources.</p>`;
  const log = box.querySelector(".fwc-log"), form = box.querySelector(".fwc-form"), input = box.querySelector("textarea");
  let busy = false, launcher = null;

  if (page) pageEl.replaceChildren(box);
  else {
    launcher = document.createElement("button");
    launcher.type = "button"; launcher.className = "fwc-launch";
    launcher.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg><span>Ask the Wire</span>`;
    launcher.setAttribute("aria-expanded", "false");
    mount.append(launcher, box);
    box.hidden = true;
    const open = (yes) => {
      box.hidden = !yes; launcher.hidden = yes; launcher.setAttribute("aria-expanded", String(yes));
      try { sessionStorage.setItem(KEY + "-open", yes ? "1" : ""); } catch (e) { /* ok */ }
      if (yes) { render(); setTimeout(() => input.focus(), 50); }
    };
    launcher.addEventListener("click", () => open(true));
    box.querySelector(".fwc-close").addEventListener("click", () => open(false));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !box.hidden) open(false); });
    try { if (sessionStorage.getItem(KEY + "-open") && state.turns.length) open(true); } catch (e) { /* ok */ }
    // sit above the podcast player's button when it's showing
    const dodge = () => {
      let lift = 0;
      for (const el of document.querySelectorAll(".pod-launch, .pod")) {
        if (el.hidden || getComputedStyle(el).display === "none" || getComputedStyle(el).position !== "fixed") continue;
        const r = el.getBoundingClientRect();
        if (r.height && r.right > innerWidth - 260) lift = Math.max(lift, innerHeight - r.top + 10);
      }
      mount.style.setProperty("--fwc-lift", lift ? `${Math.round(lift)}px` : "");
    };
    dodge(); setInterval(dodge, 1500);
  }

  box.querySelector(".fwc-new").addEventListener("click", () => { state.turns = []; save(); render(); input.focus(); });
  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); } });
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 140) + "px"; });
  log.addEventListener("click", (e) => {
    const b = e.target.closest("[data-q]");
    if (b) send(b.dataset.q);
    const t = e.target.closest(".fwc-srctoggle");
    if (t) { const list = t.nextElementSibling; list.hidden = !list.hidden; t.setAttribute("aria-expanded", String(!list.hidden)); }
  });

  function render() {
    if (!state.turns.length) {
      log.innerHTML = `<div class="fwc-hello"><p><strong>Hi, I'm the Frontier Wire analyst.</strong> Ask me about anything in AI: the latest news, models,
        companies, research or ideas. I search our newsroom's checked stories and the live web, and I cite everything.</p>
        <div class="fwc-chips">${EXAMPLES.map((q) => `<button type="button" class="fwc-chip" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div></div>`;
      return;
    }
    log.innerHTML = state.turns.map((t, i) => `<div class="fwc-q">${esc(t.q)}</div>${t.a ? answerHtml(t.a, i) : t.error ? `<div class="fwc-a fwc-err">${esc(t.error)}</div>`
      : `<div class="fwc-a fwc-thinking"><span class="dots"><i></i><i></i><i></i></span> Researching our archive and the live news…</div>`}`).join("");
    log.scrollTop = log.scrollHeight;
  }

  function badge(s) {
    if (s.kind === "frontier") return `<span class="fwc-b b-ver">Verified · Frontier Wire</span>`;
    if (s.kind === "web") return `<span class="fwc-b b-web">Web</span>`;
    return `<span class="fwc-b b-rep">Reported</span>`;
  }

  function answerHtml(a, i) {
    const srcs = a.sources || [];
    const byN = new Map(srcs.map((s) => [s.n, s]));
    const href = (s) => (s.kind === "frontier" ? `${root}story/${encodeURIComponent(s.id)}/` : (/^https:\/\//.test(s.url || "") ? s.url : "#"));
    const cite = (n) => { const s = byN.get(+n); return s ? `<a class="fwc-cite" href="${esc(href(s))}" ${s.kind === "frontier" ? "" : 'target="_blank" rel="noopener"'} title="${esc(s.headline)}">${n}</a>` : ""; };
    const shown = srcs.filter((s) => s.cited);
    const rest = srcs.filter((s) => !s.cited && s.kind === "frontier").slice(0, 3);
    const list = [...shown, ...rest];
    return `<div class="fwc-a">${md(a.answer || "We couldn't write an answer this time.", cite)}
      ${list.length ? `<button type="button" class="fwc-srctoggle" aria-expanded="${i === state.turns.length - 1}">${shown.length} source${shown.length === 1 ? "" : "s"}${rest.length ? ` · ${rest.length} related` : ""}</button>
      <ol class="fwc-src" ${i === state.turns.length - 1 ? "" : "hidden"}>${list.map((s) => `<li><span class="fwc-n">${s.cited ? s.n : "·"}</span><div>
        <a href="${esc(href(s))}" ${s.kind === "frontier" ? "" : 'target="_blank" rel="noopener"'}>${esc(s.headline)}</a>
        <span class="fwc-meta">${badge(s)}${s.kind !== "frontier" && s.publisher ? ` ${esc(s.publisher)}` : ""}${s.date ? ` · ${esc(short(s.date))}` : ""}</span></div></li>`).join("")}</ol>` : ""}
      ${i === state.turns.length - 1 && (a.followups || []).length ? `<div class="fwc-chips fwc-next">${a.followups.map((q) => `<button type="button" class="fwc-chip" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div>` : ""}</div>`;
  }

  async function send(q) {
    q = String(q || "").trim();
    if (busy || q.length < 3) return;
    busy = true; input.value = ""; input.style.height = "auto";
    const history = state.turns.filter((t) => t.a && t.a.answer).slice(-3).flatMap((t) => [{ role: "user", content: t.q }, { role: "assistant", content: t.a.answer }]);
    state.turns.push({ q, a: null }); render();
    const turn = state.turns[state.turns.length - 1];
    try {
      const r = await fetch(`${api}/api/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ q, history, mode: "chat" }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || "The analyst is busy right now. Try again in a minute.");
      turn.a = j.answer ? { answer: j.answer, sources: j.sources || [], followups: j.followups || [] } : null;
      if (!turn.a) turn.error = "We couldn't write an answer this time. Try rephrasing, or ask again in a minute.";
    } catch (e) {
      turn.error = e.message && e.message !== "Failed to fetch" ? e.message : "Couldn't reach the analyst. Check your connection and try again.";
    }
    busy = false; save(); render(); input.focus();
  }

  // a tiny, safe Markdown: paragraphs, bullets, numbered lists, **bold**, simple tables, and [n] citations
  function md(text, cite) {
    const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|\s)\*(\S[^*]*?)\*(?=\s|$|[.,;:])/g, "$1<em>$2</em>")
      .replace(/^(?:<strong>)?Speculation:(?:<\/strong>)?/, '<span class="fwc-spec">Speculation:</span>')
      .replace(/\[(\d+(?:,\s*\d+)*)\]/g, (m, nums) => `<sup class="fwc-cites">${nums.split(",").map((n) => cite(n.trim())).join("")}</sup>`);
    const lines = String(text).split("\n");
    let html = "", list = null, table = [];
    const flush = () => { if (list) { html += `</${list}>`; list = null; } if (table.length) { html += tableHtml(table); table = []; } };
    const tableHtml = (rows) => {
      const cells = rows.filter((r) => !/^\s*\|?\s*:?-{2,}/.test(r)).map((r) => r.replace(/^\s*\||\|\s*$/g, "").split("|").map((c) => inline(c.trim())));
      if (!cells.length) return "";
      return `<div class="fwc-table"><table><thead><tr>${cells[0].map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${cells.slice(1).map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    };
    for (const raw of lines) {
      const l = raw.trimEnd();
      if (/^\s*\|.*\|\s*$/.test(l)) { if (list) { html += `</${list}>`; list = null; } table.push(l); continue; }
      if (table.length) { html += tableHtml(table); table = []; }
      const b = l.match(/^\s*[-*•]\s+(.*)/), n = l.match(/^\s*\d+[.)]\s+(.*)/), h = l.match(/^\s*#{1,4}\s+(.*)/);
      if (b || n) {
        const want = b ? "ul" : "ol";
        if (list !== want) { if (list) html += `</${list}>`; html += `<${want}>`; list = want; }
        html += `<li>${inline((b || n)[1])}</li>`;
      } else if (!l.trim()) { flush(); }
      else { flush(); html += h ? `<p class="fwc-h">${inline(h[1])}</p>` : `<p>${inline(l)}</p>`; }
    }
    flush();
    return html;
  }

  render();
  if (page) {
    const q0 = new URLSearchParams(location.search).get("q");
    if (q0 && !state.turns.some((t) => t.q === q0)) send(q0);
  }
}
