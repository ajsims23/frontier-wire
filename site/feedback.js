// Community feedback on Frontier Wire (no account needed):
//  - the welcome card: shown once to a first-time visitor, a while after they arrive. "Maybe later" brings it back
//    once, a few days on; the close button or sending feedback means it never shows again.
//  - the suggestions board (/suggestions/): post ideas (similar ideas are shown first so people vote instead of
//    posting duplicates), vote, comment, follow by email, and filter by status.
const mount = document.getElementById("fw-feedback");
const board = document.querySelector("[data-board]");
const api = ((board || mount)?.dataset.api || "").replace(/\/$/, "");
const root = [board, mount].map((el) => el && el.dataset.root).find((r) => r != null) ?? "/";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
};
// a random id for this browser: lets the server count one vote per person without an account (it only keeps a hash)
function visitor() {
  let v = store.get("fw-visitor");
  if (!/^[A-Za-z0-9_-]{16,64}$/.test(v || "")) {
    v = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(18)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    store.set("fw-visitor", v);
  }
  return v;
}
async function post(path, body) {
  const r = await fetch(`${api}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ v: visitor(), ...body }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(j.error || "Something went wrong. Please try again."); e.data = j; throw e; }
  return j;
}
async function get(path) {
  const r = await fetch(`${api}${path}`);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Couldn't load suggestions. Please try again.");
  return j;
}
const ago = (iso) => {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  if (s < 86400 * 30) return `${Math.round(s / 86400)} d ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
};
const STATUS = { open: "Open", under_consideration: "Under consideration", planned: "Planned", in_progress: "In progress", implemented: "Implemented", declined: "Not planned" };
const CATS = { feature: "Feature", coverage: "Coverage", design: "Design", ask: "Ask the Wire", bug: "Bug", other: "Other" };
const HP = `<label class="fb-hp" aria-hidden="true">Leave this empty <input name="website" tabindex="-1" autocomplete="off"></label>`;

if (api && mount && !board && !/\/(admin|suggestions)\/?$/.test(location.pathname)) welcome();
if (api && board) suggestionsBoard();

// ------------------------------------------------------------------ the welcome card
function welcome() {
  const KEY = "fw-welcome";
  const st = store.get(KEY) || {};
  if (st.state === "done") return;
  if (st.state === "later" && Date.now() - st.at < 3 * 86400000) return;
  if (!st.first) store.set(KEY, { ...st, first: Date.now() });
  let shown = false;
  const show = () => {
    if (shown || document.hidden) return;
    const chat = document.querySelector(".fwc-pop");
    if (chat && !chat.hidden) return;   // don't interrupt a conversation; try again on the next trigger
    shown = true;
    removeEventListener("scroll", onScroll);
    render();
  };
  const onScroll = () => { if (scrollY > (document.documentElement.scrollHeight - innerHeight) * 0.35) show(); };
  addEventListener("scroll", onScroll, { passive: true });
  setTimeout(show, st.state === "later" ? 4000 : 15000);
  setTimeout(() => { if (!shown) show(); }, 45000);

  function render() {
    const opened = Date.now();
    const card = document.createElement("aside");
    card.className = "fb-welcome";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-labelledby", "fbw-title");
    card.innerHTML = `
      <button type="button" class="fb-x" aria-label="Close and don't show again"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
      <div class="fbw-body">
        <p class="fbw-kicker"><span aria-hidden="true">✦</span> Welcome to Frontier Wire!</p>
        <h2 id="fbw-title">What would you like to see on Frontier Wire?</h2>
        <p class="fbw-text">We're building a better way to explore and understand the world of AI. We'd love to hear your thoughts.</p>
        <form class="fbw-form">
          <label class="sr" for="fbw-text">Your suggestion</label>
          <textarea id="fbw-text" rows="3" maxlength="1500" placeholder="A feature, a topic you want covered, something to fix…" required></textarea>
          ${HP}
          <label class="fbw-share"><input type="checkbox" name="public"><span>Also post it on the public <a href="${root}suggestions/" target="_blank" rel="noopener">suggestions board</a> so others can vote</span></label>
          <p class="fb-err" role="alert" hidden></p>
          <div class="fbw-actions">
            <button class="btn fb-primary" type="submit">Send feedback</button>
            <button class="fb-later" type="button">Maybe later</button>
          </div>
          <p class="fbw-fine">No account needed. We don't collect your name or email here.</p>
        </form>
      </div>`;
    document.body.append(card);
    requestAnimationFrame(() => card.classList.add("in"));
    const close = (state) => {
      const prev = store.get(KEY) || {};
      // "later" works once: the second time the card shows, any answer closes it for good
      store.set(KEY, { ...prev, state: state === "later" && !prev.laterUsed ? "later" : "done", laterUsed: prev.laterUsed || state === "later", at: Date.now() });
      card.classList.remove("in");
      setTimeout(() => card.remove(), 250);
      document.removeEventListener("keydown", onKey);
    };
    const onKey = (e) => { if (e.key === "Escape") close("later"); };
    document.addEventListener("keydown", onKey);
    card.querySelector(".fb-x").addEventListener("click", () => close("done"));
    card.querySelector(".fb-later").addEventListener("click", () => close("later"));
    const form = card.querySelector("form");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = form.querySelector("[type=submit]"), err = form.querySelector(".fb-err");
      const text = form.querySelector("textarea").value.trim();
      if (text.length < 4) { err.textContent = "Write a few words first."; err.hidden = false; return; }
      btn.disabled = true; btn.textContent = "Sending…"; err.hidden = true;
      try {
        const r = await post("/api/feedback/popup", { text, public: form.public.checked, hp: form.website.value, ms: Date.now() - opened });
        store.set(KEY, { state: "done", at: Date.now() });
        card.querySelector(".fbw-body").innerHTML = `<p class="fbw-kicker"><span aria-hidden="true">✓</span> Thank you!</p>
          <h2 id="fbw-title">We read every suggestion.</h2>
          <p class="fbw-text">Every Monday we review all feedback and pick the ideas to work on next.${r.id ? " Yours is on the board now." : ""}</p>
          <div class="fbw-actions"><a class="btn fb-primary" href="${root}suggestions/${r.id ? `#s-${r.id}` : ""}">See the suggestions board</a><button class="fb-later" type="button">Close</button></div>`;
        card.querySelector(".fb-later").addEventListener("click", () => close("done"));
        setTimeout(() => card.isConnected && close("done"), 12000);
      } catch (ex) {
        err.textContent = ex.message; err.hidden = false; btn.disabled = false; btn.textContent = "Send feedback";
      }
    });
  }
}

