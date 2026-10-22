// Frontier Wire front page — renders data/site.json written by the newsroom agent.
(function () {
  "use strict";

  const LANES = [
    { id: "models", label: "Models", cats: ["models"] },
    { id: "research", label: "Research", cats: ["research"] },
    { id: "policy", label: "Policy & safety", cats: ["policy", "safety"] },
    { id: "industry", label: "Industry", cats: ["industry"] },
    { id: "voices", label: "Voices", cats: ["voices"] },
  ];
  const CAT_NAME = { models: "Model release", research: "Research", policy: "Policy", safety: "Safety", industry: "Industry", voices: "Commentary" };
  const color = (cat) => `var(--${CAT_NAME[cat] ? cat : "models"})`;
  const laneOf = (cat) => LANES.findIndex((l) => l.cats.includes(cat));
  const DAY = 86400000;

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? esc(u) : "#");
  const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; } };

  function ago(iso) {
    const t = new Date(iso).getTime();
    if (isNaN(t)) return "";
    const m = Math.round((Date.now() - t) / 60000);
    if (m < 60) return `${Math.max(m, 1)} min ago`;
    if (m < 1440) return `${Math.round(m / 60)}h ago`;
    const d = Math.round(m / 1440);
    return d < 7 ? `${d} day${d > 1 ? "s" : ""} ago` : new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  }
  const clip = (t, n) => { t = String(t || ""); if (t.length <= n) return t; return t.slice(0, n).replace(/\s+\S*$/, "") + "…"; };

  // ---------------------------------------------------------------- pictures
  // Each story shows its source's preview image. Underneath sits generated "signal" art
  // (unique per story, in its topic colour) that shows whenever there's no image or it fails to load.
  const hash = (t) => { let h = 2166136261; for (const ch of String(t)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
  function rng(seed) { return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function art(s) {
    const r = rng(hash(s.id || s.url || s.headline));
    const W = 400, H = 225, lines = 6 + Math.floor(r() * 4);
    const cx = 80 + r() * 240, spread = 40 + r() * 70;
    let paths = "", peak = null;
    for (let i = 0; i < lines; i++) {
      const y0 = 38 + (i * (H - 70)) / (lines - 1);
      const amp = 8 + r() * (i === 2 ? 70 : 34), freq = 2 + r() * 5, phase = r() * 6.28;
      let d = "";
      for (let x = 0; x <= W; x += 8) {
        const env = Math.exp(-(((x - cx) / spread) ** 2));
        const y = y0 - amp * env * Math.abs(Math.sin((x / W) * 6.28 * freq + phase)) - 3 * Math.sin(x / 23 + i);
        d += `${x ? "L" : "M"}${x} ${y.toFixed(1)}`;
        if (i === 2 && (!peak || y < peak[1])) peak = [x, y];
      }
      const main = i === 2;
      paths += `<path d="${d}" fill="none" stroke="${main ? "var(--c)" : "var(--soft)"}" stroke-width="${main ? 2.2 : 1}" stroke-opacity="${main ? 1 : (0.14 + r() * 0.22).toFixed(2)}"/>`;
    }
    return `<svg class="art" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="${W}" height="${H}" fill="var(--panel-2)"/>
      <rect x="${(cx - spread).toFixed(0)}" width="${(spread * 2).toFixed(0)}" height="${H}" fill="var(--c)" opacity=".07"/>
      ${paths}
      <circle cx="${peak[0]}" cy="${peak[1].toFixed(1)}" r="5" fill="var(--c)"/><circle cx="${peak[0]}" cy="${peak[1].toFixed(1)}" r="12" fill="var(--c)" opacity=".18"/>
    </svg>`;
  }
  const imgOk = (u) => /^https:\/\//i.test(u || "");
  function media(s, cls) {
    return `<div class="media ${cls}" style="--c:${color(s.category)}">${art(s)}${imgOk(s.image)
      ? `<img src="${esc(s.image)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ""}</div>`;
  }
  // a picture that fails to load is removed, revealing the generated art beneath it
  document.addEventListener("error", (e) => { const t = e.target; if (t.tagName === "IMG" && t.parentElement && t.parentElement.classList.contains("media")) t.remove(); }, true);
  document.addEventListener("load", (e) => { const t = e.target; if (t.tagName === "IMG" && t.naturalWidth > 0 && t.naturalWidth < 120) t.remove(); }, true);

  const who = (s) => s.lab || (s.sources && s.sources[0] && s.sources[0].publisher) || host(s.url);

  let data = { stories: [], labs: [], voices: [] };
  let lane = null;
  let query = "";

  const matches = (s) => {
    if (lane && !LANES.find((l) => l.id === lane).cats.includes(s.category)) return false;
    if (!query) return true;
    const hay = `${s.headline} ${s.summary} ${s.lab} ${s.model_name} ${(s.tags || []).join(" ")}`.toLowerCase();
    return query.split(/\s+/).every((w) => hay.includes(w));
  };

  // ---------------------------------------------------------------- signal chart
  function renderSignal() {
    const stories = data.stories || [];
    const now = Date.now();
    // Window adapts to the data: at least 24 hours, at most 7 days.
    const oldest = Math.min(now, ...stories.map((s) => new Date(s.published_at).getTime()).filter((t) => !isNaN(t) && t > now - 7 * DAY));
    const span = Math.min(7 * DAY, Math.max(DAY, now - oldest));
    const hours = span <= DAY ? 24 : span <= 2 * DAY ? 48 : span <= 3 * DAY ? 72 : 168;
    const start = now - hours * 3600000;

    $("lanes").innerHTML = LANES.map((l) => {
      const n = stories.filter((s) => l.cats.includes(s.category) && new Date(s.published_at).getTime() >= start).length;
      return `<button class="lane" type="button" data-lane="${l.id}" aria-pressed="false" style="--c: var(--${l.id})">
        <span class="sw" aria-hidden="true"></span><span>${esc(l.label)}</span><span class="n" aria-label="${n} stories">${n}</span></button>`;
    }).join("");

    const ticks = [];
    const n = hours === 168 ? 7 : 6;
    for (let i = 0; i < n; i++) {
      const d = new Date(start + (i * (now - start)) / n);
      const label = hours === 168
        ? d.toLocaleDateString(undefined, { weekday: "short", day: "numeric" })
        : d.toLocaleString(undefined, { weekday: hours > 24 ? "short" : undefined, hour: "numeric" });
      ticks.push(`<div><span>${esc(label)}</span></div>`);
    }
    $("days").style.gridTemplateColumns = `repeat(${n}, 1fr)`;
    $("days").innerHTML = ticks.join("");
    $("window").textContent = hours === 168 ? "the past 7 days" : `the past ${hours} hours`;

    const placed = LANES.map(() => []);

    $("dots").innerHTML = stories.map((s) => {
      const t = new Date(s.published_at).getTime();
      const li = laneOf(s.category);
      if (isNaN(t) || t < start || li < 0) return "";
      const x = Math.min(1, Math.max(0, (t - start) / (now - start))) * 100;
      const size = 8 + Math.max(0, (s.score || 6) - 5) * 3;
      // nudge points that would overlap within the lane
      const base = li * 52 + 26;
      let y = base;
      for (const off of [0, -13, 13, -21, 21, -6, 6]) {
        if (!placed[li].some((p) => Math.abs(p.x - x) < 2.2 && Math.abs(p.y - (base + off)) < 12)) { y = base + off; break; }
      }
      placed[li].push({ x, y });
      return `<a class="dot" href="${safeUrl(s.url)}" rel="noopener" tabindex="-1" data-id="${esc(s.id)}"
        style="left:${x.toFixed(2)}%;top:${y}px;--s:${size}px;--c:${color(s.category)};--d:${Math.round(x * 9)}ms"></a>`;
    }).join("");

    const tip = $("tip");
    const plot = $("plot");
    $("dots").addEventListener("mouseover", (e) => {
      const dot = e.target.closest(".dot");
      if (!dot) return;
      const s = stories.find((x) => x.id === dot.dataset.id);
      if (!s) return;
      tip.innerHTML = `<b>${esc(s.headline)}</b><span>${esc(who(s))}, ${esc(ago(s.published_at))}</span>`;
      tip.hidden = false;
      const pr = plot.getBoundingClientRect();
      const dr = dot.getBoundingClientRect();
      const left = Math.min(Math.max(8, dr.left - pr.left - 40), pr.width - tip.offsetWidth - 8);
      const below = dr.top - pr.top < pr.height / 2;
      tip.style.left = `${left}px`;
      tip.style.top = below ? `${dr.bottom - pr.top + 10}px` : `${dr.top - pr.top - tip.offsetHeight - 10}px`;
    });
    $("dots").addEventListener("mouseout", (e) => { if (e.target.closest(".dot")) tip.hidden = true; });

    $("lanes").addEventListener("click", (e) => {
      const b = e.target.closest(".lane");
      if (!b) return;
      lane = lane === b.dataset.lane ? null : b.dataset.lane;
      apply();
    });
  }

  // ---------------------------------------------------------------- stories
  function srcChips(s) {
    const items = (s.sources || []).slice(0, 5);
    return items.length ? `<div class="srcs" aria-label="Sources">${items.map((x) =>
      `<a href="${safeUrl(x.url)}" rel="noopener">${esc(x.publisher || host(x.url))}</a>`).join("")}</div>` : "";
  }

  function renderLead() {
    const s = data.lead;
    if (!s) {
      $("lead").innerHTML = `<span class="tag" style="--c: var(--research)">Warming up</span>
        <h2>The first stories arrive after the newsroom's first run</h2>
        <p class="sum">The agent runs every three hours. Check back shortly.</p>`;
      return;
    }
    $("lead").innerHTML = `
      <a class="lead-media" href="${safeUrl(s.url)}" rel="noopener" tabindex="-1" aria-hidden="true">${media(s, "wide")}</a>
      <span class="tag" style="--c:${color(s.category)}">Top story, ${esc(CAT_NAME[s.category] || s.category)}</span>
      <h2 style="--c:${color(s.category)}"><a href="${safeUrl(s.url)}" rel="noopener">${esc(s.headline)}</a></h2>
      <p class="meta">${esc(who(s))}, ${esc(ago(s.published_at))}${s.research && s.research.decision === "confirmed"
        ? `. Checked by our research agent against ${s.sources.length} sources` : ""}</p>
      <p class="sum">${esc(s.summary)}</p>
      ${s.why_it_matters ? `<p class="why"><strong>Why it matters.</strong> ${esc(s.why_it_matters)}</p>` : ""}
      ${srcChips(s)}`;
  }

  function renderFeed() {
    const leadId = data.lead && data.lead.id;
    const filtering = !!(lane || query);
    const list = (data.stories || []).filter((s) => matches(s) && (filtering || s.id !== leadId)).slice(0, filtering ? 30 : 9);
    const laneLabel = lane && LANES.find((l) => l.id === lane).label;
    $("feed-title").textContent = query ? `Results for “${query}”${laneLabel ? ` in ${laneLabel}` : ""}` : laneLabel || "Latest";
    $("clear").hidden = !filtering;
    $("feed").innerHTML = list.length
      ? list.map((s) => `<li><a href="${safeUrl(s.url)}" rel="noopener" style="--c:${color(s.category)}">
          <span class="bar" aria-hidden="true"></span>
          <span class="h">${esc(s.headline)}</span>
          ${media(s, "thumb")}
          <span class="meta">${esc(CAT_NAME[s.category] || s.category)}, ${esc(who(s))}, ${esc(ago(s.published_at))}</span></a></li>`).join("")
      : `<li class="empty">${filtering ? "No stories match yet. Try another topic or search." : "Stories appear here after each run."}</li>`;
  }

  function apply() {
    document.querySelectorAll(".lane").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lane === lane)));
    $("signal").classList.toggle("filtered", !!(lane || query));
    const ids = new Set((data.stories || []).filter(matches).map((s) => s.id));
    document.querySelectorAll(".dot").forEach((d) => d.classList.toggle("off", !ids.has(d.dataset.id)));
    renderFeed();
  }

  // ---------------------------------------------------------------- labs
  function renderBoard() {
    const now = Date.now();
    const tracked = (data.labs || []).filter((l) => l.model);
    const waiting = (data.labs || []).filter((l) => !l.model).map((l) => l.lab);
    const rows = tracked.map((l) => {
      const days = Math.max(0, Math.floor((now - new Date(l.date).getTime()) / DAY));
      const when = days === 0 ? "Today" : days === 1 ? "Yesterday" : `${days} days ago`;
      const fill = Math.max(6, 100 - (days / 30) * 100);
      return `<div class="row" role="row">
        <span class="lab" role="cell">${esc(l.lab)}</span>
        <span class="model" role="cell">${l.url ? `<a href="${safeUrl(l.url)}" rel="noopener">${esc(l.model)}</a>` : esc(l.model)}</span>
        <span class="type" role="cell">${esc(l.type || "Model")}</span>
        <span class="fresh" role="cell"><span class="track" aria-hidden="true"><span class="fill" style="width:${fill.toFixed(0)}%"></span></span><span>${esc(when)}</span></span>
      </div>`;
    });
    $("board").innerHTML = `<div class="row headr" role="row"><span role="columnheader">Lab</span><span role="columnheader">Latest release</span>
      <span role="columnheader">Type</span><span role="columnheader">Shipped</span></div>` + rows.join("")
      + (rows.length ? "" : `<div class="row none" role="row"><span role="cell">The first releases appear here after the next runs.</span></div>`);
    $("waiting").textContent = waiting.length ? `Watching for releases from ${waiting.join(", ")}.` : "";
  }

  // ---------------------------------------------------------------- sections
  function cards(el, list, empty) {
    el.innerHTML = list.length
      ? list.map((s) => `<a class="card" href="${safeUrl(s.url)}" rel="noopener" style="--c:${color(s.category)}">
          ${media(s, "card-media")}
          <span class="meta">${esc(who(s))}, ${esc(ago(s.published_at))}</span>
          <h3>${esc(s.headline)}</h3><p>${esc(s.why_it_matters || s.summary)}</p></a>`).join("")
      : `<p class="empty">${esc(empty)}</p>`;
  }

  function renderVoices() {
    const q = data.voices || [];
    if (q.length) {
      $("quotes").innerHTML = q.map((v) => `<figure class="quote">
        <blockquote>“${esc(clip(v.text, 230))}”</blockquote>
        <figcaption><strong>${esc(v.speaker)}</strong>${v.speaker_role ? `, ${esc(v.speaker_role)}` : ""}. <a href="${safeUrl(v.source_url)}" rel="noopener">Read the source</a></figcaption>
      </figure>`).join("");
    } else {
      cards($("quotes"), (data.stories || []).filter((s) => s.category === "voices").slice(0, 4), "Commentary from leading people appears here.");
    }
  }

  // ---------------------------------------------------------------- daily briefing
  function renderBriefing(b) {
    const sec = $("briefing");
    if (!b || !b.themes || !b.themes.length) { sec.hidden = true; return; }
    sec.hidden = false;
    $("brief-line").textContent = b.one_line || "";
    const when = b.written_at ? new Date(b.written_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "";
    $("brief-by").textContent = `Written by our newsroom agent${when ? ` at ${when}` : ""} from ${b.from_stories || "today's"} stories. Every line links to its sources.`;
    $("themes").innerHTML = b.themes.map((t) => `<li class="theme">
        <h3>${esc(t.title)}</h3>
        <p>${esc(t.text)}</p>
        <div class="refs">${(t.stories || []).slice(0, 4).map((s) => `<a href="${safeUrl(s.url)}" rel="noopener" title="${esc(s.headline)}">${esc(clip(s.headline, 42))}</a>`).join("")}</div>
      </li>`).join("");
  }

  // ---------------------------------------------------------------- developing threads
  function renderThreads(threads) {
    const sec = $("developing");
    if (!threads || !threads.length) { sec.hidden = true; return; }
    sec.hidden = false;
    $("threads").innerHTML = threads.map((t) => {
      const c = color((t.stories[0] || {}).category);
      return `<article class="thread" style="--c:${c}">
        <div class="thread-head"><h3>${esc(t.title)}</h3><span>${t.stories.length} updates</span></div>
        <ol class="tl">${t.stories.slice(0, 4).map((s, i) => `<li>
          <span class="when">${i === 0 ? "Latest, " : ""}${esc(ago(s.published_at))}</span>
          <a href="${safeUrl(s.url)}" rel="noopener">${esc(s.headline)}</a></li>`).join("")}</ol>
      </article>`;
    }).join("");
  }

  // ---------------------------------------------------------------- theme toggle
  (function themeToggle() {
    const root = document.documentElement;
    const btn = $("theme-btn");
    const sync = () => btn.setAttribute("aria-label", root.dataset.theme === "daylight" ? "Switch to dark mode" : "Switch to light mode");
    sync();
    btn.addEventListener("click", () => {
      const next = root.dataset.theme === "daylight" ? (root.dataset.defaultDark || "abyss") : "daylight";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("fw-theme", next); } catch (e) {}
      sync();
    });
  })();

  function render(d) {
    data = d || data;
    const st = data.stats || {};
    $("updated").textContent = data.updated_at
      ? `Updated ${ago(data.updated_at)}. ${st.stories_this_month || 0} stories and ${st.model_releases_this_month || 0} model releases this month.`
      : "Waiting for the first run";
    renderSignal();
    renderLead();
    renderFeed();
    renderBoard();
    const s = data.stories || [];
    cards($("research-list"), s.filter((x) => x.category === "research").slice(0, 6), "Research stories appear here.");
    cards($("policy-list"), s.filter((x) => x.category === "policy" || x.category === "safety").slice(0, 6), "Policy and safety stories appear here.");
    renderVoices();
    renderBriefing(data.briefing);
    renderThreads(data.threads);
  }

  // search: type to filter; "/" focuses, Esc clears
  const q = $("q");
  q.addEventListener("input", () => { query = q.value.trim().toLowerCase(); apply(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== q && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); q.focus(); }
    if (e.key === "Escape" && document.activeElement === q) { q.value = ""; query = ""; apply(); q.blur(); }
  });
  $("clear").addEventListener("click", () => { lane = null; query = ""; q.value = ""; apply(); });

  $("year").textContent = new Date().getFullYear();
  fetch("data/site.json", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then(render)
    .catch(() => render({ stories: [], labs: [], stats: {} }));
})();
