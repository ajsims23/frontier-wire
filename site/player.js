// Frontier Wire video player: any element with data-video="<YouTube id>" opens a pop-up player.
// Elements with data-mp4="<our own video file>" (the daily recap) play in the same pop-up.
// On desktop, hovering a video card plays a silent preview in place.
(function () {
  "use strict";
  const ID = /^[A-Za-z0-9_-]{11}$/;
  const embed = (id, extra) => `https://www.youtube-nocookie.com/embed/${id}?rel=0&modestbranding=1&playsinline=1${extra}`;
  let dlg = null, opener = null;

  function build() {
    dlg = document.createElement("dialog");
    dlg.className = "player";
    dlg.setAttribute("aria-label", "Video player");
    dlg.innerHTML = `<div class="player-box"><div class="player-head"><p class="player-title"></p>
      <button class="player-x" type="button" aria-label="Close video"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
      <div class="player-frame"></div></div>`;
    document.body.appendChild(dlg);
    dlg.querySelector(".player-x").addEventListener("click", () => dlg.close());
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener("close", () => { dlg.querySelector(".player-frame").innerHTML = ""; document.documentElement.classList.remove("no-scroll"); if (opener) opener.focus(); });
  }

  window.FWPlay = function (id, title, from) {
    if (!ID.test(id || "")) return;
    if (!dlg) build();
    opener = from || null;
    dlg.querySelector(".player-title").textContent = title || "";
    dlg.querySelector(".player-frame").innerHTML = `<iframe src="${embed(id, "&autoplay=1")}" title="${(title || "Video").replace(/"/g, "&quot;")}" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>`;
    document.documentElement.classList.add("no-scroll");
    dlg.showModal();
  };

  // our own videos (same-site .mp4 files, or the archive on GitHub Releases)
  const MP4 = /^(?:[A-Za-z0-9_./-]+|https:\/\/github\.com\/[A-Za-z0-9_.\/-]+)\.mp4$/;
  const JPG = /^(?:[A-Za-z0-9_./-]+|https:\/\/github\.com\/[A-Za-z0-9_.\/-]+)\.jpg$/;
  const esc = (t) => String(t || "").replace(/[&"<>]/g, (c) => ({ "&": "&amp;", '"': "&quot;", "<": "&lt;", ">": "&gt;" })[c]);
  window.FWPlayFile = function (src, title, poster, from) {
    if (!MP4.test(src || "")) return;
    if (!dlg) build();
    opener = from || null;
    dlg.querySelector(".player-title").textContent = title || "";
    dlg.querySelector(".player-frame").innerHTML = `<video src="${esc(src)}"${JPG.test(poster || "") ? ` poster="${esc(poster)}"` : ""} controls autoplay playsinline></video>`;
    document.documentElement.classList.add("no-scroll");
    dlg.showModal();
  };

  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-video],[data-mp4]");
    if (!el) return;
    e.preventDefault();
    if (el.dataset.mp4) window.FWPlayFile(el.dataset.mp4, el.dataset.title, el.dataset.poster, el);
    else window.FWPlay(el.dataset.video, el.dataset.title, el);
  });

  // silent hover preview (desktop pointers only; skipped for reduced motion)
  const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!canHover) return;
  let timer = null;
  document.addEventListener("mouseover", (e) => {
    const card = e.target.closest(".vcard[data-video]");
    if (!card || card.querySelector(".vprev")) return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      const thumb = card.querySelector(".vthumb");
      if (!thumb || !card.matches(":hover")) return;
      thumb.insertAdjacentHTML("beforeend", `<iframe class="vprev" src="${embed(card.dataset.video, "&autoplay=1&mute=1&controls=0&loop=1&playlist=" + card.dataset.video)}" title="" tabindex="-1" aria-hidden="true" allow="autoplay"></iframe>`);
    }, 700);
  });
  document.addEventListener("mouseout", (e) => {
    const card = e.target.closest(".vcard[data-video]");
    if (!card || card.contains(e.relatedTarget)) return;
    clearTimeout(timer);
    const f = card.querySelector(".vprev");
    if (f) f.remove();
  });
})();
