// Frontier Wire podcast player: an AI podcast picked by the newsroom agent plays silently (as browsers require
// until the reader taps for sound) in a mini player in the corner, and keeps playing while you read. On phones it
// waits behind a small "AI podcast" button. The reader can expand it to the big player. Moving to another page picks up where it left off, in the corner.
// It only stops if the reader closes it; then a small "AI podcast" button brings it back.
(function () {
  "use strict";
  const ID = /^[A-Za-z0-9_-]{11}$/;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k, s) { try { return (s ? sessionStorage : localStorage).getItem(k); } catch (e) { return null; } },
    set(k, v, s) { try { (s ? sessionStorage : localStorage).setItem(k, v); } catch (e) { /* private mode */ } },
  };
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ICON = {
    muted: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M23 9l-6 6M17 9l6 6"/></svg>',
    sound: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/></svg>',
    next: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 4l10 8-10 8V4zM19 5v14"/></svg>',
    min: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7"/></svg>',
    max: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>',
    close: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    play: '<svg width="14" height="14" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1l7 4-7 4z" fill="currentColor"/></svg>',
  };

  let list = [], idx = 0, el = null, launcher = null, muted = true, timer = null, pos = 0;
  const SAVE = "fw-pod-state";

  function src(id, withSound, start) {
    return `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=${withSound ? 0 : 1}&rel=0&modestbranding=1&playsinline=1&enablejsapi=1${start ? `&start=${Math.floor(start)}` : ""}&origin=${encodeURIComponent(location.origin)}`;
  }
  // remember which episode and where we are, so the next page continues it
  function save(extra) {
    if (!list[idx]) return;
    store.set(SAVE, JSON.stringify({ id: list[idx].id, t: pos, muted, ...extra }), true);
  }
  window.addEventListener("message", (e) => {
    if (!/youtube(-nocookie)?\.com$/.test(new URL(e.origin || "https://x.invalid").hostname)) return;
    let d; try { d = typeof e.data === "string" ? JSON.parse(e.data) : e.data; } catch (err) { return; }
    if (d && d.info && typeof d.info.currentTime === "number") pos = d.info.currentTime;
  });
  window.addEventListener("pagehide", () => { if (el && el.dataset.state !== "closed") save(); });
  setInterval(() => { if (el && el.dataset.state !== "closed") save(); }, 5000);
  function command(func) {
    const f = el && el.querySelector("iframe");
    if (f && f.contentWindow) f.contentWindow.postMessage(JSON.stringify({ event: "command", func, args: [] }), "*");
  }

  function setMuted(m) {
    muted = m;
    const b = el.querySelector(".pod-sound");
    b.innerHTML = (m ? ICON.muted : ICON.sound) + `<span>${m ? "Tap for sound" : "Sound on"}</span>`;
    b.setAttribute("aria-pressed", String(!m));
    b.setAttribute("aria-label", m ? "Turn sound on" : "Mute");
  }

  function load(i, withSound, start) {
    idx = (i + list.length) % list.length;
    const p = list[idx];
    pos = start || 0;
    el.querySelector(".pod-frame").innerHTML = `<iframe src="${src(p.id, withSound, start)}" title="${esc(p.title)}" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>`;
    const f = el.querySelector("iframe");
    f.addEventListener("load", () => f.contentWindow.postMessage(JSON.stringify({ event: "listening", id: "fw-pod", channel: "widget" }), "*"));
    el.querySelector(".pod-title").textContent = p.title;
    el.querySelector(".pod-guest").textContent = p.guest ? `${p.guest} · ${p.channel}` : p.channel;
    el.querySelector(".pod-next").hidden = list.length < 2;
    setMuted(!withSound);
  }

  // FLIP: animate the same element (so the video keeps playing) between the big pop-up and the mini player.
  function setState(state) {
    if (!el || el.dataset.state === state) return;
    clearTimeout(timer);
    const first = el.getBoundingClientRect();
    el.dataset.state = state;
    const size = el.querySelector(".pod-size");
    size.innerHTML = state === "big" ? ICON.min : ICON.max;
    size.setAttribute("aria-label", state === "big" ? "Minimize player" : "Expand player");
    if (reduced) return;
    const last = el.getBoundingClientRect();
    el.animate([
      { transform: `translate(${first.left - last.left}px, ${first.top - last.top}px) scale(${first.width / last.width}, ${first.height / last.height})`, transformOrigin: "top left" },
      { transform: "none", transformOrigin: "top left" },
    ], { duration: 560, easing: "cubic-bezier(.2, .8, .2, 1)" });
  }

  function build() {
    el = document.createElement("aside");
    el.className = "pod";
    el.setAttribute("aria-label", "AI podcast player");
    el.dataset.state = "closed";
    el.innerHTML = `
      <div class="pod-timer" aria-hidden="true"></div>
      <div class="pod-frame"></div>
      <div class="pod-body">
        <div class="pod-info"><span class="pod-kicker"><span class="pod-live" aria-hidden="true"></span>AI podcast, picked by our agent</span>
          <p class="pod-title"></p><p class="pod-guest"></p></div>
        <div class="pod-ctrl">
          <button class="pod-btn pod-sound" type="button"></button>
          <button class="pod-btn icon pod-next" type="button" aria-label="Next podcast">${ICON.next}</button>
          <button class="pod-btn icon pod-size" type="button" aria-label="Minimize player">${ICON.min}</button>
          <button class="pod-btn icon pod-x" type="button" aria-label="Close player">${ICON.close}</button>
        </div>
      </div>`;
    document.body.appendChild(el);
    el.querySelector(".pod-sound").addEventListener("click", () => {
      if (muted) { command("unMute"); command("playVideo"); setMuted(false); } else { command("mute"); setMuted(true); }
    });
    el.querySelector(".pod-next").addEventListener("click", () => load(idx + 1, !muted));
    el.querySelector(".pod-size").addEventListener("click", () => setState(el.dataset.state === "big" ? "mini" : "big"));
    el.querySelector(".pod-x").addEventListener("click", close);
    el.querySelector(".pod-timer").addEventListener("animationend", () => setState("mini"));
    el.addEventListener("keydown", (e) => { if (e.key === "Escape") setState("mini"); });
    // reading on: shrink out of the way
    const onScroll = () => { if (el.dataset.state === "big" && window.scrollY > 260) setState("mini"); };
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  function open(withSound, state, start) {
    if (!el) build();
    if (launcher) launcher.hidden = true;
    store.set("fw-pod-closed", "", true);
    el.dataset.state = "closed";
    load(idx, withSound, start);
    setState(state || "big");
  }

  function close() {
    command("pauseVideo");
    el.querySelector(".pod-frame").innerHTML = "";
    el.dataset.state = "closed";
    store.set("fw-pod-closed", "1", true);   // stays closed for the rest of this visit
    store.set(SAVE, "", true);
    showLauncher();
  }

  function showLauncher() {
    if (!launcher) {
      launcher = document.createElement("button");
      launcher.type = "button";
      launcher.className = "pod-launch";
      launcher.innerHTML = `<span class="pod-live" aria-hidden="true"></span>${ICON.play}<span>AI podcast</span>`;
      launcher.addEventListener("click", () => open(true)); // a click allows sound straight away
      document.body.appendChild(launcher);
    }
    launcher.hidden = false;
  }

  function start(podcasts) {
    list = (podcasts || []).filter((p) => ID.test(p.id || ""));
    if (!list.length || el || launcher) return;
    if (store.get("fw-pod-closed", true) === "1") { showLauncher(); return; }
    let saved = null;
    try { saved = JSON.parse(store.get(SAVE, true) || "null"); } catch (e) { saved = null; }
    const i = saved ? list.findIndex((p) => p.id === saved.id) : -1;
    if (i >= 0) {
      // continuing from another page: straight into the corner, at the same point
      idx = i;
      open(false, "mini", saved.t);
    } else if (reduced) {
      showLauncher();
    } else if (window.matchMedia("(max-width: 760px)").matches) {
      showLauncher();   // phones: a small button, so the player never covers the story being read
    } else {
      setTimeout(() => open(false, "mini"), 1500);   // desktop: plays quietly in the corner, never over the front page
    }
  }
  window.FWPodcast = start;
  // pages other than the home page load the picks themselves
  const me = document.currentScript;
  if (me && me.dataset.root !== undefined) {
    fetch(me.dataset.root + "data/site.json", { cache: "no-store" }).then((r) => r.json()).then((d) => start(d.podcasts)).catch(() => {});
  }
})();
