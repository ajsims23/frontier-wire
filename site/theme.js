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
