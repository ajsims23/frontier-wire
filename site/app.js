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
  // A story shows its source's preview image (or a figure from the paper); a generated cover
  // (cover.js) sits underneath and shows whenever there's no image or it fails to load.
  const hash = (t) => { let h = 2166136261; for (const ch of String(t)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
  function rng(seed) { return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const imgOk = (u) => /^https:\/\//i.test(u || "");
  function media(s, cls) {
    const fig = s.image_kind === "figure" ? " fig" : "";
    const vid = s.video && /^[A-Za-z0-9_-]{11}$/.test(s.video.id) ? `<span class="vbadge"><svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1l7 4-7 4z" fill="currentColor"/></svg>Video</span>` : "";
    return `<div class="media ${cls}${fig}" style="--c:${color(s.category)}">${window.FWCover ? window.FWCover(s) : ""}${imgOk(s.image)
      ? `<img src="${esc(s.image)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ""}${vid}</div>`;
  }
  document.addEventListener("error", (e) => { const t = e.target; if (t.tagName === "IMG" && t.parentElement && t.parentElement.classList.contains("media")) t.remove(); }, true);
  document.addEventListener("load", (e) => { const t = e.target; if (t.tagName === "IMG" && t.naturalWidth > 0 && t.naturalWidth < 120) t.remove(); }, true);

  const who = (s) => s.lab || (s.sources && s.sources[0] && s.sources[0].publisher) || host(s.url);

  let data = { stories: [], labs: [], voices: [] };
  let topic = "all";
  // "Reading as": builders, business or investors. Each story carries one line per group on what it means for them.
  const AUD = { builders: "For builders", business: "For business", investors: "For investors" };
  let aud = (() => { try { const v = localStorage.getItem("fw-aud"); return AUD[v] ? v : "all"; } catch (e) { return "all"; } })();
  const audLine = (s) => (aud !== "all" && s.audiences && s.audiences[aud]) || "";
  const audHtml = (s, cls) => { const l = audLine(s); return l ? `<span class="aud-line ${cls || ""}"><b>${AUD[aud]}:</b> ${esc(l)}</span>` : ""; };
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
    for (const s of ranked) { if (more.length < 4 && !labs.has(s.lab || s.id)) { more.push(s); labs.add(s.lab || s.id); } }
    for (const s of ranked) { if (more.length < 4 && !more.includes(s)) more.push(s); }
    return { lead, more };
  }

  // The top five stories take turns as the lead: slow zoom on the picture, progress bars like stories.
  // A bar's fill animation drives the rotation, so hovering (which pauses it) also pauses the rotation.
  function renderFront() {
    const { lead, more } = topStories();
    if (!lead) {
      $("lead").innerHTML = `<div class="front-media">${media({ id: "empty", category: "research", headline: "Frontier Wire" }, "wide")}</div>
        <h2>The first stories arrive after the newsroom's first run</h2>`;
      $("more").innerHTML = "";
      return;
    }
    const slides = [lead, ...more].slice(0, 5);
    $("lead").innerHTML = `
      <div class="hero-bars" role="tablist" aria-label="Top stories">${slides.map((s, i) =>
        `<button class="hb${i ? "" : " on"}" type="button" role="tab" data-i="${i}" aria-selected="${!i}" aria-label="Top story ${i + 1}: ${esc(clip(s.headline, 60))}"><span></span></button>`).join("")}</div>
      <div class="hero-stage">${slides.map((s, i) => `
        <div class="hero-slide${i ? "" : " on"}" data-i="${i}" ${i ? 'aria-hidden="true"' : ""}>
          <a class="front-media" href="${storyHref(s)}" tabindex="-1" aria-hidden="true">${media(s, `wide kb kb${i % 3}`)}</a>
          <span class="tag" style="--c:${color(s.category)}">${i ? "Top stories" : "Top story"}, ${esc(CAT_NAME[s.category] || s.category)}</span>
          <h2><a href="${storyHref(s)}" ${i ? 'tabindex="-1"' : ""}>${esc(s.headline)}</a></h2>
          <p class="sum">${esc(s.summary)}</p>
          ${audHtml(s, "big")}
          <p class="meta">${esc(who(s))}, ${esc(ago(s.published_at))}. Checked against ${(s.sources || []).length} source${(s.sources || []).length === 1 ? "" : "s"}.</p>
          ${s.video && /^[A-Za-z0-9_-]{11}$/.test(s.video.id) ? `<button class="btn play-btn" type="button" data-video="${esc(s.video.id)}" data-title="${esc(s.video.title)}" ${i ? 'tabindex="-1"' : ""}><svg width="14" height="14" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1l7 4-7 4z" fill="currentColor"/></svg>Watch the video</button>` : ""}
        </div>`).join("")}</div>`;
    $("more").innerHTML = slides.map((s, i) => `<li class="${i ? "" : "on"}" data-i="${i}"><a href="${storyHref(s)}" style="--c:${color(s.category)}">
        ${media(s, "more-media")}
        <span class="more-text"><span class="tag" style="--c:${color(s.category)}">${esc(CAT_NAME[s.category] || s.category)}</span>
        <span class="h">${esc(s.headline)}</span><span class="meta">${esc(who(s))}, ${esc(ago(s.published_at))}</span></span></a></li>`).join("");
    startHero(slides.length);
  }

  function startHero(n) {
    const root = $("lead");
    let cur = 0;
    const show = (i) => {
      cur = (i + n) % n;
      root.querySelectorAll(".hb").forEach((b, j) => {
        b.classList.toggle("on", j === cur); b.classList.toggle("done", j < cur); b.setAttribute("aria-selected", String(j === cur));
        const bar = b.firstElementChild; bar.style.animation = "none"; void bar.offsetWidth; bar.style.animation = "";
      });
      root.querySelectorAll(".hero-slide").forEach((el, j) => {
        const on = j === cur;
        el.classList.toggle("on", on);
        if (on) { el.removeAttribute("aria-hidden"); const m = el.querySelector(".media"); m.classList.remove("kb"); void m.offsetWidth; m.classList.add("kb"); }
        else el.setAttribute("aria-hidden", "true");
        el.querySelectorAll("h2 a, .play-btn").forEach((a) => (on ? a.removeAttribute("tabindex") : a.setAttribute("tabindex", "-1")));
      });
      document.querySelectorAll("#more li").forEach((li, j) => li.classList.toggle("on", j === cur));
    };
    root.querySelectorAll(".hb").forEach((b) => {
      b.addEventListener("click", () => show(+b.dataset.i));
      b.firstElementChild.addEventListener("animationend", () => { if (b.classList.contains("on")) show(cur + 1); });
    });
    document.querySelectorAll("#more li").forEach((li) => {
      const pick = () => { if (+li.dataset.i !== cur) show(+li.dataset.i); };
      li.addEventListener("mouseenter", pick); li.addEventListener("focusin", pick);
    });
    // pause while the reader hovers the lead or the list, or the tab is hidden
    const pause = (on) => root.classList.toggle("paused", on);
    [root, $("more")].forEach((el) => { el.addEventListener("mouseenter", () => pause(true)); el.addEventListener("mouseleave", () => pause(false)); });
    document.addEventListener("visibilitychange", () => pause(document.hidden));
    let x0 = null; // swipe on phones
    root.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
    root.addEventListener("touchend", (e) => { if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1)); x0 = null; });
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
    const front = new Set([(data.lead || (data.stories || [])[0] || {}).id, ...topStories().more.map((s) => s.id)]);
    let list = (data.stories || []).filter((s) => matches(s) && (filtering || !front.has(s.id)));
    if (aud !== "all") list = list.filter((s) => audLine(s)).concat(list.filter((s) => !audLine(s)));  // what matters to you first
    list = list.slice(0, filtering ? 30 : 12);
    const t = TOPICS.find((x) => x.id === topic);
    $("feed-title").textContent = query ? `Results for “${query}”` : topic === "all" ? (aud === "all" ? "Latest" : `Latest ${AUD[aud].toLowerCase()}`) : t.label;
    $("clear").hidden = !filtering;
    $("feed").innerHTML = list.length
      ? list.map((s) => `<li><a class="story-card" href="${storyHref(s)}" style="--c:${color(s.category)}">
          ${media(s, "card-media")}
          <span class="sc-body"><span class="tag" style="--c:${color(s.category)}">${esc(CAT_NAME[s.category] || s.category)}</span>
          <span class="h">${esc(s.headline)}</span>
          ${audHtml(s)}
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
    const w = data.weekly;
    $("brief-weekly").innerHTML = w && /^\d{4}-W\d{2}$/.test(w.key || "") ? `<a class="weekly-link" href="weekly/${w.key}/"><span class="ex-kicker">Weekly deep dive, ${esc(w.range)}</span><span class="strong">${esc(w.title)}</span><span class="wl-go">Read the week's five biggest shifts</span></a>` : "";
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

  document.addEventListener("click", (e) => { if (e.target.closest(".vstory")) e.stopPropagation(); }, true);
  // ---------------------------------------------------------------- watch: videos picked by the agent
  const thumb = (id) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
  function renderWatch() {
    const vids = (data.videos || []).filter((v) => /^[A-Za-z0-9_-]{11}$/.test(v.id || "")).slice(0, 5);
    $("watch").hidden = !vids.length;
    if (!vids.length) return;
    const byId = Object.fromEntries((data.stories || []).map((s) => [s.id, s]));
    $("watch-list").innerHTML = vids.map((v, i) => {
      const st = v.story_id && byId[v.story_id];
      return `<article class="vcard${i ? "" : " feat"}" data-video="${esc(v.id)}" data-title="${esc(v.title)}">
        <button class="vthumb" type="button" aria-label="Play video: ${esc(v.title)}">
          <img src="${thumb(v.id)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">
          <span class="vplay" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 10 10"><path d="M2.5 1.2l6 3.8-6 3.8z" fill="currentColor"/></svg></span>
        </button>
        <div class="vtext"><p class="meta">${esc(v.channel)}, ${esc(ago(v.published))}</p>
          <h3>${esc(v.title)}</h3>
          ${i === 0 && v.blurb ? `<p class="vblurb">${esc(v.blurb)}</p>` : ""}
          ${st ? `<a class="text-link vstory" href="${storyHref(st)}">Read our story</a>` : ""}</div>
      </article>`;
    }).join("");
  }

  function renderAud() {
    document.querySelectorAll("#aud button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.aud === aud)));
  }
  $("aud").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-aud]");
    if (!b) return;
    aud = b.dataset.aud;
    try { localStorage.setItem("fw-aud", aud); } catch (err) { /* private mode */ }
    renderAud(); renderFront(); renderFeed();
  });

  function render(d) {
    data = d || data;
    const st = data.stats || {};
    $("updated").textContent = data.updated_at
      ? `Updated ${ago(data.updated_at)}. ${st.stories_this_month || 0} stories this month, each checked against its sources.`
      : "Waiting for the first run";
    renderAud();
    renderFront();
    renderNewsChart();
    renderBriefing(data.briefing);
    renderWatch();
    if (window.FWPodcast) window.FWPodcast(data.podcasts);
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
    const mo = d.models || {};
    body("desk-models", big(mo.count || 0, "models tracked") + (mo.cheapest ? `<p class="muted">Cheapest newest model: ${esc(mo.cheapest.name)}, $${esc(mo.cheapest.price)} per 1M output tokens</p>` : "") +
      ((mo.changes || []).length ? `<ul>${mo.changes.map((c) => `<li>${esc(clip(c, 80))}</li>`).join("")}</ul>` : `<p class="muted">New models and price changes, logged automatically.</p>`));
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
