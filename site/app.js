// Frontier Wire home page — renders data/site.json written by the newsroom agent.
// Every story links to its own page on this site (story/<id>/); sources are linked from there.
(function () {
  "use strict";

  const TOPICS = [
    { id: "all", label: "All", cats: null },
    { id: "models", label: "Models", cats: ["models"] },
    { id: "research", label: "Research", cats: ["research"] },
    { id: "policy", label: "Policy & safety", cats: ["policy", "safety"] },
    { id: "industry", label: "Industry", cats: ["industry"] },
    { id: "voices", label: "Voices", cats: ["voices"] },
  ];
  const CAT_NAME = { models: "Model release", research: "Research", policy: "Policy", safety: "Safety", industry: "Industry", voices: "Commentary" };
  const color = (cat) => `var(--${CAT_NAME[cat] ? cat : "models"})`;
  const DAY = 86400000;

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? esc(u) : "#");
  const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; } };
  const slug = (t) => String(t || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "lab";
  const storyHref = (s) => `story/${encodeURIComponent(s.id)}/`;
  const clip = (t, n) => { t = String(t || ""); if (t.length <= n) return t; return t.slice(0, n).replace(/\s+\S*$/, "") + "…"; };

  function ago(iso) {
    const t = new Date(iso).getTime();
    if (isNaN(t)) return "";
    const m = Math.round((Date.now() - t) / 60000);
    if (m < 60) return `${Math.max(m, 1)} min ago`;
    if (m < 1440) return `${Math.round(m / 60)}h ago`;
    const d = Math.round(m / 1440);
    return d < 7 ? `${d} day${d > 1 ? "s" : ""} ago` : new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  }

  // ---------------------------------------------------------------- pictures
  // A story shows its source's preview image; generated "signal" art sits underneath and shows
  // whenever there's no image or it fails to load.
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
  document.addEventListener("error", (e) => { const t = e.target; if (t.tagName === "IMG" && t.parentElement && t.parentElement.classList.contains("media")) t.remove(); }, true);
  document.addEventListener("load", (e) => { const t = e.target; if (t.tagName === "IMG" && t.naturalWidth > 0 && t.naturalWidth < 120) t.remove(); }, true);

  const who = (s) => s.lab || (s.sources && s.sources[0] && s.sources[0].publisher) || host(s.url);

  let data = { stories: [], labs: [], voices: [] };
  let topic = "all";
  let query = "";

  const matches = (s) => {
    const t = TOPICS.find((x) => x.id === topic);
    if (t && t.cats && !t.cats.includes(s.category)) return false;
    if (!query) return true;
    const hay = `${s.headline} ${s.summary} ${s.lab} ${s.model_name} ${(s.tags || []).join(" ")}`.toLowerCase();
    return query.split(/\s+/).every((w) => hay.includes(w));
  };

  // ---------------------------------------------------------------- front page: picture-led top stories
  function topStories() {
    const stories = data.stories || [];
    const lead = data.lead || stories[0];
    const recent = stories.filter((s) => !lead || s.id !== lead.id);
    // the next three: most important recent stories, preferring ones with photos and different labs
    const pool = recent.filter((s) => Date.now() - new Date(s.published_at).getTime() < 2 * DAY);
    const ranked = (pool.length >= 3 ? pool : recent).slice().sort((a, b) => (b.score - a.score) || ((b.image ? 1 : 0) - (a.image ? 1 : 0)));
    const more = [], labs = new Set(lead ? [lead.lab] : []);
    for (const s of ranked) { if (more.length < 3 && !labs.has(s.lab || s.id)) { more.push(s); labs.add(s.lab || s.id); } }
    for (const s of ranked) { if (more.length < 3 && !more.includes(s)) more.push(s); }
    return { lead, more };
  }

  function renderFront() {
    const { lead, more } = topStories();
    if (!lead) {
      $("lead").innerHTML = `<div class="front-media">${media({ id: "empty", category: "research" }, "wide")}</div>
        <h2>The first stories arrive after the newsroom's first run</h2>`;
      $("more").innerHTML = "";
      return;
    }
    $("lead").innerHTML = `
      <a class="front-media" href="${storyHref(lead)}" tabindex="-1" aria-hidden="true">${media(lead, "wide")}</a>
      <span class="tag" style="--c:${color(lead.category)}">Top story, ${esc(CAT_NAME[lead.category] || lead.category)}</span>
      <h2><a href="${storyHref(lead)}">${esc(lead.headline)}</a></h2>
      <p class="sum">${esc(lead.summary)}</p>
      <p class="meta">${esc(who(lead))}, ${esc(ago(lead.published_at))}. Checked against ${(lead.sources || []).length} sources.</p>`;
    $("more").innerHTML = more.map((s) => `<li><a href="${storyHref(s)}" style="--c:${color(s.category)}">
        ${media(s, "more-media")}
        <span class="more-text"><span class="tag" style="--c:${color(s.category)}">${esc(CAT_NAME[s.category] || s.category)}</span>
        <span class="h">${esc(s.headline)}</span><span class="meta">${esc(who(s))}, ${esc(ago(s.published_at))}</span></span></a></li>`).join("");
  }

  // "Who's making news": stories per lab over the last 7 days, as a bar chart linking to lab pages.
  function renderNewsChart() {
    const counts = {};
    const since = Date.now() - 7 * DAY;
    for (const s of data.stories || []) {
      if (s.lab && new Date(s.published_at).getTime() >= since) counts[s.lab] = (counts[s.lab] || 0) + 1;
    }
    const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 7);
    const top = rows.length ? rows[0][1] : 1;
    $("news-chart").innerHTML = rows.length ? rows.map(([lab, n]) => `<li><a href="lab/${slug(lab)}/">
        <span class="nc-lab">${esc(lab)}</span>
        <span class="nc-bar" aria-hidden="true"><span style="width:${Math.max(6, (n / top) * 100).toFixed(0)}%"></span></span>
        <span class="nc-n">${n}<span class="sr"> stor${n === 1 ? "y" : "ies"}</span></span></a></li>`).join("")
      : `<li class="empty">Lab activity appears after a few runs.</li>`;
  }

  // ---------------------------------------------------------------- latest stories
  function renderChips() {
    const counts = Object.fromEntries(TOPICS.map((t) => [t.id, (data.stories || []).filter((s) => !t.cats || t.cats.includes(s.category)).length]));
    $("chips").innerHTML = TOPICS.filter((t) => t.id === "all" || counts[t.id] > 0).map((t) => `<button class="chip" type="button" data-topic="${t.id}" aria-pressed="${t.id === topic}">${esc(t.label)} <span class="n">${counts[t.id]}</span></button>`).join("");
  }

  function renderFeed() {
    const filtering = topic !== "all" || !!query;
    const front = new Set([data.lead && data.lead.id, ...topStories().more.map((s) => s.id)]);
    const list = (data.stories || []).filter((s) => matches(s) && (filtering || !front.has(s.id))).slice(0, filtering ? 30 : 12);
    const t = TOPICS.find((x) => x.id === topic);
    $("feed-title").textContent = query ? `Results for “${query}”` : topic === "all" ? "Latest" : t.label;
    $("clear").hidden = !filtering;
    $("feed").innerHTML = list.length
      ? list.map((s) => `<li><a class="story-card" href="${storyHref(s)}" style="--c:${color(s.category)}">
          ${media(s, "card-media")}
          <span class="sc-body"><span class="tag" style="--c:${color(s.category)}">${esc(CAT_NAME[s.category] || s.category)}</span>
          <span class="h">${esc(s.headline)}</span>
          <span class="meta">${esc(who(s))}, ${esc(ago(s.published_at))}</span></span></a></li>`).join("")
      : `<li class="empty">${filtering ? "No stories match yet. Try another topic or search." : "Stories appear here after each run."}</li>`;
    document.querySelectorAll(".chip[data-topic]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.topic === topic)));
  }

  // ---------------------------------------------------------------- labs
  function renderBoard() {
    const now = Date.now();
    const tracked = (data.labs || []).filter((l) => l.model);
    const waiting = (data.labs || []).filter((l) => !l.model);
    const rows = tracked.map((l) => {
      const days = Math.max(0, Math.floor((now - new Date(l.date).getTime()) / DAY));
      const when = days === 0 ? "Today" : days === 1 ? "Yesterday" : `${days} days ago`;
      const fill = Math.max(6, 100 - (days / 30) * 100);
      const rel = l.story_id ? `story/${encodeURIComponent(l.story_id)}/` : null;
      return `<div class="row" role="row">
        <span class="lab" role="cell"><a href="lab/${slug(l.lab)}/">${esc(l.lab)}</a></span>
        <span class="model" role="cell">${rel ? `<a href="${rel}">${esc(clip(l.model, 60))}</a>` : esc(l.model)}</span>
        <span class="type" role="cell">${esc(l.type || "Model")}</span>
        <span class="fresh" role="cell"><span class="track" aria-hidden="true"><span class="fill" style="width:${fill.toFixed(0)}%"></span></span><span>${esc(when)}</span></span>
      </div>`;
    });
    $("board").innerHTML = `<div class="row headr" role="row"><span role="columnheader">Lab</span><span role="columnheader">Latest release</span>
      <span role="columnheader">Type</span><span role="columnheader">Shipped</span></div>` + rows.join("")
      + (rows.length ? "" : `<div class="row none" role="row"><span role="cell">The first releases appear here after the next runs.</span></div>`);
    $("waiting").innerHTML = waiting.length ? `Watching for releases from ${waiting.map((l) => `<a href="lab/${slug(l.lab)}/">${esc(l.lab)}</a>`).join(", ")}.` : "";
  }

  // ---------------------------------------------------------------- sections
  function cards(el, list, empty) {
    el.innerHTML = list.length
      ? list.map((s) => `<a class="card" href="${storyHref(s)}" style="--c:${color(s.category)}">
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
        <figcaption><strong>${esc(v.speaker)}</strong>${v.speaker_role ? `, ${esc(v.speaker_role)}` : ""}. <a href="story/${encodeURIComponent(v.story_id)}/">Read the story</a></figcaption>
      </figure>`).join("");
    } else {
      cards($("quotes"), (data.stories || []).filter((s) => s.category === "voices").slice(0, 4), "Commentary from leading people appears here.");
    }
  }

  function renderBriefing(b) {
    const sec = $("briefing");
    if (!b || !b.themes || !b.themes.length) { sec.hidden = true; return; }
    sec.hidden = false;
    $("brief-line").textContent = b.one_line || "";
    const when = b.written_at ? new Date(b.written_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "";
    $("brief-by").textContent = `Written by our newsroom agent${when ? ` at ${when}` : ""} from ${b.from_stories || "today's"} stories. Every line links to its stories.`;
    $("themes").innerHTML = b.themes.map((t) => `<li class="theme">
        <h3>${esc(t.title)}</h3>
        <p>${esc(t.text)}</p>
        <div class="refs">${(t.stories || []).slice(0, 4).map((s) => `<a href="${storyHref(s)}" title="${esc(s.headline)}">${esc(clip(s.headline, 42))}</a>`).join("")}</div>
      </li>`).join("");
  }

  function renderThreads(threads) {
    const sec = $("developing");
    if (!threads || !threads.length) { sec.hidden = true; return; }
    sec.hidden = false;
    $("threads").innerHTML = threads.map((t) => `<article class="thread" style="--c:${color((t.stories[0] || {}).category)}">
        <div class="thread-head"><h3>${esc(t.title)}</h3><span>${t.stories.length} updates</span></div>
        <ol class="tl">${t.stories.slice(0, 4).map((s, i) => `<li>
          <span class="when">${i === 0 ? "Latest, " : ""}${esc(ago(s.published_at))}</span>
          <a href="${storyHref(s)}">${esc(s.headline)}</a></li>`).join("")}</ol>
      </article>`).join("");
  }

  function render(d) {
    data = d || data;
    const st = data.stats || {};
    $("updated").textContent = data.updated_at
      ? `Updated ${ago(data.updated_at)}. ${st.stories_this_month || 0} stories this month, each checked against its sources.`
      : "Waiting for the first run";
    renderFront();
    renderNewsChart();
    renderBriefing(data.briefing);
    renderChips();
    renderFeed();
    renderThreads(data.threads);
    renderBoard();
    cards($("research-list"), (data.stories || []).filter((x) => x.category === "research").slice(0, 6), "Research stories appear here.");
    renderVoices();
    if (window.goatcounter && window.goatcounter.bind_events) window.goatcounter.bind_events();
  }

  // topic chips, search ("/" focuses, Esc clears), and ?topic= links from story pages
  $("chips").addEventListener("click", (e) => {
    const b = e.target.closest(".chip[data-topic]");
    if (!b) return;
    topic = b.dataset.topic;
    renderFeed();
  });
  const q = $("q");
  q.addEventListener("input", () => {
    query = q.value.trim().toLowerCase();
    renderFeed();
    if (query) $("stories").scrollIntoView({ block: "start" });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== q && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); q.focus(); }
    if (e.key === "Escape" && document.activeElement === q) { q.value = ""; query = ""; renderFeed(); q.blur(); }
  });
  $("clear").addEventListener("click", () => { topic = "all"; query = ""; q.value = ""; renderFeed(); });
  try { const t = new URLSearchParams(location.search).get("topic"); if (TOPICS.some((x) => x.id === t)) topic = t; } catch (e) {}

  // ---------------------------------------------------------------- desks (summary built with the site)
  function spark(values) {
    const top = Math.max(1, ...values), w = 140, h = 36, bw = w / values.length;
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">${values.map((v, i) =>
      `<rect x="${(i * bw + 1).toFixed(1)}" y="${(h - Math.max(2, (v / top) * h)).toFixed(1)}" width="${(bw - 2).toFixed(1)}" height="${Math.max(2, (v / top) * h).toFixed(1)}" rx="1.5" fill="${v ? "var(--brand)" : "var(--line-soft)"}"/>`).join("")}</svg>`;
  }
  const big = (n, label) => `<span class="dc-num"><b>${esc(n)}</b> ${esc(label)}</span>`;
  function renderDesks(d) {
    const body = (id, html) => { const el = document.querySelector(`#${id} .dc-body`); if (el) el.innerHTML = html; };
    const i = d.india || {};
    body("desk-india", big(i.count7 || 0, "stories this week") + ((i.latest || []).length
      ? `<ul>${i.latest.map((s) => `<li>${esc(clip(s.headline, 70))}</li>`).join("")}</ul>` : `<p class="muted">Indian AI news appears here.</p>`));
    const b = d.business || {};
    body("desk-business", big(b.deals7 || 0, "deals this week") + spark(b.days || []) +
      (b.largest ? `<p class="muted">Largest disclosed: ${esc(b.largest.amount)}${b.largest.company ? `, ${esc(b.largest.company)}` : ""}</p>` : `<p class="muted">Deals and funding, tracked.</p>`));
    const o = d.opportunities || {};
    body("desk-opps", big((o.roles || 0).toLocaleString(), `open roles at ${o.labs || 0} labs`) +
      `<ul class="dc-stats"><li><b>${o.interns || 0}</b> internships</li><li><b>${o.india || 0}</b> in India</li><li><b>${o.courses || 0}</b> courses</li></ul>`);
    const sec = d.sectors || [], top = Math.max(1, ...sec.map((x) => x.count));
    body("desk-sectors", sec.length ? `<ul class="dc-bars">${sec.map((x) => `<li><span>${esc(x.name)}</span><span class="nc-bar"><span style="width:${Math.max(6, x.count / top * 100).toFixed(0)}%"></span></span><b>${x.count}</b></li>`).join("")}</ul>`
      : `<p class="muted">Healthcare, finance, education and more.</p>`);
  }
  fetch("data/desks.json", { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).then((d) => d && renderDesks(d)).catch(() => {});

  $("year").textContent = new Date().getFullYear();
  fetch("data/site.json", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then(render)
    .catch(() => render({ stories: [], labs: [], stats: {} }));
})();
