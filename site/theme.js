// Light/dark toggle (shared by every page) and copy-link buttons.
(function () {
  "use strict";
  const root = document.documentElement;
  const btn = document.getElementById("theme-btn");
  if (btn) {
    const sync = () => btn.setAttribute("aria-label", root.dataset.theme === "daylight" ? "Switch to dark mode" : "Switch to light mode");
    sync();
    btn.addEventListener("click", () => {
      const next = root.dataset.theme === "daylight" ? (root.dataset.defaultDark || "abyss") : "daylight";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("fw-theme", next); } catch (e) {}
      sync();
    });
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-copy]");
    if (!b) return;
    const done = () => { const t = b.textContent; b.textContent = "Link copied"; setTimeout(() => { b.textContent = t; }, 1600); };
    if (navigator.clipboard) navigator.clipboard.writeText(b.dataset.copy).then(done, () => {});
  });
})();

// Header: today's date, and which section the reader is in.
(function () {
  "use strict";
  const d = document.getElementById("u-date");
  if (d) d.textContent = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const here = location.pathname.replace(/index\.html$/, "");
  const links = Array.from(document.querySelectorAll(".secnav a"));
  let best = null, len = 0;
  for (const a of links) {
    const u = new URL(a.getAttribute("href"), location.href);
    if (u.search || u.hash) continue;   // topic filters on the home page
    const p = u.pathname.replace(/index\.html$/, "");
    if ((a.dataset.nav === "home" ? here === p : here.startsWith(p)) && p.length > len) { best = a; len = p.length; }
  }
  if (best) best.setAttribute("aria-current", "page");
  const cur = links.find((a) => a.getAttribute("aria-current"));
  if (cur && cur.scrollIntoView && cur.offsetLeft > window.innerWidth * 0.6) cur.parentElement.scrollLeft = cur.offsetLeft - 16;
})();
