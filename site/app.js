// Frontier Wire front page: renders data/site.json (written by the newsroom agent).
(function () {
  "use strict";

  const CATS = [
    { id: "all", label: "All" },
    { id: "models", label: "Model releases" },
    { id: "research", label: "Research" },
    { id: "policy", label: "Policy & safety", match: ["policy", "safety"] },
    { id: "industry", label: "Industry" },
    { id: "voices", label: "Commentary" },
  ];
  const CAT_LABEL = { models: "Model release", research: "Research", policy: "Policy", safety: "Safety", industry: "Industry", voices: "Commentary" };
  const WARM_TYPES = new Set(["Multimodal", "Vision-language", "Image", "Video"]);

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? esc(u) : "#");
  const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; } };

  function ago(iso) {
    const d = new Date(iso);
    const mins = Math.round((Date.now() - d.getTime()) / 60000);
    if (isNaN(mins)) return "";
    if (mins < 60) return `${Math.max(mins, 1)}m ago`;
    if (mins < 60 * 24) return `${Math.round(mins / 60)}h ago`;
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  }
  const shortDate = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "—");

  function sourcesLine(s) {
    const links = (s.sources || []).slice(0, 4).map((x) => `<a href="${safeUrl(x.url)}" rel="noopener">${esc(x.publisher || host(x.url))}</a>`);
    return links.length ? `<p class="sources">Sources: ${links.join(" · ")}</p>` : "";
  }

  function renderLead(s) {
    if (!s) {
      $("lead").innerHTML = `<div class="lead-art">${art()}<span class="mono">FIRST RUN PENDING</span></div>
        <h1>The newsroom is warming up</h1>
        <p class="summary">Stories appear here after the agent's first run. It runs every three hours.</p>`;
      return;
    }
    $("lead").innerHTML = `
      <div class="lead-art">${art()}<span class="mono">TOP STORY</span></div>
      <div class="meta"><span class="cat">${esc(CAT_LABEL[s.category] || s.category)}</span><span>${esc(s.lab || host(s.url))} · ${esc(ago(s.published_at))}</span></div>
      <h1><a href="${safeUrl(s.url)}" rel="noopener">${esc(s.headline)}</a></h1>
      <p class="summary">${esc(s.summary)}</p>
      <p class="why"><b>Why it matters:</b> ${esc(s.why_it_matters)}</p>
      ${sourcesLine(s)}`;
  }

  function art() {
    return `<svg aria-hidden="true" viewBox="0 0 800 350" preserveAspectRatio="xMidYMid slice" fill="none">
      <path d="M0 70H800M0 140H800M0 210H800M0 280H800M160 0V350M320 0V350M480 0V350M640 0V350" stroke="#2a2f3a"/>
      <path d="M40 300 L180 230 L300 255 L420 160 L540 185 L660 90 L760 60" stroke="#5b7bff" stroke-width="3"/></svg>`;
  }

  function renderFeed(stories, cat, leadId) {
    const def = CATS.find((c) => c.id === cat) || CATS[0];
    const list = stories.filter((s) => s.id !== leadId && (cat === "all" || (def.match || [def.id]).includes(s.category))).slice(0, 10);
    $("feed").innerHTML = list.length
      ? list.map((s) => `<li><a href="${safeUrl(s.url)}" rel="noopener">
          <span class="mono muted">${esc((CAT_LABEL[s.category] || s.category).toUpperCase())} · ${esc(ago(s.published_at))}</span>
          <span class="h">${esc(s.headline)}</span>
          <span class="pub">${esc(s.lab || (s.sources && s.sources[0] && s.sources[0].publisher) || host(s.url))}</span></a></li>`).join("")
      : `<li class="empty">Nothing in this topic yet.</li>`;
  }

  function renderLabs(labs) {
    $("labs-body").innerHTML = (labs || []).map((l) => l.model
      ? `<tr><td class="lab">${esc(l.lab)}</td><td>${l.url ? `<a href="${safeUrl(l.url)}" rel="noopener">${esc(l.model)}</a>` : esc(l.model)}</td>
          <td><span class="pill${WARM_TYPES.has(l.type) ? " warm" : ""}">${esc(l.type || "Other")}</span></td><td class="date">${esc(shortDate(l.date))}</td></tr>`
      : `<tr><td class="lab">${esc(l.lab)}</td><td class="none" colspan="3">No release tracked yet</td></tr>`).join("");
  }

  function renderCards(el, stories, emptyText) {
    el.innerHTML = stories.length
      ? stories.map((s) => `<a class="card" href="${safeUrl(s.url)}" rel="noopener">
          <span class="mono muted">${esc(((s.lab || host(s.url)) + " · " + shortDate(s.published_at)).toUpperCase())}</span>
          <h3>${esc(s.headline)}</h3><p>${esc(s.why_it_matters || s.summary)}</p></a>`).join("")
      : `<p class="empty">${esc(emptyText)}</p>`;
  }

  function renderVoices(voices, stories) {
    if (voices.length) {
      $("voices-cards").innerHTML = voices.map((q) => `<figure class="quote">
          <blockquote>“${esc(q.text)}”</blockquote>
          <figcaption><b>${esc(q.speaker)}</b>${esc(q.speaker_role || "")}${q.speaker_role ? " · " : ""}<a href="${safeUrl(q.source_url)}" rel="noopener">source</a></figcaption>
        </figure>`).join("");
      return;
    }
    const commentary = stories.filter((s) => s.category === "voices").slice(0, 6);
    renderCards($("voices-cards"), commentary, "Commentary from leading people will appear here.");
  }

  function renderPolicy(stories) {
    const list = stories.filter((s) => s.category === "policy" || s.category === "safety").slice(0, 6);
    $("policy-list").innerHTML = list.length
      ? list.map((s) => `<a href="${safeUrl(s.url)}" rel="noopener">
          <span class="mono muted">${esc((CAT_LABEL[s.category] + " · " + shortDate(s.published_at)).toUpperCase())}</span>
          <span class="h">${esc(s.headline)}</span></a>`).join("")
      : `<p class="empty">Policy and safety stories will appear here.</p>`;
  }

  function renderChips(onPick) {
    $("chips").innerHTML = CATS.map((c, i) => `<button class="chip" type="button" data-cat="${c.id}" aria-pressed="${i === 0}">${esc(c.label)}</button>`).join("");
    $("chips").addEventListener("click", (e) => {
      const b = e.target.closest(".chip");
      if (!b) return;
      document.querySelectorAll(".chip").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      onPick(b.dataset.cat);
    });
  }

  function render(data) {
    const stories = data.stories || [];
    const leadId = data.lead && data.lead.id;
    const updated = data.updated_at ? new Date(data.updated_at) : null;
    $("updated").textContent = updated
      ? `LIVE · Updated ${ago(data.updated_at)} (${updated.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })})`
      : "LIVE";
    const st = data.stats || {};
    $("stats").textContent = `Tracking ${st.labs_tracked || 0} labs · ${st.model_releases_this_month || 0} model releases this month`;
    renderLead(data.lead);
    renderChips((cat) => renderFeed(stories, cat, leadId));
    renderFeed(stories, "all", leadId);
    renderLabs(data.labs);
    renderCards($("research-cards"), stories.filter((s) => s.category === "research").slice(0, 6), "Research stories will appear here.");
    renderVoices(data.voices || [], stories);
    renderPolicy(stories);
  }

  $("year").textContent = new Date().getFullYear();
  fetch("data/site.json", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then(render)
    .catch(() => render({ stories: [], labs: [], stats: {} }));
})();
