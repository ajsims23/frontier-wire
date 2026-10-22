// Frontier Wire covers: when a story has no photo, draw an editorial cover built around the story's
// key fact (a number, model or company the agent picked from the story) on one of several patterns.
// Shared by the home page and story pages. Exposes window.FWCover(story) -> SVG string.
(function () {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const hash = (t) => { let h = 2166136261; for (const ch of String(t)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
  function rng(seed) { return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const CAT = { models: "Model release", research: "Research", policy: "Policy", safety: "Safety", industry: "Industry", voices: "Commentary" };

  // The big words on the cover: the agent's pick, else a model name, a figure or a distinctive name from the headline.
  function keyText(s) {
    const ok = (t) => t && String(t).length <= 18;
    if (ok(s.cover)) return s.cover;
    if (ok(s.model_name)) return s.model_name;
    const h = String(s.headline || "");
    const money = h.match(/[$₹€£]\s?\d[\d.,]*\s?(?:billion|million|trillion|crore|lakh|bn|[BMK])?\b/i);
    if (money) return money[0].replace(/\s?billion/i, "B").replace(/\s?million/i, "M").replace(/\s?trillion/i, "T");
    const num = h.match(/\b\d[\d.,]*(?:%|x\b|\s?(?:years?|binders|tasks|languages|countries|models|agents|GW|MW)\b)/i);
    if (num) return num[0];
    const SKIP = new Set(["AI", "US", "UK", "EU", "CEO", "API", "LLM", "LLMs", "AGI"]);
    const name = (h.match(/\b(?:[A-Z][a-z]*[A-Z0-9][\w.-]*|[A-Z]{2,}[\w.-]*\d*)\b/g) || []).find((t) => !SKIP.has(t) && t.length <= 16);
    if (name) return name;
    return s.lab && s.lab.length <= 16 ? s.lab : (CAT[s.category] || "AI");
  }

  function pattern(kind, r, W, H) {
    let g = "";
    if (kind === 0) { // dot field with a few lit dots
      for (let y = 18; y < H; y += 20) for (let x = 18; x < W; x += 20) {
        const lit = r() < 0.07;
        g += `<circle cx="${x}" cy="${y}" r="${lit ? 3.2 : 1.4}" fill="${lit ? "var(--c)" : "var(--soft)"}" opacity="${lit ? 0.95 : 0.22}"/>`;
      }
    } else if (kind === 1) { // rings radiating from a corner
      const cx = W * (0.62 + r() * 0.3), cy = H * (0.1 + r() * 0.35);
      for (let i = 1; i <= 11; i++) g += `<circle cx="${cx.toFixed(0)}" cy="${cy.toFixed(0)}" r="${i * 22}" fill="none" stroke="var(--c)" stroke-width="${i % 3 ? 1 : 2}" opacity="${(0.75 - i * 0.055).toFixed(2)}"/>`;
      g += `<circle cx="${cx.toFixed(0)}" cy="${cy.toFixed(0)}" r="6" fill="var(--c)"/>`;
    } else if (kind === 2) { // rising columns, like a chart
      const n = 14, bw = (W * 0.5) / n, x0 = W * 0.47;
      const hs = Array.from({ length: n }, () => 0.15 + r() * 0.85).sort((a, b) => a - b);
      hs.forEach((v, i) => { const bh = v * H * 0.72; g += `<rect x="${(x0 + i * bw).toFixed(1)}" y="${(H - bh).toFixed(1)}" width="${(bw - 3).toFixed(1)}" height="${bh.toFixed(1)}" rx="2" fill="var(--c)" opacity="${(0.12 + (i / n) * 0.55).toFixed(2)}"/>`; });
    } else if (kind === 3) { // perspective grid toward a horizon
      const vx = W * (0.35 + r() * 0.5), hy = H * 0.38;
      for (let i = -10; i <= 10; i++) g += `<line x1="${vx.toFixed(0)}" y1="${hy}" x2="${(vx + i * 60).toFixed(0)}" y2="${H}" stroke="var(--c)" stroke-width="1" opacity=".28"/>`;
      for (let k = 1; k <= 7; k++) { const y = hy + (H - hy) * (k / 7) ** 1.8; g += `<line x1="0" y1="${y.toFixed(1)}" x2="${W}" y2="${y.toFixed(1)}" stroke="var(--c)" stroke-width="1" opacity="${(0.1 + k * 0.04).toFixed(2)}"/>`; }
      g += `<circle cx="${vx.toFixed(0)}" cy="${hy}" r="34" fill="var(--c)" opacity=".18"/><circle cx="${vx.toFixed(0)}" cy="${hy}" r="10" fill="var(--c)"/>`;
    } else { // network of nodes
      const pts = Array.from({ length: 16 }, () => [W * (0.35 + r() * 0.62), H * (0.06 + r() * 0.6)]);
      pts.forEach((p, i) => pts.slice(i + 1).forEach((q) => { if (Math.hypot(p[0] - q[0], p[1] - q[1]) < 95) g += `<line x1="${p[0].toFixed(0)}" y1="${p[1].toFixed(0)}" x2="${q[0].toFixed(0)}" y2="${q[1].toFixed(0)}" stroke="var(--c)" stroke-width="1" opacity=".35"/>`; }));
      pts.forEach((p, i) => { g += `<circle cx="${p[0].toFixed(0)}" cy="${p[1].toFixed(0)}" r="${i % 5 ? 2.6 : 5}" fill="var(--c)" opacity="${i % 5 ? 0.6 : 1}"/>`; });
    }
    return g;
  }

  window.FWCover = function (s) {
    const seed = hash(s.id || s.url || s.headline || "x"), r = rng(seed);
    const W = 400, H = 225, kind = seed % 5, gid = `g${seed.toString(36)}`;
    const text = keyText(s), size = Math.max(30, Math.min(84, 560 / Math.max(3, text.length)));
    const label = (s.lab || CAT[s.category] || "").toUpperCase();
    const gx = (r() * 100).toFixed(0), gy = (r() * 100).toFixed(0);
    return `<svg class="art cover" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMinYMid slice" aria-hidden="true">
      <defs><radialGradient id="${gid}" cx="${gx}%" cy="${gy}%" r="85%"><stop offset="0" stop-color="var(--c)" stop-opacity=".30"/><stop offset="1" stop-color="var(--c)" stop-opacity="0"/></radialGradient></defs>
      <rect width="${W}" height="${H}" fill="var(--panel-2)"/><rect width="${W}" height="${H}" fill="url(#${gid})"/>
      ${pattern(kind, r, W, H)}
      <text x="22" y="34" fill="var(--c)" font-family="Archivo, sans-serif" font-size="12" font-weight="700" letter-spacing="2.2">${esc(label)}</text>
      <text x="20" y="${H - 26}" fill="var(--strong)" font-family="Archivo, sans-serif" font-size="${size.toFixed(0)}" font-weight="800" font-stretch="112%" letter-spacing="-1.5" textLength="${text.length > 9 ? Math.min(W - 40, text.length * size * 0.56).toFixed(0) : ""}" lengthAdjust="spacingAndGlyphs">${esc(text)}</text>
    </svg>`.replace(/ textLength=""/, "");
  };

  // Story pages: fill any .media[data-cover] placeholder.
  document.querySelectorAll(".media[data-cover]").forEach((el) => {
    try { el.insertAdjacentHTML("afterbegin", window.FWCover(JSON.parse(el.dataset.cover))); } catch (e) { /* keep the plain panel */ }
  });
})();
