// Ask the Wire: instant matching stories in the browser, plus a grounded AI answer from the Frontier Wire API.
import { buildIndex, rank } from "./search.js";

const root = "../";
const form = document.getElementById("ask-form");
const out = document.getElementById("ask-out");
const input = document.getElementById("ask-q");
const api = (form.dataset.api || "").replace(/\/$/, "");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const short = (d) => new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short" });
let index = null;
const ready = fetch(root + "data/search.json").then((r) => r.json()).then((docs) => { index = buildIndex(docs); });

function storyList(items, title) {
  if (!items.length) return "";
  return `<section class="ask-src"><h2>${title}</h2><ol>${items.map((s) => `<li id="src-${s.n || ""}">${s.n ? `<span class="src-n">${s.n}</span>` : ""}
    <a href="${root}story/${encodeURIComponent(s.id)}/">${esc(s.headline)}</a><span class="muted"> ${short(s.date)}</span></li>`).join("")}</ol></section>`;
}

function formatAnswer(text) {
  // escape, then turn [n] into links to the sources and "- " lines into a list
  let html = esc(text).replace(/\[(\d+(?:,\s*\d+)*)\]/g, (m, nums) => nums.split(",").map((n) => `<a class="cite" href="#src-${n.trim()}">${n.trim()}</a>`).join(""));
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const lines = html.split(/\n+/).filter((l) => l.trim());
  let res = "", inList = false;
  for (const l of lines) {
    const m = l.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)/);
    if (m) { if (!inList) { res += "<ul>"; inList = true; } res += `<li>${m[1]}</li>`; }
    else { if (inList) { res += "</ul>"; inList = false; } res += `<p>${l}</p>`; }
  }
  return res + (inList ? "</ul>" : "");
}

async function ask(q) {
  q = q.trim();
  if (q.length < 3) return;
  history.replaceState(null, "", `?q=${encodeURIComponent(q)}`);
  await ready;
  const local = rank(index, q, 8).map((h) => ({ id: h.doc.id, headline: h.doc.h, date: h.doc.d }));
  if (!api) {
    out.innerHTML = local.length ? storyList(local, "Most relevant stories") : `<p class="muted">No stories match that yet. Try different words.</p>`;
    return;
  }
  out.innerHTML = `<div class="ask-answer thinking"><span class="ask-kicker">Answer</span><p><span class="dots"><i></i><i></i><i></i></span> Reading ${local.length || "our"} stories…</p></div>${storyList(local, "Most relevant stories")}`;
  try {
    const r = await fetch(`${api}/api/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ q }) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "error");
    if (!j.answer) {
      out.innerHTML = `<div class="ask-answer"><p>${esc(j.note || "We couldn't write an answer this time. Here are the most relevant stories.")}</p></div>${storyList(j.sources.length ? j.sources : local, "Most relevant stories")}`;
      return;
    }
    out.innerHTML = `<div class="ask-answer"><span class="ask-kicker">Answer</span>${formatAnswer(j.answer)}
      <p class="ex-note">Written by AI from the stories below only. Check the linked stories before relying on it.</p></div>${storyList(j.sources, "Sources")}`;
  } catch (e) {
    out.innerHTML = `<div class="ask-answer"><p>${esc(e.message && e.message !== "error" ? e.message : "The answer service is busy. Here are the most relevant stories.")}</p></div>${storyList(local, "Most relevant stories")}`;
  }
}

form.addEventListener("submit", (e) => { e.preventDefault(); ask(input.value); });
document.getElementById("ask-examples").addEventListener("click", (e) => {
  const b = e.target.closest("[data-q]");
  if (b) { input.value = b.dataset.q; ask(b.dataset.q); }
});
const q0 = new URLSearchParams(location.search).get("q");
if (q0) { input.value = q0; ask(q0); }
