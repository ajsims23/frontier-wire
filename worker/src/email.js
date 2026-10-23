// Email templates for Frontier Wire alerts and daily digests. Table layout and inline styles, so they render
// in Gmail, Outlook and Apple Mail. Every link goes to frontier wire or the original source.
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https:\/\//.test(String(u || "")) ? esc(u) : "");
const TEAL = "#0f9c8a", INK = "#0d1222", SOFT = "#4b5468", MUTED = "#7a8296", LINE = "#e6e9f0", DARK = "#051416";
const FONT = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";

function storyId(e) { const m = String(e.key || "").match(/^story:([a-z0-9]+)/); return m ? m[1] : ""; }

// Which picture to show: the story's own image, else its Frontier Wire preview card.
export function imageFor(e, site) {
  if (safeUrl(e.image)) return e.image;
  const id = storyId(e);
  return id ? `${site}og/${id}.png` : "";
}

// Keep one entry per tracker (its newest update) and drop exact repeats.
export function tidy(events) {
  const seen = new Set(), latestTracker = new Map(), out = [];
  for (const e of events) {
    const t = String(e.key || "").match(/^tracker:([^:]+):/);
    if (t) { latestTracker.set(t[1], e); continue; }
    const k = (e.title || "").toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(e);
  }
  return [...out, ...latestTracker.values()];
}

export function digestSubject(events) {
  const stories = events.filter((e) => storyId(e));
  const lead = (stories[0] || events[0] || {}).title || "Your Frontier Wire digest";
  const short = lead.length > 70 ? lead.slice(0, 67).replace(/\s+\S*$/, "") + "…" : lead;
  return events.length > 1 ? `${short} + ${events.length - 1} more` : short;
}

function button(href, label) {
  return `<a href="${esc(href)}" style="display:inline-block;background:${DARK};color:#ffffff;${FONT};font-size:14px;font-weight:700;text-decoration:none;padding:10px 18px;border-radius:999px">${esc(label)}</a>`;
}

// The cover is drawn with HTML and CSS, not an image, so every email client shows it, including Outlook,
// which blocks pictures from senders it doesn't know.
const CAT_COLOR = { models: "#8aabff", research: "#5fe3cf", policy: "#ffc266", safety: "#ff8f80", industry: "#c9a4ff", voices: "#f1eee6" };
export function coverText(e) {
  const ok = (t) => t && String(t).length <= 18;
  if (ok(e.cover)) return e.cover;
  const h = String(e.title || "");
  const money = h.match(/[$₹€£]\s?\d[\d.,]*\s?(?:billion|million|trillion|crore|bn|[BMK])?\b/i);
  if (money) return money[0].replace(/\s?billion/i, "B").replace(/\s?million/i, "M").replace(/\s?trillion/i, "T");
  const num = h.match(/\b\d[\d.,]*(?:%|x\b|\s?(?:years?|GW|MW|languages|countries|models|agents)\b)/i);
  if (num) return num[0];
  const SKIP = new Set(["AI", "US", "UK", "EU", "CEO", "API", "LLM", "AGI"]);
  const name = (h.match(/\b(?:[A-Z][a-z]*[A-Z0-9][\w.-]*|[A-Z]{2,}[\w.-]*\d*)\b/g) || []).find((t) => !SKIP.has(t) && t.length <= 16);
  return name || (ok(e.lab) ? e.lab : "");
}

function coverBlock(e, big) {
  const text = coverText(e);
  if (!text) return "";
  const color = CAT_COLOR[e.category] || "#5fe3cf";
  const size = Math.max(28, Math.min(big ? 56 : 40, Math.round((big ? 420 : 330) / Math.max(3, text.length))));
  return `<a href="${esc(e.url)}" style="text-decoration:none"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#0f292d" style="background:#0f292d;border-radius:12px">
    <tr><td style="padding:${big ? "22px 24px 24px" : "16px 20px 18px"};border-left:6px solid ${color};border-radius:12px">
      <p style="margin:0 0 ${big ? 18 : 10}px;${FONT};font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:${color}">${esc((e.lab || e.tag || "Frontier Wire").toUpperCase())}</p>
      <p style="margin:0;${FONT};font-size:${size}px;line-height:1.05;font-weight:800;letter-spacing:-.02em;color:#ffffff">${esc(text)}</p>
    </td></tr></table></a>`;
}

function storyCard(e, site, big) {
  const cover = coverBlock(e, big);
  return `<tr><td style="padding:0 0 26px">
    ${cover}
    <p style="margin:${cover ? "14px" : "0"} 0 6px;${FONT};font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:${TEAL}">${esc(e.tag || "Story")}${e.because ? ` · <span style="color:${MUTED};font-weight:600;letter-spacing:0;text-transform:none">You follow ${esc(e.because)}</span>` : ""}</p>
    <a href="${esc(e.url)}" style="${FONT};font-size:${big ? 22 : 18}px;line-height:1.3;font-weight:800;color:${INK};text-decoration:none">${esc(e.title)}</a>
    <p style="margin:8px 0 0;${FONT};font-size:15px;line-height:1.55;color:${SOFT}">${esc(e.summary || "")}</p>
    ${e.audience ? `<p style="margin:10px 0 0;padding:8px 12px;border-left:3px solid ${TEAL};background:#f3faf9;${FONT};font-size:14px;line-height:1.5;color:${SOFT}">${esc(e.audience)}</p>` : ""}
  </td></tr>`;
}

