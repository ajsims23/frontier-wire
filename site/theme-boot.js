  // Theme: the site default, a visitor's saved choice, or their system's light/dark setting.
  (function () {
    var DEFAULT_DARK = "abyss";
    var t = null;
    try { t = new URLSearchParams(location.search).get("theme") || localStorage.getItem("fw-theme"); } catch (e) {}
    if (!t) t = window.matchMedia && matchMedia("(prefers-color-scheme: light)").matches ? "daylight" : DEFAULT_DARK;
    document.documentElement.setAttribute("data-theme", t);
    document.documentElement.setAttribute("data-default-dark", DEFAULT_DARK);
  })();