// ------------------------------------------------------------------ the suggestions board
function suggestionsBoard() {
  const opened = Date.now();
  const $ = (s) => board.querySelector(s);
  board.innerHTML = `
    <div class="fb-grid">
      <section class="fb-compose" aria-labelledby="fb-new">
        <h2 id="fb-new">Suggest an idea</h2>
        <form class="fb-form" novalidate>
          <label for="fb-title">Your idea in one line</label>
          <input id="fb-title" name="title" maxlength="120" autocomplete="off" placeholder="e.g. A weekly roundup of open-source models" required>
          <div class="fb-similar" aria-live="polite" hidden></div>
          <label for="fb-body">Details <span>(optional)</span></label>
          <textarea id="fb-body" name="body" rows="4" maxlength="1500" placeholder="What problem would it solve? How would you use it?"></textarea>
          <div class="fb-row">
            <div><label for="fb-cat">Type</label>
              <select id="fb-cat" name="category">${Object.entries(CATS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></div>
            <div><label for="fb-name">Name <span>(optional)</span></label><input id="fb-name" name="name" maxlength="40" autocomplete="nickname" placeholder="Shown with your idea"></div>
          </div>
          <label for="fb-email">Email me when it moves <span>(optional, never shown)</span></label>
          <input id="fb-email" name="email" type="email" maxlength="200" autocomplete="email" placeholder="you@example.com">
          ${HP}
          <p class="fb-err" role="alert" hidden></p>
          <button class="btn fb-primary" type="submit">Post idea</button>
          <p class="fb-fine">Ideas with links or rude words wait for a quick review before they appear.</p>
        </form>
        <div class="fb-how">
          <h3>How ideas get picked</h3>
          <ol><li><strong>You post and vote.</strong> The best ideas rise to the top.</li>
            <li><strong>Every Monday, AI reviews all feedback.</strong> It groups similar ideas, weighs popularity, impact and effort, and recommends two.</li>
            <li><strong>A person decides.</strong> Approved ideas move to Planned, and you can follow them here until they ship.</li></ol>
        </div>
      </section>
      <section class="fb-list-wrap" aria-label="Suggestions">
        <div class="fb-toolbar">
          <div class="fb-sort" role="tablist" aria-label="Sort">
            <button type="button" role="tab" data-sort="top" aria-selected="true">Top</button><button type="button" role="tab" data-sort="new" aria-selected="false">New</button>
          </div>
          <label class="fb-search"><span class="sr">Search suggestions</span><input type="search" placeholder="Search ideas" maxlength="80"></label>
        </div>
        <div class="fb-status" role="group" aria-label="Filter by status"></div>
        <div class="fb-list"><p class="fb-loading">Loading suggestions…</p></div>
      </section>
    </div>`;

  let items = [], voted = new Set(), mine = new Set(), counts = {}, sort = "top", status = "all", query = "";
  const open = new Map();   // id -> loaded comments

  async function load() {
    try {
      const j = await get(`/api/feedback/list?v=${encodeURIComponent(visitor())}`);
      items = j.items; voted = new Set(j.voted); mine = new Set(j.mine); counts = j.counts || {};
      renderStats(); renderFilters(); renderList();
      const m = location.hash.match(/^#s-(\d+)$/);
      if (m) expand(+m[1], true);
    } catch (e) {
      $(".fb-list").innerHTML = `<p class="fb-err">${esc(e.message)} <button type="button" class="fb-link fb-retry">Retry</button></p>`;
      $(".fb-retry").addEventListener("click", load);
    }
  }

  function renderStats() {
    const el = document.querySelector("[data-board-stats]");
    if (!el) return;
    const votes = items.reduce((a, s) => a + s.votes, 0);
    el.innerHTML = [["Ideas", items.length], ["Votes", votes], ["Planned or in progress", (counts.planned || 0) + (counts.in_progress || 0)], ["Implemented", counts.implemented || 0]]
      .map(([l, n]) => `<div><strong>${n}</strong><span>${l}</span></div>`).join("");
  }

  function renderFilters() {
    const keys = ["all", "open", "under_consideration", "planned", "in_progress", "implemented"];
    $(".fb-status").innerHTML = keys.map((k) => {
      const n = k === "all" ? items.filter((s) => s.status !== "declined").length : counts[k] || 0;
      return `<button type="button" class="fb-chip ${k === status ? "on" : ""}" data-status="${k}" aria-pressed="${k === status}">${k === "all" ? "All" : STATUS[k]} <span>${n}</span></button>`;
    }).join("") + ((counts.declined || 0) ? `<button type="button" class="fb-chip ${status === "declined" ? "on" : ""}" data-status="declined" aria-pressed="${status === "declined"}">Not planned <span>${counts.declined}</span></button>` : "");
  }

  function card(s) {
    const isOpen = open.has(s.id);
    return `<article class="fb-card ${isOpen ? "open" : ""}" id="s-${s.id}">
      <button type="button" class="fb-vote ${voted.has(s.id) ? "on" : ""}" data-vote="${s.id}" aria-pressed="${voted.has(s.id)}" aria-label="${voted.has(s.id) ? "Remove your vote" : "Vote for this idea"} (${s.votes} vote${s.votes === 1 ? "" : "s"})">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 15l6-6 6 6"/></svg><b>${s.votes}</b></button>
      <div class="fb-main">
        <h3><button type="button" class="fb-open" data-open="${s.id}" aria-expanded="${isOpen}">${esc(s.title)}</button></h3>
        ${s.body ? `<p class="fb-body ${isOpen ? "" : "clamp"}">${esc(s.body)}</p>` : ""}
        <p class="fb-meta"><span class="fb-st st-${s.status}">${STATUS[s.status] || s.status}</span><span>${CATS[s.category] || "Idea"}</span><span>${esc(s.name)}${mine.has(s.id) ? " (you)" : ""}</span><span>${ago(s.created)}</span>
          <button type="button" class="fb-link" data-open="${s.id}">${s.comments} comment${s.comments === 1 ? "" : "s"}</button></p>
        ${s.note ? `<p class="fb-note"><strong>From the team:</strong> ${esc(s.note)}</p>` : ""}
        ${isOpen ? thread(s) : ""}
      </div></article>`;
  }

  function thread(s) {
    const cs = open.get(s.id);
    return `<div class="fb-thread">
      ${cs === null ? `<p class="fb-loading">Loading comments…</p>` : (cs || []).length ? `<ul class="fb-comments">${cs.map((c) => `<li class="${c.team ? "team" : ""}"><p class="fb-cmeta"><strong>${esc(c.name)}</strong> · ${ago(c.created)}</p><p>${esc(c.body)}</p></li>`).join("")}</ul>` : `<p class="fb-empty-c">No comments yet. Add the first.</p>`}
      <form class="fb-cform" data-comment="${s.id}">
        <label class="sr" for="fbc-${s.id}">Your comment</label>
        <textarea id="fbc-${s.id}" rows="2" maxlength="800" placeholder="Add a comment: how would you use it?" required></textarea>
        ${HP}
        <div class="fb-row fb-crow"><label class="sr" for="fbn-${s.id}">Name (optional)</label><input id="fbn-${s.id}" name="name" maxlength="40" placeholder="Name (optional)"><button class="btn fb-primary" type="submit">Comment</button></div>
        <p class="fb-err" role="alert" hidden></p>
      </form>
      ${["implemented", "declined"].includes(s.status) ? "" : `<form class="fb-watch" data-watch="${s.id}"><label for="fbw-${s.id}">Email me when this moves</label>
        <div class="fb-row fb-crow"><input id="fbw-${s.id}" type="email" maxlength="200" placeholder="you@example.com" required><button class="btn btn-ghost" type="submit">Follow</button></div>
        <p class="fb-err" role="alert" hidden></p></form>`}
    </div>`;
  }

  function visible() {
    let list = items.filter((s) => (status === "all" ? s.status !== "declined" : s.status === status));
    if (query) { const q = query.toLowerCase(); list = list.filter((s) => `${s.title} ${s.body}`.toLowerCase().includes(q)); }
    return sort === "new" ? [...list].sort((a, b) => b.created.localeCompare(a.created)) : list;
  }

  function renderList() {
    const list = visible();
    $(".fb-list").innerHTML = list.length ? list.map(card).join("")
      : `<div class="fb-empty"><p><strong>${items.length ? "Nothing here yet." : "No ideas yet. Be the first!"}</strong></p><p>${items.length ? "Try another filter, or post the idea yourself." : "Post an idea on the left, and others can vote for it."}</p></div>`;
  }

  async function expand(id, scroll) {
    if (open.has(id)) { open.delete(id); renderList(); return; }
    open.set(id, null); renderList();
    if (scroll) document.getElementById(`s-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    try { const j = await get(`/api/feedback/item?id=${id}`); open.set(id, j.comments); const i = items.findIndex((s) => s.id === id); if (i >= 0) items[i] = j.item; }
    catch (e) { open.set(id, []); }
    renderList();
  }

  async function vote(id, btn) {
    btn.disabled = true;
    try {
      const r = await post("/api/feedback/vote", { id });
      r.voted ? voted.add(id) : voted.delete(id);
      const s = items.find((x) => x.id === id); if (s) s.votes = r.votes;
      if (sort === "top") items.sort((a, b) => b.votes - a.votes || b.created.localeCompare(a.created));
      renderList(); renderStats(); simCheck(true);
    } catch (e) { btn.disabled = false; toast(e.message); }
  }

  function toast(msg) {
    const t = document.createElement("div"); t.className = "fb-toast"; t.setAttribute("role", "status"); t.textContent = msg;
    document.body.append(t); setTimeout(() => t.remove(), 4000);
  }

  board.addEventListener("click", (e) => {
    const v = e.target.closest("[data-vote]"); if (v) return vote(+v.dataset.vote, v);
    const o = e.target.closest("[data-open]"); if (o) { history.replaceState(null, "", `#s-${o.dataset.open}`); return expand(+o.dataset.open); }
    const st = e.target.closest("[data-status]"); if (st) { status = st.dataset.status; renderFilters(); renderList(); return; }
    const so = e.target.closest("[data-sort]");
    if (so) { sort = so.dataset.sort; board.querySelectorAll("[data-sort]").forEach((b) => b.setAttribute("aria-selected", String(b === so))); renderList(); }
  });
  $(".fb-search input").addEventListener("input", (e) => { query = e.target.value.trim(); renderList(); });

  board.addEventListener("submit", async (e) => {
    const f = e.target;
    if (f.matches("[data-comment]")) {
      e.preventDefault();
      const id = +f.dataset.comment, err = f.querySelector(".fb-err"), btn = f.querySelector("[type=submit]");
      btn.disabled = true; err.hidden = true;
      try {
        const r = await post("/api/feedback/comment", { id, body: f.querySelector("textarea").value, name: f.name.value, hp: f.website.value, ms: Date.now() - opened });
        if (r.held) toast("Thanks! Your comment will appear after a quick review.");
        else if (r.comment) { open.set(id, [...(open.get(id) || []), r.comment]); const s = items.find((x) => x.id === id); if (s) s.comments++; }
        renderList();
      } catch (ex) { err.textContent = ex.message; err.hidden = false; btn.disabled = false; }
    }
    if (f.matches("[data-watch]")) {
      e.preventDefault();
      const err = f.querySelector(".fb-err");
      try { await post("/api/feedback/watch", { id: +f.dataset.watch, email: f.querySelector("input").value }); f.innerHTML = `<p class="fb-ok">✓ We'll email you when this idea moves. Your address is deleted once it ships.</p>`; }
      catch (ex) { err.textContent = ex.message; err.hidden = false; }
    }
  });

  // similar ideas while typing a title
  const form = $(".fb-form"), sim = $(".fb-similar");
  let simTimer = 0, simSeq = 0;
  async function simCheck(now) {
    clearTimeout(simTimer);
    const q = `${form.title.value} ${form.body.value}`.trim();
    if (q.length < 6) { sim.hidden = true; return; }
    simTimer = setTimeout(async () => {
      const seq = ++simSeq;
      try {
        const j = await get(`/api/feedback/similar?q=${encodeURIComponent(q.slice(0, 200))}`);
        if (seq !== simSeq) return;
        sim.hidden = !j.items.length;
        sim.innerHTML = j.items.length ? `<p><strong>Similar ideas already on the board.</strong> If one matches, vote for it instead:</p>
          <ul>${j.items.map((s) => `<li><button type="button" class="fb-vote sm ${voted.has(s.id) ? "on" : ""}" data-vote="${s.id}" aria-pressed="${voted.has(s.id)}" aria-label="Vote for ${esc(s.title)}"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M6 15l6-6 6 6"/></svg><b>${(items.find((x) => x.id === s.id) || s).votes}</b></button>
            <a href="#s-${s.id}" data-open="${s.id}">${esc(s.title)}</a> <span class="fb-st st-${s.status}">${STATUS[s.status]}</span></li>`).join("")}</ul>` : "";
      } catch (e) { sim.hidden = true; }
    }, now === true ? 0 : 380);
  }
  form.title.addEventListener("input", simCheck);
  form.body.addEventListener("input", simCheck);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = form.querySelector(".fb-err"), btn = form.querySelector("[type=submit]");
    if (form.title.value.trim().length < 8) { err.textContent = "Give your idea a title of at least a few words."; err.hidden = false; form.title.focus(); return; }
    if (form.email.value && !form.email.checkValidity()) { err.textContent = "That email doesn't look right (or leave it empty)."; err.hidden = false; return; }
    btn.disabled = true; btn.textContent = "Posting…"; err.hidden = true;
    try {
      const r = await post("/api/feedback/suggest", { title: form.title.value, body: form.body.value, category: form.category.value, name: form.name.value,
        email: form.email.value, hp: form.website.value, ms: Date.now() - opened });
      form.reset(); sim.hidden = true;
      if (r.held) toast("Thanks! Your idea will appear after a quick review.");
      else if (r.item) {
        items.unshift(r.item); voted.add(r.item.id); mine.add(r.item.id); counts.open = (counts.open || 0) + 1;
        status = "all"; sort = "new";
        board.querySelectorAll("[data-sort]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.sort === "new")));
        renderStats(); renderFilters(); renderList();
        document.getElementById(`s-${r.item.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
        document.getElementById(`s-${r.item.id}`)?.classList.add("fresh");
        toast("Posted! Share it so others can vote.");
      }
    } catch (ex) {
      err.textContent = ex.message; err.hidden = false;
      if (ex.data && ex.data.id) { err.innerHTML = `${esc(ex.message)} <a href="#s-${ex.data.id}" data-open="${ex.data.id}">See it</a>`; }
    }
    btn.disabled = false; btn.textContent = "Post idea";
  });

  load();
}
