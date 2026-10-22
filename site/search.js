// Frontier Wire search: BM25 ranking over the story archive (data/search.json).
// One file used by both the Ask page in the browser and the Ask service (Cloudflare Worker).
const STOP = new Set("a an and are as at be by for from has have how i in into is it its of on or that the this to was were what when where which who why will with about after did does do new".split(" "));

export function tokens(text) {
  return String(text || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .split(/[^a-z0-9.$%₹-]+/).map((t) => t.replace(/^[.-]+|[.-]+$/g, "")).filter((t) => t.length > 1 && !STOP.has(t));
}

function docText(d) {
  return `${d.h} ${d.h} ${d.l || ""} ${d.s || ""} ${d.w || ""} ${(d.t || []).join(" ")} ${d.a || ""} ${d.k || ""}`;
}

export function buildIndex(docs) {
  const tf = [], df = new Map();
  let total = 0;
  for (const d of docs) {
    const counts = new Map();
    for (const t of tokens(docText(d))) counts.set(t, (counts.get(t) || 0) + 1);
    let len = 0;
    for (const [t, n] of counts) { len += n; df.set(t, (df.get(t) || 0) + 1); }
    tf.push({ counts, len });
    total += len;
  }
  return { docs, tf, df, avg: total / Math.max(1, docs.length) };
}

// BM25 with a small boost for recency, so "latest" questions favour new stories.
export function rank(index, query, limit = 8, now = Date.now()) {
  const q = [...new Set(tokens(query))];
  if (!q.length) return [];
  const N = index.docs.length, k1 = 1.4, b = 0.75;
  const out = [];
  index.docs.forEach((d, i) => {
    const { counts, len } = index.tf[i];
    let score = 0;
    for (const t of q) {
      const f = counts.get(t);
      if (!f) continue;
      const n = index.df.get(t) || 0;
      const idf = Math.log(1 + (N - n + 0.5) / (n + 0.5));
      score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * len / index.avg));
    }
    if (score > 0) {
      const ageDays = Math.max(0, (now - new Date(d.d).getTime()) / 86400000);
      out.push({ doc: d, score: score * (1 + 0.25 * Math.exp(-ageDays / 14)) });
    }
  });
  return out.sort((x, y) => y.score - x.score).slice(0, limit);
}
