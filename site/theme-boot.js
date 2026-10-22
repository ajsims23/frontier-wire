  // Theme: dark (Abyss) by default for everyone; light only if the visitor switches to it.
  (function () {
    var DEFAULT_DARK = "abyss";
    var t = null;
    try {
      // one-time reset so earlier automatic choices don't override the new dark default
      if (!localStorage.getItem("fw-theme-v2")) { localStorage.removeItem("fw-theme"); localStorage.setItem("fw-theme-v2", "1"); }
      t = new URLSearchParams(location.search).get("theme") || localStorage.getItem("fw-theme");
    } catch (e) {}
    document.documentElement.setAttribute("data-theme", t || DEFAULT_DARK);
    document.documentElement.setAttribute("data-default-dark", DEFAULT_DARK);
  })();
