/* Frontier Wire bulletin engine.
 *
 * init(timeline, world) builds the programme; seek(t) poses every element for time t (seconds). Nothing animates on
 * its own: every position, opacity and number is a function of t, so each frame can be captured independently and
 * every render of the same timeline is identical. Layout adapts to the viewport: 16:9 (1920x1080) or 9:16
 * (1080x1920, with word-by-word captions for Shorts and Reels).
 */
(function () {
  "use strict";
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);
  const easeIO = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  const back = (x) => { x = clamp(x); const c1 = 1.5, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
  const K = (t, t0, d, fn = ease) => fn((t - t0) / d);
  const lerp = (a, b, k) => a + (b - a) * k;
  function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function el(tag, cls, parent, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; if (parent) parent.appendChild(e); return e; }
  function css(e, o) { for (const k in o) e.style[k] = o[k]; return e; }
  const esc = (s) => String(s || "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  function rgba(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`; }
  function fmtNum(pre, x, dec, suf) { const s = x >= 1000 ? x.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : x.toFixed(dec); return pre + s + suf; }
  const show = (e, k, dy = 0, dx = 0, sc = 1) => { e.style.opacity = clamp(k); e.style.transform = `translate(${dx}px,${dy}px) scale(${sc})`; e.style.visibility = k <= 0.001 ? "hidden" : "visible"; };

  let TL, W, H, U, V, root, S = {};
  const px = (n) => n * U;

  window.init = function (tl, world) {
    TL = tl; W = window.innerWidth; H = window.innerHeight; V = H > W; U = V ? W / 1080 : H / 1080;
    root = document.getElementById("root");
    root.style.setProperty("--u", U);
    root.style.setProperty("--accent", tl.accent);
    S.world = prepWorld(world);
    buildSet(); buildChrome(); buildScenes(); buildCaptions(); buildOverlays();
  };

  window.layout = function () {  // measure each scene while it is shown, then hide it again
    for (const sc of S.scenes) { sc.root.style.display = "block"; if (sc.layout) sc.layout(); sc.root.style.display = "none"; }
  };
  // cue times in order: an item the anchor doesn't name comes just after the one before it
  function ordered(cues, first, gap, latest) {
    // never leave the graphic waiting on an empty screen: item i shows by latest + i * gap at the latest
    const out = []; let prev = first - gap;
    cues.forEach((c, i) => {
      let x = c != null ? c : prev + gap;
      if (latest != null) x = Math.min(x, latest + i * gap);
      x = Math.max(x, prev + 0.25); out.push(x); prev = x;
    });
    return out;
  }

  // B-roll is a folder of frames per story; an <img> shows the frame for the playhead, and seek() waits for the
  // frames it changed to decode before the capture
  const pending = [];
  const frameSrc = (b, f) => "file://" + b.dir + "/" + String(clamp(f, 0, b.n - 1) + 1).padStart(4, "0") + ".jpg";
  function setImg(img, src) { if (img._src !== src) { img._src = src; img.src = src; pending.push(img.decode().catch(() => {})); } }
  function brollImg(parent) { const im = el("img", "abs", parent); css(im, { left: 0, top: 0, width: "100%", height: "100%", objectFit: "cover" }); return im; }

  window.seek = function (t) {
    pending.length = 0;
    const scs = S.scenes;
    let cur = scs.findIndex((s) => t >= s.d.start && t < s.d.start + s.d.dur);
    if (cur < 0) cur = t < 0 ? 0 : scs.length - 1;
    for (let i = 0; i < scs.length; i++) {
      const on = i === cur;
      scs[i].root.style.display = on ? "block" : "none";
      if (on) scs[i].update(t, t - scs[i].d.start);
    }
    updateSet(t, scs[cur]); updateChrome(t, cur); updateCaptions(t); updateOverlays(t, cur);
    return Promise.all(pending);
  };

  // ------------------------------------------------------------ the virtual set
  function buildSet() {
    const bg = el("div", "layer", root); bg.id = "bg";
    S.blobs = [0, 1, 2].map(() => el("div", "blob", bg));
    S.floor = el("div", "", bg); S.floor.id = "floor";
    const beams = el("div", "", bg); beams.id = "beams";
    S.beams = [0, 1, 2].map(() => el("div", "beam", beams));
    S.stage = el("div", "layer", root);
    const vig = el("div", "layer", root); vig.id = "vignette";

  }
  function updateSet(t, scene) {
    const col = scene.d.color || TL.accent;
    const sizes = [1.0, 0.75, 0.6];
    S.blobs.forEach((b, i) => {
      const s = px(900 * sizes[i]);
      const x = W * (0.25 + 0.5 * i / 2) + Math.sin(t * 0.13 + i * 2.1) * px(220);
      const y = H * (0.3 + 0.18 * i) + Math.cos(t * 0.11 + i * 1.3) * px(140);
      const c = i === 1 ? "#0f4a52" : col;  // soft light as a gradient: a CSS blur this size costs ~250 ms a frame
      css(b, { width: s * 1.6 + "px", height: s * 1.6 + "px", left: (x - s * 0.8) + "px", top: (y - s * 0.8) + "px", background: `radial-gradient(circle, ${rgba(c, i === 1 ? 0.5 : 0.36)} 0%, ${rgba(c, i === 1 ? 0.22 : 0.14)} 30%, ${rgba(c, 0)} 62%)` });
    });
    css(S.floor, { transform: `perspective(${px(700)}px) rotateX(64deg) translateY(${(t * px(30)) % px(90)}px)` });
    S.beams.forEach((b, i) => css(b, { left: ((((t * 0.04 + i * 0.37) % 1.4) - 0.2) * W) + "px", transform: `skewX(-18deg)` }));

  }

  // ------------------------------------------------------------ chrome: bug, progress, ticker
  function markEl(parent, h, colors) {
    const m = el("div", "mark", parent); m.style.height = h + "px";
    const hs = [0.45, 0.75, 1.0, 0.6];
    return hs.map((x, i) => { const b = el("i", "", m); css(b, { height: (x * h) + "px", width: (h * 0.22) + "px", background: colors[i % colors.length] }); return b; });
  }
  function buildChrome() {
    S.bug = el("div", "abs", root); S.bug.id = "bug";
    S.bugMark = markEl(S.bug, px(26), [TL.accent, "#8aabff", "#ffc266", TL.accent]);
    el("div", "brand", S.bug, "Frontier Wire");
    el("div", "tag", S.bug, "TODAY IN AI");
    if (!V) el("div", "date", S.bug, esc(TL.date));
    else { css(S.bug, { flexWrap: "wrap", width: px(700) + "px", rowGap: px(10) + "px" }); el("div", "date", S.bug, esc(TL.date)); }
    S.progress = el("div", "abs", root); S.progress.id = "progress";
    if (V) css(S.progress, { left: px(64) + "px", right: "auto", top: px(150) + "px" });
    const stories = TL.scenes.filter((s) => s.kind === "story");
    S.segs = stories.map((s) => { const seg = el("div", "seg", S.progress); const b = el("b", "", seg); b.style.background = s.color; return b; });
    const tk = el("div", "abs", root); tk.id = "ticker";
    el("div", "lab", tk, "HEADLINES");
    S.run = el("div", "run", tk);
    const items = TL.ticker.map((x) => `<span>${esc(x)}</span>`).join("");
    S.run.innerHTML = items + items + items;
  }
  function updateChrome(t, cur) {
    const stories = TL.scenes.filter((s) => s.kind === "story");
    stories.forEach((s, i) => { S.segs[i].style.width = (clamp((t - s.start) / s.dur) * 100) + "%"; });
    const k = K(t, 0.6, 0.5);
    show(S.bug, k); show(S.progress, K(t, TL.scenes[1] ? TL.scenes[1].start - 0.2 : 0, 0.5));
    const w = S.run.scrollWidth / 3 || 1;
    S.run.style.transform = `translateX(${px(V ? 190 : 210) - ((t * px(110)) % w)}px)`;
  }

  // ------------------------------------------------------------ scenes
  function buildScenes() {
    S.scenes = TL.scenes.map((d) => {
      const r = el("div", "layer", S.stage); r.style.display = "none";
      const sc = d.kind === "open" ? openScene(d, r) : d.kind === "close" ? closeScene(d, r) : storyScene(d, r);
      sc.root = r; sc.d = d; return sc;
    });
  }

  // the open: a title sting, then tonight's rundown as the anchor teases it
  function openScene(d, r) {
    const reel = TL.scenes.filter((s) => s.kind === "story" && s.broll).map((s) => s.broll);
    const mont = reel.length ? brollImg(r) : null;
    const shade = reel.length ? el("div", "layer", r) : null;
    if (shade) shade.style.background = "linear-gradient(180deg, rgba(5,13,16,.55), rgba(5,13,16,.82))";
    const wrap = el("div", "abs title", r); css(wrap, { left: 0, right: 0, transformOrigin: "50% 50%" });
    const lock = el("div", "", wrap); css(lock, { display: "flex", justifyContent: "center", alignItems: V ? "center" : "flex-end", gap: px(26) + "px", flexDirection: V ? "column" : "row" });
    const bars = markEl(lock, px(V ? 120 : 110), [TL.accent, "#8aabff", "#ffc266", TL.accent]);
    const word = el("div", "big", lock); word.style.fontSize = px(V ? 150 : 150) + "px"; if (V) word.style.textAlign = "center";
    const chars = [...(V ? "FRONTIER\nWIRE" : "FRONTIER WIRE")].map((c) => c === "\n" ? (el("br", "", word), null) : el("span", "ch", word, c === " " ? "&nbsp;" : esc(c))).filter(Boolean);
    const sub = el("div", "", wrap); css(sub, { marginTop: px(34) + "px", display: "flex", justifyContent: "center", gap: px(20) + "px", alignItems: "center", flexWrap: "wrap" });
    const tag = el("div", "tag", sub, "TODAY IN AI"); tag.style.fontSize = px(30) + "px";
    const dt = el("div", "date", sub, esc((TL.weekday ? TL.weekday + "  ·  " : "") + TL.date)); dt.style.fontSize = px(30) + "px";
    const rule = el("div", "", wrap); css(rule, { height: px(4) + "px", background: TL.accent, margin: `${px(30)}px auto 0`, width: px(V ? 700 : 900) + "px", transformOrigin: "50% 50%" });

    const rund = el("div", "abs rund", r);
    const head = el("div", "", rund); css(head, { display: "flex", alignItems: "center", gap: px(18) + "px", marginBottom: px(26) + "px" });
    const ht = el("div", "big", head, "TONIGHT"); ht.style.fontSize = px(V ? 84 : 76) + "px";
    const hl = el("div", "", head); css(hl, { flex: "1", height: px(4) + "px", background: TL.accent, transformOrigin: "0 50%" });
    const rows = d.tiles.map((tile, i) => {
      const row = el("div", "row", rund); row.style.borderLeftColor = tile.color;
      const n = el("div", "n", row, String(i + 1).padStart(2, "0")); n.style.color = tile.color;
      if (!V) { const k = el("div", "k", row, esc(tile.label)); k.style.color = tile.color; }
      const h = el("div", "h", row, esc(tile.line)); if (V) h.style.fontSize = px(36) + "px";
      return { row, tile };
    });
    const words = d.words || [];
    const greetN = (TL.greeting_words || 0);
    const teaser = d.teaser_t != null ? d.teaser_t - d.start : Math.min(d.dur * 0.42, 6.5);
    const sc = {
      layout() {
        css(wrap, { top: (H * (V ? 0.36 : 0.33)) + "px" });
        css(rund, { top: px(V ? 330 : 190) + "px" });
      },
      update(t, lt) {
        if (mont) {  // cut through the day's clips, about one a second and a half
          const k = Math.floor(lt / 1.5), b = reel[k % reel.length];
          setImg(mont, frameSrc(b, Math.floor((lt - k * 1.5 + 1) * TL.fps)));
          mont.style.opacity = 0.55 * K(lt, 0.2, 1.0);
          mont.style.transform = `scale(${1.08 - 0.05 * ((lt % 1.5) / 1.5)})`;
        }
        bars.forEach((b, i) => { b.style.transform = `scaleY(${back((lt - 0.1 - i * 0.07) / 0.5)})`; b.style.transformOrigin = "50% 100%"; });
        chars.forEach((c, i) => { const k = K(lt, 0.25 + i * 0.035, 0.5); c.style.opacity = k; c.style.transform = `translateY(${(1 - k) * px(60)}px)`; });
        show(sub, K(lt, 0.9, 0.5), (1 - K(lt, 0.9, 0.5)) * px(16));
        rule.style.transform = `scaleX(${K(lt, 0.8, 0.9, easeIO)})`;
        // the title lifts away as the anchor starts the rundown
        const out = K(lt, teaser - 0.5, 0.6, easeIO);
        const drift = 1 + 0.04 * clamp(lt / Math.max(teaser, 1));
        wrap.style.opacity = 1 - out;
        wrap.style.transform = `translateY(${-out * px(120)}px) scale(${drift * (1 - out * 0.15)})`;
        show(ht, K(lt, teaser - 0.1, 0.5), (1 - K(lt, teaser - 0.1, 0.5)) * px(30));
        hl.style.transform = `scaleX(${K(lt, teaser, 0.8, easeIO)})`;
        const lastCue = rows.reduce((m, x) => (x.tile.cue != null && x.tile.cue - d.start <= lt ? Math.max(m, x.tile.cue - d.start) : m), -1);
        rows.forEach(({ row, tile }, i) => {
          const t0 = teaser + 0.25 + i * 0.32;
          const k = K(lt, t0, 0.55);
          show(row, k, 0, (1 - k) * px(140));
          const said = tile.cue != null && tile.cue - d.start <= lt;
          const now = said && tile.cue - d.start === lastCue;
          row.style.background = now ? rgba(tile.color, 0.22) : "rgba(6,19,22,.78)";
          row.style.transform += now ? ` scale(1.015)` : "";
        });
        const endk = K(lt, d.dur - 0.5, 0.4);
        rund.style.opacity = 1 - endk * 0.6;
      },
    };
    return sc;
  }

  // a story: a headline slam, then the explainer graphic with the lower third
  function storyScene(d, r) {
    const B = d.broll;
    const vid = B ? brollImg(r) : null;
    const grade = B ? el("div", "layer", r) : null;
    if (grade) grade.style.background = V
      ? "linear-gradient(180deg, rgba(5,13,16,.35) 0%, rgba(5,13,16,.15) 35%, rgba(5,13,16,.8) 70%, rgba(5,13,16,.95) 100%)"
      : "linear-gradient(90deg, rgba(5,13,16,.88) 0%, rgba(5,13,16,.55) 45%, rgba(5,13,16,.15) 75%), linear-gradient(180deg, rgba(5,13,16,0) 60%, rgba(5,13,16,.7) 100%)";
    const credit = B ? el("div", "abs", r, (B.kind === "photo" ? "PHOTO  \u00b7  " : "STOCK FOOTAGE  \u00b7  ") + esc(B.credit)) : null;
    if (credit) css(credit, { right: px(64) + "px", fontWeight: 700, fontSize: px(17) + "px", letterSpacing: ".08em", color: "rgba(230,240,238,.75)", background: "rgba(5,13,16,.55)", padding: `${px(5)}px ${px(10)}px` });
    const ghost = el("div", "abs ghostnum", r, String(d.i).padStart(2, "0"));
    css(ghost, { fontSize: px(V ? 520 : 560) + "px", right: px(V ? -30 : 40) + "px", top: px(V ? 180 : 120) + "px" });
    const slam = el("div", "abs", r);
    css(slam, V ? { left: px(56) + "px", right: px(56) + "px", top: px(560) + "px" } : { left: px(96) + "px", right: px(300) + "px", top: px(250) + "px" });
    const kick = el("div", "kicker", slam, esc(d.label + (d.lab ? "  ·  " + d.lab : "")));
    kick.style.background = d.color;
    const hl = el("div", "slam", slam); css(hl, { fontSize: px(V ? 92 : 104) + "px", marginTop: px(26) + "px" });
    const ws = d.line.split(/\s+/).map((w) => el("span", "w", hl, esc(w)));
    const ul = el("div", "", slam); css(ul, { height: px(8) + "px", width: px(220) + "px", background: d.color, marginTop: px(30) + "px", transformOrigin: "0 50%" });

    const l3 = el("div", "abs l3", r);
    if (V) css(l3, { left: px(40) + "px", right: px(40) + "px" });
    const chip = el("div", "kicker", l3, esc(d.label + (d.lab ? "  ·  " + d.lab : ""))); chip.style.background = d.color;
    const bar = el("div", "bar", l3, esc(d.line)); bar.style.borderLeftColor = d.color;
    if (V) bar.style.fontSize = px(54) + "px";
    const plate = el("div", "plate", l3);
    const det = el("div", "det", plate, esc(d.detail)); if (V) det.style.fontSize = px(36) + "px";
    el("div", "src", plate, "SOURCE: " + esc(d.source));

    const gbox = el("div", "abs", r);
    let g = null;
    const s2 = d.shot2;
    const sc = {
      layout() {
        const top = V ? px(1010) : H - px(62) - px(30) - l3.offsetHeight;
        css(l3, { top: top + "px" });
        const box = V ? { left: px(40), top: px(250), w: W - px(80), h: px(720) } : { left: px(96), top: px(138), w: W - px(192), h: top - px(36) - px(138) };
        css(gbox, { left: box.left + "px", top: box.top + "px", width: box.w + "px", height: box.h + "px" });
        g = d.graphic ? makeGraphic(d.graphic, gbox, box.w, box.h, d) : figureGraphic(d, gbox, box.w, box.h);
      },
      update(t, lt) {
        // the footage: shot 1, and a closing shot on longer stories (s3)
        let vk = 0;
        if (B) {
          const s3 = d.dur - d.shot2 >= 8.5 ? d.dur - 3.0 : null;
          vk = Math.max(1 - K(lt, s2 - 0.05, 0.4), s3 != null ? K(lt, s3, 0.45) : 0);
          if (vk > 0.001) {
            setImg(vid, frameSrc(B, Math.floor(lt * TL.fps)));
            css(vid, { opacity: vk, visibility: "visible", transform: `scale(${1.08 - 0.06 * clamp(lt / d.dur)})` });
          } else vid.style.visibility = "hidden";
          grade.style.opacity = vk;
          css(credit, { top: (vk > 0 && lt > s2 ? (l3.offsetTop - px(44)) : H - px(62) - px(46)) + "px" });
          show(credit, vk * K(lt, 0.4, 0.4));
        }
        // shot 1: the headline slams in
        const out = K(lt, s2 - 0.1, 0.45, easeIO);
        show(ghost, K(lt, 0.1, 0.8) * (1 - out) , 0, (1 - K(lt, 0.1, 1.2)) * px(80), 1 + 0.04 * clamp(lt / 4));
        show(kick, K(lt, 0.2, 0.4) * (1 - out), 0, (1 - K(lt, 0.2, 0.4)) * -px(40));
        ws.forEach((w, i) => { const k = K(lt, 0.3 + i * 0.06, 0.45); w.style.opacity = k * (1 - out); w.style.transform = `translateY(${(1 - k) * px(70) - out * px(60)}px)`; });
        ul.style.transform = `scaleX(${K(lt, 0.5 + ws.length * 0.06, 0.6, easeIO) * (1 - out)})`;
        slam.style.transform = `scale(${1 + 0.025 * clamp(lt / 3)})`;
        // shot 2: lower third and graphic
        const k1 = K(lt, s2, 0.4), k2 = K(lt, s2 + 0.15, 0.5), k3 = K(lt, s2 + 0.45, 0.5);
        chip.style.clipPath = `inset(0 ${(1 - k1) * 100}% 0 0)`; chip.style.visibility = k1 > 0 ? "visible" : "hidden";
        bar.style.clipPath = `inset(0 ${(1 - k2) * 100}% 0 0)`; bar.style.visibility = k2 > 0 ? "visible" : "hidden";
        show(plate, k3, (1 - k3) * px(18));
        if (g) {
          const s3 = B && d.dur - d.shot2 >= 8.5 ? d.dur - 3.0 : null;
          const kg = K(lt, s2 + 0.05, 0.5) * (s3 != null ? 1 - K(lt, s3 - 0.1, 0.4) : 1);
          gbox.style.opacity = kg; gbox.style.visibility = kg > 0 ? "visible" : "hidden"; g(t, lt);
        }
      },
    };
    return sc;
  }

  // the close: the day's stories at a glance, then the website
  function closeScene(d, r) {
    const head = el("div", "abs big", r, "THAT'S THE DAY IN AI");
    css(head, { left: px(V ? 56 : 96) + "px", top: px(V ? 260 : 170) + "px", fontSize: px(V ? 78 : 74) + "px" });
    const stories = TL.scenes.filter((s) => s.kind === "story");
    const cards = stories.map((s, i) => {
      const c = el("div", "card", r); c.style.borderTopColor = s.color;
      if (s.broll) { const im = el("img", "", c); im.src = frameSrc(s.broll, Math.min(s.broll.n - 1, TL.fps)); css(im, { display: "block", width: `calc(100% + ${px(44)}px)`, margin: `-${px(20)}px -${px(22)}px ${px(14)}px`, height: px(V ? 0 : 150) + "px", objectFit: "cover", opacity: 0.9 }); if (V) im.style.display = "none"; }
      const n = el("div", "cn", c, String(i + 1).padStart(2, "0")); n.style.color = s.color;
      const k = el("div", "ck", c, esc(s.label)); k.style.color = s.color;
      el("div", "ch2", c, esc(s.line));
      return c;
    });
    const lock = el("div", "abs", r);
    css(lock, { left: 0, right: 0, textAlign: "center" });
    const lk = el("div", "", lock); css(lk, { display: "flex", justifyContent: "center", alignItems: "flex-end", gap: px(22) + "px" });
    const bars = markEl(lk, px(90), [TL.accent, "#8aabff", "#ffc266", TL.accent]);
    const bw = el("div", "big", lk, "Frontier Wire"); bw.style.fontSize = px(V ? 104 : 116) + "px";
    const url = el("div", "", lock, esc(TL.site)); css(url, { marginTop: px(28) + "px", fontWeight: 760, fontSize: px(V ? 40 : 44) + "px", color: TL.accent, letterSpacing: ".02em" });
    const pill = el("div", "pill", lock, "Every story, with its sources  ·  Free daily briefing"); css(pill, { marginTop: px(30) + "px" });
    if (V) pill.style.fontSize = px(30) + "px";
    const swap = d.url_cue != null ? d.url_cue - d.start : d.dur * 0.5;
    return {
      layout() {
        const n = cards.length;
        if (!V) {
          const gap = px(22), w = (W - px(192) - gap * (n - 1)) / n;
          cards.forEach((c, i) => css(c, { left: (px(96) + i * (w + gap)) + "px", top: px(320) + "px", width: w + "px", minHeight: px(330) + "px" }));
          css(lock, { top: (H * 0.3) + "px" });
        } else {
          cards.forEach((c, i) => css(c, { left: px(56) + "px", right: px(56) + "px", top: (px(420) + i * px(250)) + "px", minHeight: px(220) + "px" }));
          css(lock, { top: (H * 0.36) + "px" });
        }
      },
      update(t, lt) {
        const out = K(lt, swap - 0.3, 0.6, easeIO);
        const kh = K(lt, 0.15, 0.5);
        show(head, kh * (1 - out), (1 - kh) * px(30) - out * px(40));
        cards.forEach((c, i) => { const k = K(lt, 0.35 + i * 0.12, 0.5); show(c, k * (1 - out), (1 - k) * px(50) - out * px(40), 0, 1 - out * 0.04); });
        bars.forEach((b, i) => { b.style.transformOrigin = "50% 100%"; b.style.transform = `scaleY(${back((lt - swap - 0.1 - i * 0.07) / 0.5)})`; });
        show(bw, K(lt, swap + 0.1, 0.5), (1 - K(lt, swap + 0.1, 0.5)) * px(30));
        show(url, K(lt, swap + 0.45, 0.5), (1 - K(lt, swap + 0.45, 0.5)) * px(20));
        show(pill, K(lt, swap + 0.8, 0.5), (1 - K(lt, swap + 0.8, 0.5)) * px(20));
        lock.style.transform = `scale(${1 + 0.03 * clamp((lt - swap) / 6)})`;
      },
    };
  }

  // ------------------------------------------------------------ graphics
  function capEl(parent, text, color) {
    if (!text) return null;
    const c = el("div", "gcap", parent); c.style.color = color;
    const i = el("i", "", c); i.style.background = color;
    el("span", "", c, esc(text));
    return c;
  }
  const at = (cue, fallback) => (cue != null ? cue : fallback);

  function makeGraphic(g, box, w, h, d) {
    const f = { map: gMap, number: gNumber, change: gChange, bars: gBars, list: gList, steps: gSteps, quote: gQuote }[g.type];
    return f ? f(g, box, w, h, d) : null;
  }

  function figureGraphic(d, box, w, h) {  // no graphic in the script: the key figure, big
    if (!d.figure) return null;
    const n = el("div", "abs num", box, esc(d.figure)); css(n, { fontSize: Math.min(h * 0.8, px(240)) + "px", right: 0, top: px(10) + "px", color: "#eef4f2" });
    return (t, lt) => show(n, K(lt, d.shot2 + 0.2, 0.5), 0, (1 - K(lt, d.shot2 + 0.2, 0.6)) * px(60));
  }

  // a world map: flies in from the globe to the places, lights them up as the anchor names them, draws the route
  function gMap(g, box, w, h, d) {
    const cap = capEl(box, g.caption, d.color);
    const capH = cap ? px(56) : 0;
    const mh = h - capH;
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg"); svg.setAttribute("width", w); svg.setAttribute("height", mh);
    css(svg, { position: "absolute", left: 0, top: capH + "px", overflow: "hidden" });
    box.appendChild(svg);
    const places = g.places || [];
    const focus = [];
    for (const p of places) {
      const [lo, la] = p.pin; const dx = p.city ? 9 : 16, dy = p.city ? 6 : 11;
      focus.push([lo - dx, la - dy], [lo + dx, la + dy], [lo - dx, la + dy], [lo + dx, la - dy]);
    }
    const pad = Math.min(w, mh) * 0.08;
    const proj = d3.geoNaturalEarth1().fitExtent([[pad, pad], [w - pad, mh - pad]], { type: "MultiPoint", coordinates: focus });
    const world = d3.geoNaturalEarth1().fitExtent([[pad, pad], [w - pad, mh - pad]], { type: "Sphere" });
    const path = d3.geoPath(proj);
    const k0 = Math.min(1, world.scale() / proj.scale());
    const cam = document.createElementNS(NS, "g"); svg.appendChild(cam);
    const add = (tag, attrs, parent = cam) => { const e = document.createElementNS(NS, tag); for (const a in attrs) e.setAttribute(a, attrs[a]); parent.appendChild(e); return e; };
    add("path", { d: path({ type: "Sphere" }), fill: "rgba(10,32,38,.55)", stroke: "rgba(140,220,210,.18)", "vector-effect": "non-scaling-stroke" });
    add("path", { d: path(d3.geoGraticule10()), fill: "none", stroke: "rgba(140,220,210,.07)", "stroke-width": 1, "vector-effect": "non-scaling-stroke" });
    const hiNames = new Set(places.flatMap((p) => p.countries));
    for (const c of S.world) {
      add("path", { d: path(c.geo), fill: "#16343b", stroke: "#2b5560", "stroke-width": 0.8, "vector-effect": "non-scaling-stroke" });
    }
    const hiG = places.map((p) => {
      const gg = add("g", {});
      gg.style.filter = `drop-shadow(0 0 ${px(14)}px ${rgba(d.color, 0.8)})`;
      for (const c of S.world) if (p.countries.includes(c.name)) {
        // light up the part of the country the story is about (not, say, Alaska for a story about Washington)
        const near = { type: "MultiPolygon", coordinates: c.geo.coordinates.filter((poly) => { const [lo, la] = d3.geoCentroid({ type: "Polygon", coordinates: poly }); return Math.abs(lo - p.pin[0]) < 35 && Math.abs(la - p.pin[1]) < 30 || c.geo.coordinates.length === 1; }) };
        add("path", { d: path(near.coordinates.length ? near : c.geo), fill: d.color, stroke: "#ffffff", "stroke-opacity": 0.6, "stroke-width": 1, "vector-effect": "non-scaling-stroke" }, gg);
      }
      return gg;
    });
    let arc = null, arcLen = 0, head = null, stamp = null;
    const from = places.find((p) => p.name === g.from), to = places.find((p) => p.name === g.to);
    if (from && to) {
      // a broadcast-style arc between the two pins, lifted by how far apart they are
      const a = proj(from.pin), b = proj(to.pin), dist = Math.hypot(b[0] - a[0], b[1] - a[1]);
      const lift = d3.range(0, 1.0001, 1 / 80).map((s) => [lerp(a[0], b[0], s), lerp(a[1], b[1], s) - Math.sin(Math.PI * s) * Math.min(dist * 0.32, mh * 0.42)]);
      arc = add("path", { d: "M" + lift.map((p) => p.join(",")).join("L"), fill: "none", stroke: g.blocked ? "#ffd2d2" : "#ffffff", "stroke-width": px(5), "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" });
      arcLen = arc.getTotalLength();
      arc.setAttribute("stroke-dasharray", `${arcLen} ${arcLen}`);
      S._lift = lift;
      head = add("path", { d: "M0,0", fill: g.blocked ? "#ffd2d2" : "#ffffff" });
      if (g.blocked) {
        const m = lift[Math.floor(lift.length / 2)];
        stamp = add("g", {});
        add("circle", { cx: 0, cy: 0, r: px(34), fill: "#e23636", stroke: "#fff", "stroke-width": px(4), "vector-effect": "non-scaling-stroke" }, stamp);
        add("path", { d: `M${-px(15)},${-px(15)}L${px(15)},${px(15)}M${-px(15)},${px(15)}L${px(15)},${-px(15)}`, stroke: "#fff", "stroke-width": px(7), "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" }, stamp);
        stamp._m = m;
      }
      arc._lift = lift;
    }
    const pins = places.map((p) => {
      const [x, y] = proj(p.pin);
      const ring = add("circle", { cx: x, cy: y, r: px(12), fill: "none", stroke: "#fff", "stroke-width": px(3), "vector-effect": "non-scaling-stroke" });
      const dot = add("circle", { cx: x, cy: y, r: px(10), fill: "#fff", stroke: "#061316", "stroke-width": px(3), "vector-effect": "non-scaling-stroke" });
      const lab = el("div", "pinlab", box, esc(p.label.toUpperCase())); lab.style.borderBottom = `${px(4)}px solid ${d.color}`;
      return { x, y, ring, dot, lab, p };
    });
    const s2 = d.start + d.shot2;
    const fly0 = s2, fly = 1.8;
    const cx = w / 2, cy = mh / 2;
    const c0 = [world.translate()[0] + (cx - proj.translate()[0]) * (world.scale() / proj.scale()), world.translate()[1] + (cy - proj.translate()[1]) * (world.scale() / proj.scale())];
    return (t, lt) => {
      if (cap) show(cap, K(t, s2 + 0.1, 0.4), 0, (1 - K(t, s2 + 0.1, 0.5)) * -px(30));
      const z = K(t, fly0, fly, easeIO);
      const k = Math.exp(lerp(Math.log(k0), 0, z)) * (1 + 0.03 * clamp((t - fly0 - fly) / 8));
      const P = [lerp(c0[0], cx, z), lerp(c0[1], cy, z)];
      const tx = P[0] - k * cx, ty = P[1] - k * cy;
      cam.setAttribute("transform", `translate(${tx},${ty}) scale(${k})`);
      const scr = (x, y) => [tx + k * x, ty + k * y];
      places.forEach((p, i) => {
        const tc = Math.min(at(p.cue, fly0 + fly * 0.7 + i * 0.5), fly0 + fly + 0.8 + i * 0.8);
        const kc = K(t, Math.max(tc, fly0 + fly * 0.6), 0.5);
        hiG[i].style.opacity = kc;
        const pin = pins[i];
        const kp = K(t, Math.max(tc, fly0 + fly * 0.6) + 0.15, 0.4, back);
        pin.dot.setAttribute("r", Math.max(0, px(10) * kp / k));
        pin.dot.setAttribute("stroke-width", px(3) / k);
        const ph = ((((t - tc) * 0.8) % 1) + 1) % 1;
        pin.ring.setAttribute("r", (px(12) + px(40) * ph) / k);
        pin.ring.setAttribute("stroke-opacity", kp > 0.5 ? (1 - ph) * 0.9 : 0);
        const [sx, sy] = scr(pin.x, pin.y);
        css(pin.lab, { left: sx + "px", top: (capH + sy + px(22)) + "px" });
        show(pin.lab, K(t, Math.max(tc, fly0 + fly * 0.6) + 0.3, 0.4), 0);
        pin.lab.style.transform = "translate(-50%,0)";
      });
      if (arc) {
        const ta = Math.max(at(g.arrow_cue, fly0 + fly + 0.6), fly0 + fly * 0.9);
        const ka = K(t, ta, 1.1, easeIO);
        arc.setAttribute("stroke-dashoffset", arcLen * (1 - ka));
        arc.setAttribute("stroke-width", px(5));
        arc.style.opacity = ka > 0 ? 1 : 0;
        const L = arc._lift, n = L.length - 1, idx = Math.max(1, Math.round(n * ka));
        const [x2, y2] = L[idx], [x1, y1] = L[idx - 1];
        const ang = Math.atan2(y2 - y1, x2 - x1), sz = px(22) / k;
        head.setAttribute("d", ka > 0.02 ? `M${x2 + Math.cos(ang) * sz},${y2 + Math.sin(ang) * sz}L${x2 + Math.cos(ang + 2.5) * sz},${y2 + Math.sin(ang + 2.5) * sz}L${x2 + Math.cos(ang - 2.5) * sz},${y2 + Math.sin(ang - 2.5) * sz}Z` : "M0,0");
        if (stamp) {
          const ks = K(t, ta + 1.2, 0.45, back);
          const [mx, my] = stamp._m;
          stamp.setAttribute("transform", `translate(${mx},${my}) scale(${ks / k})`);
          stamp.style.opacity = ks > 0.01 ? 1 : 0;
          if (ks > 0.5) arc.setAttribute("stroke-dasharray", `${px(14) / k} ${px(12) / k}`);
          else arc.setAttribute("stroke-dasharray", `${arcLen} ${arcLen}`);
        }
      }
    };
  }

  // the number that carries the story, counting up as the anchor says it, with its split
  function gNumber(g, box, w, h, d) {
    const s2 = d.start + d.shot2;
    const big = el("div", "abs num", box); const fs = V ? px(230) : Math.min(px(230), h * 0.62);
    css(big, { fontSize: fs + "px", left: 0, top: (V ? px(20) : px(10)) + "px", color: "#f4f7f6" });
    const ul = el("div", "abs", box); css(ul, { height: px(12) + "px", background: d.color, left: 0, transformOrigin: "0 50%" });
    const capT = el("div", "abs", box, esc(g.caption)); css(capT, { fontWeight: 640, fontSize: px(V ? 50 : 44) + "px", lineHeight: 1.18 });
    const parts = (g.parts || []).map((p, i) => ({ lab: p[0], raw: p[1], v: g.parts_v[i], cue: (g.part_cues || [])[i] }));
    const pbar = el("div", "abs", box);
    const segs = parts.map((p, i) => { const s = el("div", "abs", pbar); s.style.background = i === 0 ? d.color : rgba(d.color, 0.55 - i * 0.15); return s; });
    const plabs = parts.map((p) => { const l = el("div", "abs", box, `<div style="font-weight:840;font-size:${px(V ? 46 : 42)}px">${esc(p.raw)}</div><div style="font-weight:600;color:#9fb3b0;font-size:${px(V ? 28 : 26)}px;margin-top:${px(4)}px">${esc(p.lab)}</div>`); return l; });
    const n = g.num;
    big.textContent = fmtNum(n.pre, n.x, n.dec, n.suf);
    let bw = 0;
    return (t, lt) => {
      if (!bw) bw = big.offsetWidth;
      const tc = Math.max(at(g.cue, s2 + 0.3), s2 + 0.2);
      const kc = K(t, Math.min(tc, s2 + 1.2), 1.5);
      big.textContent = kc >= 0.999 ? g.value : fmtNum(n.pre, n.x * kc, n.dec, n.suf);
      show(big, K(t, s2 + 0.05, 0.4), (1 - K(t, s2 + 0.05, 0.5)) * px(40));
      const asc = big.offsetHeight;
      css(ul, { top: (big.offsetTop + asc + px(6)) + "px", width: bw + "px", transform: `scaleX(${K(t, s2 + 0.4, 0.9, easeIO)})` });
      const cx = V ? 0 : Math.max(bw + px(90), w * 0.46), cy = V ? big.offsetTop + asc + px(70) : px(26);
      css(capT, { left: cx + "px", top: cy + "px", width: (V ? w : w - cx) + "px" });
      show(capT, K(t, s2 + 0.6, 0.5), (1 - K(t, s2 + 0.6, 0.5)) * px(20));
      if (parts.length) {
        const tot = parts.reduce((a, p) => a + p.v, 0) || 1;
        const by = cy + capT.offsetHeight + px(V ? 50 : 40), bwid = V ? w : w - cx;
        css(pbar, { left: cx + "px", top: by + "px", width: bwid + "px", height: px(V ? 40 : 34) + "px" });
        let x = 0;
        parts.forEach((p, i) => {
          const ts = Math.max(at(p.cue, s2 + 1.4 + i * 0.5), s2 + 1.0);
          const ks = K(t, ts, 0.7, easeIO);
          const sw = bwid * p.v / tot;
          css(segs[i], { left: x + "px", top: 0, height: "100%", width: Math.max(0, sw * ks - px(4)) + "px" });
          css(plabs[i], { left: (cx + x) + "px", top: (by + px(V ? 54 : 48)) + "px" });
          show(plabs[i], K(t, ts + 0.3, 0.4), (1 - K(t, ts + 0.3, 0.4)) * px(14));
          x += sw;
        });
      }
    };
  }

  // a percentage change: the old level, then the new one sliding to it
  function gChange(g, box, w, h, d) {
    const s2 = d.start + d.shot2;
    const cap = capEl(box, g.caption, d.color); const top = cap ? px(70) : 0;
    const rows = [[g.before, 1, "#5b7a80"], [g.after, 1 + g.pct / 100, d.color]];
    const bwmax = V ? w : w * 0.6;
    const els = rows.map(([lab, v, col], i) => {
      const l = el("div", "abs", box, esc(lab)); css(l, { fontWeight: i ? 780 : 620, color: i ? "#f4f7f6" : "#a9bcb9", fontSize: px(V ? 40 : 34) + "px", left: 0 });
      const b = el("div", "abs", box); css(b, { background: col, left: 0, height: px(V ? 80 : 70) + "px" });
      return { l, b, v };
    });
    const badge = el("div", "abs num", box); css(badge, { fontSize: px(V ? 190 : 170) + "px", color: "#f4f7f6" });
    const arrow = el("div", "abs", box, g.pct < 0 ? "&#9660;" : "&#9650;"); css(arrow, { fontSize: px(70) + "px", color: d.color });
    const mx = Math.max(1, 1 + g.pct / 100);
    return (t, lt) => {
      if (cap) show(cap, K(t, s2 + 0.1, 0.4), 0, (1 - K(t, s2 + 0.1, 0.5)) * -px(30));
      const tc = Math.max(at(g.cue, s2 + 1.0), s2 + 0.8);
      let y = top + px(20);
      els.forEach(({ l, b, v }, i) => {
        css(l, { top: y + "px" }); show(l, K(t, s2 + 0.2 + i * 0.3, 0.4));
        y += l.offsetHeight + px(10);
        const grow = K(t, s2 + 0.3 + i * 0.3, 0.7, easeIO);
        const shrink = i ? K(t, tc, 1.0, easeIO) : 0;
        const ww = bwmax * (i ? lerp(1, v, shrink) : v) / mx * grow;
        css(b, { top: y + "px", width: ww + "px" });
        y += px(V ? 80 : 70) + px(30);
      });
      const kb = K(t, tc, 1.0);
      badge.textContent = (g.pct < 0 ? "−" : "+") + Math.round(Math.abs(g.pct) * kb * 10) / 10 + "%";
      if (V) css(badge, { left: 0, top: (y + px(30)) + "px" }); else css(badge, { left: (bwmax + px(80)) + "px", top: (top + px(10)) + "px" });
      show(badge, K(t, tc, 0.4), 0, 0, 0.9 + 0.1 * K(t, tc, 0.5, back));
      css(arrow, V ? { left: (badge.offsetWidth + px(20)) + "px", top: (y + px(80)) + "px" } : { left: (bwmax + px(80) + badge.offsetWidth + px(20)) + "px", top: (top + px(60)) + "px" });
      show(arrow, K(t, tc + 0.5, 0.4), (1 - K(t, tc + 0.5, 0.4)) * (g.pct < 0 ? -px(20) : px(20)));
    };
  }

  function gBars(g, box, w, h, d) {
    const s2 = d.start + d.shot2;
    const cap = capEl(box, g.caption, d.color); const top = cap ? px(76) : 0;
    const items = g.items.map((it, i) => ({ lab: it[0], raw: it[1], v: g.values[i], cue: (g.cues || [])[i] }));
    const mx = Math.max(...items.map((x) => x.v)) || 1;
    const rh = Math.min((h - top) / items.length, px(V ? 170 : 130));
    const rows = items.map((it, i) => {
      const l = el("div", "abs", box, esc(it.lab)); css(l, { fontWeight: 700, color: "#cfdcda", fontSize: px(V ? 36 : 32) + "px", left: 0, top: (top + i * rh) + "px" });
      const b = el("div", "abs", box); css(b, { background: it.v === mx ? d.color : "#5b7a80", left: 0, top: (top + i * rh + px(V ? 52 : 46)) + "px", height: px(V ? 56 : 50) + "px" });
      const v = el("div", "abs num", box, esc(it.raw)); css(v, { fontSize: px(V ? 56 : 50) + "px", top: (top + i * rh + px(V ? 50 : 44)) + "px" });
      return { l, b, v, it };
    });
    return (t) => {
      if (cap) show(cap, K(t, s2 + 0.1, 0.4), 0, (1 - K(t, s2 + 0.1, 0.5)) * -px(30));
      rows.forEach(({ l, b, v, it }, i) => {
        const tc = Math.max(at(it.cue, s2 + 0.5 + i * 0.6), s2 + 0.3 + i * 0.2);
        const k = K(t, tc, 0.9, easeIO);
        show(l, K(t, tc - 0.2, 0.4));
        const ww = (w - px(260)) * it.v / mx * k;
        b.style.width = ww + "px";
        css(v, { left: (ww + px(20)) + "px" }); show(v, K(t, tc + 0.3, 0.4));
      });
    };
  }

  function gList(g, box, w, h, d) {
    const s2 = d.start + d.shot2;
    const cap = capEl(box, g.caption, d.color); const top = cap ? px(76) : 0;
    const n = g.items.length;
    const cols = V ? (n > 4 ? 2 : 1) : (n > 4 ? 3 : 2), rows = Math.ceil(n / cols), gap = px(20);
    const tw = (w - gap * (cols - 1)) / cols, th = Math.min((h - top - gap * (rows - 1)) / rows, px(V ? 150 : 140));
    const tiles = g.items.map((it, i) => {
      const tl = el("div", "tile", box); tl.style.borderLeftColor = d.color;
      css(tl, { left: ((i % cols) * (tw + gap)) + "px", top: (top + Math.floor(i / cols) * (th + gap)) + "px", width: tw + "px", height: th + "px", fontSize: px(V ? 46 : 44) + "px" });
      el("span", "", tl, esc(it));
      const ix = el("span", "ix", tl, String(i + 1).padStart(2, "0")); ix.style.color = d.color;
      return tl;
    });
    const times = ordered((g.cues || []).map((c) => (c != null && c > s2 + 0.3 ? c : null)), s2 + 0.5, 0.45, s2 + 0.9);
    return (t) => {
      if (cap) show(cap, K(t, s2 + 0.1, 0.4), 0, (1 - K(t, s2 + 0.1, 0.5)) * -px(30));
      const latest = times.reduce((m, x, i) => (x <= t ? i : m), -1);
      tiles.forEach((tl, i) => {
        const k = K(t, times[i], 0.45, back);
        tl.style.opacity = clamp(k * 1.4); tl.style.visibility = k > 0 ? "visible" : "hidden";
        tl.style.transform = `translateY(${(1 - k) * px(30)}px) scale(${i === latest ? 1.02 : 1})`;
        tl.style.background = i === latest ? rgba(d.color, 0.2) : "rgba(6,19,22,.82)";
      });
    };
  }

  function gSteps(g, box, w, h, d) {
    const s2 = d.start + d.shot2;
    const cap = capEl(box, g.caption, d.color); const top = cap ? px(76) : 0;
    const n = g.items.length, gap = px(V ? 26 : 64);
    const line = el("div", "abs", box); css(line, { background: d.color, transformOrigin: V ? "50% 0" : "0 50%" });
    const cards = g.items.map((it, i) => {
      const c = el("div", "step", box); c.style.borderTopColor = d.color;
      const sn = el("div", "sn", c, String(i + 1)); sn.style.color = d.color;
      el("div", "st", c, esc(it));
      if (V) { const ch = (h - top - gap * (n - 1)) / n; css(c, { left: 0, right: 0, top: (top + i * (ch + gap)) + "px", height: ch + "px", display: "flex", alignItems: "center", gap: px(30) + "px" }); c.lastChild.style.marginTop = 0; }
      else { const cw = (w - gap * (n - 1)) / n; css(c, { left: (i * (cw + gap)) + "px", top: top + "px", width: cw + "px", height: Math.min(h - top, px(300)) + "px" }); }
      return c;
    });
    if (V) css(line, { left: px(50) + "px", width: px(6) + "px", top: top + "px", height: (h - top) + "px" });
    else css(line, { left: 0, right: 0, height: px(6) + "px", top: (top + Math.min(h - top, px(300)) / 2) + "px" });
    const times = ordered((g.cues || []).map((c) => (c != null && c > s2 + 0.3 ? c : null)), s2 + 0.5, 1.2, s2 + 0.9);
    return (t) => {
      if (cap) show(cap, K(t, s2 + 0.1, 0.4), 0, (1 - K(t, s2 + 0.1, 0.5)) * -px(30));
      const last = times[times.length - 1];
      line.style.transform = V ? `scaleY(${K(t, times[0], last - times[0] + 0.6, easeIO)})` : `scaleX(${K(t, times[0], last - times[0] + 0.6, easeIO)})`;
      line.style.opacity = 0.5;
      cards.forEach((c, i) => { const k = K(t, times[i], 0.5); show(c, k, V ? 0 : (1 - k) * px(40), V ? (1 - k) * px(60) : 0); });
    };
  }

  function gQuote(g, box, w, h, d) {
    const s2 = d.start + d.shot2;
    const mark = el("div", "abs", box, "“"); css(mark, { fontWeight: 900, fontSize: px(V ? 260 : 240) + "px", lineHeight: 1, color: d.color, left: 0, top: -px(30) + "px" });
    const q = el("div", "abs quote", box); css(q, { left: px(V ? 0 : 150) + "px", right: 0, top: px(V ? 180 : 20) + "px", fontSize: px(V ? 56 : 52) + "px" });
    const words = g.text.trim().replace(/^["“]|["”]$/g, "").split(/\s+/).map((x) => el("span", "qw", q, esc(x) + " "));
    const by = el("div", "abs", box, `— ${esc(g.by)}${g.role ? ", " + esc(g.role) : ""}`); css(by, { left: px(V ? 0 : 150) + "px", fontWeight: 780, color: d.color, fontSize: px(V ? 38 : 34) + "px" });
    const dur = Math.min(Math.max(words.length / 3.2, 1.5), Math.max(1.5, d.dur - d.shot2 - 1.5));
    return (t) => {
      show(mark, K(t, s2, 0.4), 0, 0, 0.8 + 0.2 * K(t, s2, 0.5, back));
      const kr = K(t, s2 + 0.3, dur, (x) => x);
      words.forEach((wd, i) => { wd.style.opacity = 0.18 + 0.82 * clamp(kr * words.length - i); });
      css(by, { top: (q.offsetTop + q.offsetHeight + px(26)) + "px" }); show(by, K(t, s2 + 0.6, 0.5));
    };
  }

  // ------------------------------------------------------------ captions (vertical) and overlays
  function buildCaptions() {
    S.caps = el("div", "abs", root); S.caps.id = "caps";
    S.capBox = el("div", "box", S.caps);
    S.capOn = V && TL.narrated && TL.captions.length;
    S.caps.style.top = px(1560) + "px";
    S.capIdx = -1;
  }
  function updateCaptions(t) {
    if (!S.capOn) { S.caps.style.display = "none"; return; }
    const c = TL.captions.find((x) => t >= x.t0 - 0.08 && t <= x.t1 + 0.3);
    if (!c) { S.caps.style.visibility = "hidden"; return; }
    S.caps.style.visibility = "visible";
    const idx = TL.captions.indexOf(c);
    if (idx !== S.capIdx) { S.capIdx = idx; S.capBox.innerHTML = ""; S.capWords = c.words.map((w) => el("span", "cw", S.capBox, esc(w.w))); }
    c.words.forEach((w, i) => {
      const e = S.capWords[i];
      const said = t >= w.t0, now = said && t < w.t1 + 0.05;
      e.style.color = now ? TL.accent : "#ffffff"; e.style.opacity = said ? 1 : 0.45;
      e.style.transform = "none";
    });
    const k = K(t, c.t0 - 0.08, 0.15);
    S.capBox.style.transform = `translateY(${(1 - k) * px(16)}px)`;
  }
  function buildOverlays() {
    S.wipe = el("div", "layer", root); S.wipe.id = "wipe";
    root.insertBefore(S.wipe, S.bug);  // under the brand bug, progress and ticker, which stay on screen through the cut
    S.slabs = [0, 1].map(() => el("div", "slab", S.wipe));
    S.fade = el("div", "layer", root); S.fade.id = "fade";
  }
  function updateOverlays(t, cur) {
    // a branded wipe across each cut: the next scene's colour, then a dark slab, sweeping left to right
    let shown = false;
    for (let i = 1; i < TL.scenes.length; i++) {
      const b = TL.scenes[i].start, dt = t - b;
      if (dt > -0.4 && dt < 0.4) {
        const col = TL.scenes[i].color || TL.accent;
        const p = (dt + 0.4) / 0.8;  // 0..1 across the cut
        S.slabs.forEach((s, j) => {
          const q = clamp(p * 1.15 - j * 0.12);
          const x = lerp(-0.85, 1.15, easeIO(q)) * W;
          css(s, { left: x + "px", width: (W * 0.75) + "px", background: j === 0 ? col : "#061316", transform: "skewX(-14deg)", display: "block" });
        });
        shown = true;
      }
    }
    if (!shown) S.slabs.forEach((s) => (s.style.display = "none"));
    const end = TL.total;
    S.fade.style.opacity = Math.max(1 - K(t, 0, 0.35, (x) => x), K(t, end - 0.6, 0.55, (x) => x));
  }

  // ------------------------------------------------------------ the world map data
  function prepWorld(world) {
    if (!world || typeof d3 === "undefined") return [];
    return world.countries.map((c) => {
      const polys = c.rings.map((r) => {
        let ring = r.slice();
        if (ring[0][0] !== ring[ring.length - 1][0] || ring[0][1] !== ring[ring.length - 1][1]) ring.push(ring[0]);
        let poly = { type: "Polygon", coordinates: [ring] };
        if (d3.geoArea(poly) > 2 * Math.PI) poly = { type: "Polygon", coordinates: [ring.slice().reverse()] };
        return poly.coordinates;
      });
      return { name: c.name, geo: { type: "MultiPolygon", coordinates: polys } };
    });
  }
})();
