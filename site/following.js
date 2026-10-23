// "Your wire": manage follows, see what's new for you since your last visit, and sign up for alerts.
document.addEventListener("DOMContentLoaded", function () {  // runs after follow.js, which loads at the end of the page
  "use strict";
  const F = window.FWFollow;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const root = "../";
  const feeds = window.FW_FEEDS || {};
  let stories = [];
  const lastSeen = (() => { try { return localStorage.getItem("fw-last-visit-following") || ""; } catch (e) { return ""; } })();

  function short(iso) { return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }); }

  function render() {
    const mine = F.list();
    document.getElementById("mine-sub").textContent = mine.length ? `${mine.length} follow${mine.length === 1 ? "" : "s"}. Remove any with ×.` : "Nothing yet. Pick a few below.";
    document.getElementById("mine").innerHTML = mine.map((f) => `<li><span>${esc(f.label)}</span>
      ${feeds[f.key] ? `<a class="mine-rss" href="${root}${esc(feeds[f.key])}" title="RSS feed for ${esc(f.label)}">RSS</a>` : ""}
      <button type="button" class="mine-x" data-key="${esc(f.key)}" aria-label="Unfollow ${esc(f.label)}">×</button></li>`).join("");
    const keys = new Set(mine.map((f) => f.key));
    const hits = stories.filter((s) => F.keysFor(s).some((k) => keys.has(k)));
    const sec = document.getElementById("new-sec");
    sec.hidden = !mine.length;
    const fresh = hits.filter((s) => lastSeen && s.published_at > lastSeen).length;
    document.getElementById("new-sub").textContent = hits.length ? (fresh ? `${fresh} new since your last visit.` : "Newest first.") : "Nothing in the last two weeks yet. New stories appear here as they're published.";
    document.getElementById("new-list").innerHTML = hits.slice(0, 40).map((s) => `<li style="--c: var(--${esc(s.category)})"><time>${short(s.published_at)}</time>
      <div>${lastSeen && s.published_at > lastSeen ? '<span class="tc-new">New</span> ' : ""}<a href="${root}story/${encodeURIComponent(s.id)}/">${esc(s.headline)}</a></div></li>`).join("");
  }
  document.getElementById("mine").addEventListener("click", (e) => {
    const b = e.target.closest(".mine-x");
    if (b) F.toggle(b.dataset.key);
  });
  document.addEventListener("fw-follows", render);
  fetch(root + "data/site.json", { cache: "no-store" }).then((r) => r.json()).then((d) => { stories = d.stories || []; render(); }).catch(render);
  render();
  if (new URLSearchParams(location.search).get("alerts") === "on") document.getElementById("alerts-on").hidden = false;
  setTimeout(() => { try { localStorage.setItem("fw-last-visit-following", new Date().toISOString()); } catch (e) { /* ignore */ } }, 4000);

  // email alerts (only when the site has an alerts service configured)
  const form = document.getElementById("alert-form");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const msg = document.getElementById("al-msg");
      const follows = F.list().map((f) => f.key);
      if (!follows.length) { msg.textContent = "Follow at least one thing first."; return; }
      msg.textContent = "Sending…";
      fetch(form.dataset.api.replace(/\/$/, "") + "/api/subscribe", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: document.getElementById("al-email").value, follows, labels: F.list(), frequency: document.getElementById("al-freq").value }),
      }).then((r) => r.json().then((j) => ({ ok: r.ok, j }))).then(({ ok, j }) => {
        msg.textContent = ok ? "Check your inbox for a confirmation link." : (j.error || "That didn't work. Try again in a minute.");
      }).catch(() => { msg.textContent = "That didn't work. Try again in a minute."; });
    });
  }
});