function compactRow(e, label, color) {
  return `<tr><td style="padding:12px 0;border-top:1px solid ${LINE}">
    <p style="margin:0 0 4px;${FONT};font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:${color}">${esc(label)}</p>
    <a href="${esc(e.url)}" style="${FONT};font-size:16px;font-weight:700;color:${INK};text-decoration:none">${esc(e.title)}</a>
    ${e.summary ? `<p style="margin:4px 0 0;${FONT};font-size:14px;line-height:1.5;color:${SOFT}">${esc(e.summary)}</p>` : ""}
  </td></tr>`;
}

function section(title, rows) {
  if (!rows) return "";
  return `<tr><td style="padding:8px 0 10px"><p style="margin:0;${FONT};font-size:13px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:${INK}">${esc(title)}</p></td></tr>${rows}`;
}

function briefingBox(b, site) {
  if (!b || !b.one_line) return "";
  const themes = (b.themes || []).slice(0, 3).map((t) => `<li style="margin:0 0 6px"><b style="color:${INK}">${esc(t.title)}.</b> ${esc(t.text)}</li>`).join("");
  return `<tr><td style="padding:0 0 26px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3faf9;border-radius:12px;border:1px solid #d5efeb"><tr><td style="padding:18px 20px">
    <p style="margin:0 0 6px;${FONT};font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:${TEAL}">Today in AI</p>
    <p style="margin:0 0 10px;${FONT};font-size:17px;line-height:1.45;font-weight:700;color:${INK}">${esc(b.one_line)}</p>
    ${themes ? `<ul style="margin:0;padding-left:18px;${FONT};font-size:14px;line-height:1.5;color:${SOFT}">${themes}</ul>` : ""}
    <p style="margin:12px 0 0"><a href="${esc(site)}" style="${FONT};font-size:14px;font-weight:700;color:${TEAL};text-decoration:none">Read the full briefing →</a></p>
  </td></tr></table></td></tr>`;
}

export function renderEmail({ site, api, events, briefing, unsub, kind }) {
  const list = tidy(events);
  const stories = list.filter((e) => storyId(e));
  const trackers = list.filter((e) => /^tracker:/.test(e.key || ""));
  const models = list.filter((e) => /^model:/.test(e.key || ""));
  const claims = list.filter((e) => /^claim:/.test(e.key || ""));
  const date = new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "Asia/Kolkata" });
  const preheader = stories[0] ? stories[0].title : "What moved in AI for the things you follow";
  const body = [
    briefingBox(briefing, site),
    section(stories.length ? "From what you follow" : "", stories.map((e, i) => storyCard(e, site, i === 0)).join("")),
    section(trackers.length ? "Where things stand" : "", trackers.map((e) => compactRow(e, "Tracker update", "#b7791f")).join("")),
    section(models.length ? "Model tracker" : "", models.map((e) => compactRow(e, "Model change", "#2f5bd8")).join("")),
    section(claims.length ? "Claims check" : "", claims.map((e) => compactRow(e, "Claim resolved", "#c93d2f")).join("")),
  ].join("");
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light only"><title>Frontier Wire</title></head>
<body style="margin:0;padding:0;background:#eef1f5">
<span style="display:none;max-height:0;overflow:hidden;opacity:0">${esc(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef1f5"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden">
  <tr><td style="background:${DARK};padding:22px 24px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="${FONT};font-size:20px;font-weight:800;color:#ffffff;letter-spacing:-.01em"><span style="color:#5fe3cf">▌</span> Frontier Wire</td>
      <td align="right" style="${FONT};font-size:12px;color:#84a6a1">${esc(kind === "digest" ? "Your daily digest" : "Alert")}<br>${esc(date)}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:24px 24px 6px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">${body}</table></td></tr>
  <tr><td style="padding:6px 24px 26px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f7f8fa;border-radius:12px"><tr><td style="padding:16px 18px">
    <p style="margin:0 0 10px;${FONT};font-size:15px;font-weight:700;color:${INK}">Got a question about any of this?</p>
    ${button(`${site}ask/`, "Ask the Wire")}&nbsp;&nbsp;<a href="${esc(site)}following/" style="${FONT};font-size:14px;font-weight:700;color:${TEAL};text-decoration:none">Manage what you follow</a>
  </td></tr></table></td></tr>
  <tr><td style="padding:0 24px 24px;${FONT};font-size:12px;line-height:1.5;color:${MUTED}">
    Every story on Frontier Wire is checked against its sources by our newsroom agent. You get this because you follow these on <a href="${esc(site)}following/" style="color:${MUTED}">Frontier Wire</a>.
    ${unsub ? `<a href="${esc(api)}/api/unsubscribe?t=${esc(unsub)}" style="color:${MUTED}">Unsubscribe</a>.` : ""}
  </td></tr>
</table></td></tr></table></body></html>`;
}
