// Frontier Wire follows: readers follow labs, trackers, sectors and topics. Follows live in this browser
// (no account needed) and drive the "For you" section, per-topic RSS feeds and, when enabled, email alerts.
(function () {
  "use strict";
  const KEY = "fw-follows";
  const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || "[]").filter((f) => f && f.key); } catch (e) { return []; } };
  const write = (list) => { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* private mode */ } };

  const api = {
    list: read,
    has: (key) => read().some((f) => f.key === key),
    toggle(key, label) {
      const list = read();
      const i = list.findIndex((f) => f.key === key);
      if (i >= 0) list.splice(i, 1); else list.push({ key, label: label || key });
      write(list);
      refresh();
      document.dispatchEvent(new CustomEvent("fw-follows"));
      return i < 0;
    },
    // which follow keys a story matches
    keysFor(s) {
      const k = [];
      if (s.lab) k.push(`lab:${s.lab}`);
      (s.trackers || []).forEach((t) => k.push(`tracker:${t}`));
      (s.sectors || []).forEach((t) => k.push(`sector:${t}`));
      if (s.category) k.push(`topic:${s.category}`);
      if ((s.regions || []).includes("india") || (!s.regions && s.desk === "india")) k.push("region:india");
      if (s.deal) k.push("deals");
      return k;
    },
  };
  window.FWFollow = api;

  function refresh() {
    const mine = new Set(read().map((f) => f.key));
    document.querySelectorAll("[data-follow]").forEach((b) => {
      const on = mine.has(b.dataset.follow);
      b.hidden = false;
      b.setAttribute("aria-pressed", String(on));
      b.classList.toggle("on", on);
      b.textContent = on ? "Following ✓" : (b.dataset.cta || "Follow");
    });
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-follow]");
    if (!b) return;
    e.preventDefault();
    api.toggle(b.dataset.follow, b.dataset.label);
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", refresh); else refresh();
  api.refresh = refresh;
})();

// close the nav's Desks menu when clicking elsewhere or pressing Escape
document.addEventListener("click", (e) => {
  document.querySelectorAll("details.nav-menu[open]").forEach((d) => { if (!d.contains(e.target)) d.removeAttribute("open"); });
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.querySelectorAll("details.nav-menu[open]").forEach((d) => d.removeAttribute("open"));
});
