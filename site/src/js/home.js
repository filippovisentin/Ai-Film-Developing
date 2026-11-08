import { makeCompare, enableZoom, tr } from "./common.js";

const hero = document.getElementById("heroCmp"), cmp = makeCompare(hero);
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
const toggle = document.getElementById("motionToggle"), replay = document.getElementById("replay");
let manuallyPaused = false, animation = 0;
const motionEnabled = () => !reduced.matches && !manuallyPaused;
const stop = () => { cancelAnimationFrame(animation); animation = 0; replay.disabled = !motionEnabled(); };
function play() {
  stop();
  if (!motionEnabled()) { cmp.set(50); return; }
  let started;
  replay.disabled = true;
  const frame = (now) => {
    if (!motionEnabled() || document.hidden) { stop(); return; }
    started ??= now;
    const t = Math.min((now - started) / 2600, 1);
    cmp.set(t < .65 ? 96 * (1 - (1 - t / .65) ** 3) : 96 - 46 * (1 - (1 - (t - .65) / .35) ** 3));
    if (t < 1) animation = requestAnimationFrame(frame); else stop();
  };
  animation = requestAnimationFrame(frame);
}
function applyMotion() {
  const enabled = motionEnabled();
  document.body.classList.toggle("motion-off", !enabled);
  toggle.setAttribute("aria-pressed", String(!enabled));
  document.getElementById("motionLabel").textContent = tr(enabled ? { it: "Animazioni attive", en: "Motion on" } : { it: "Animazioni ferme", en: "Motion off" });
  toggle.disabled = reduced.matches;
  if (!enabled) {
    stop();
    document.querySelectorAll(".reveal").forEach((el) => el.classList.add("visible"));
    document.querySelectorAll(".word").forEach((el) => el.classList.add("lit"));
  }
  replay.disabled = !enabled || !!animation;
}
if ("IntersectionObserver" in window) {
  document.querySelectorAll("[data-word-reveal]").forEach((el) => {
    const text = el.textContent.trim(); el.setAttribute("aria-label", text);
    el.replaceChildren(...text.split(/\s+/).flatMap((word, i) => {
      const span = document.createElement("span"); span.className = "word"; span.textContent = word; span.setAttribute("aria-hidden", "true");
      span.style.setProperty("--word-delay", `${(i % 7) * 45}ms`);
      return i ? [document.createTextNode(" "), span] : [span];
    }));
  });
  const revealObserver = new IntersectionObserver((entries) => entries.forEach(({ target, isIntersecting }) => {
    if (isIntersecting) { target.classList.add("visible"); revealObserver.unobserve(target); }
  }), { threshold: .08 });
  const wordObserver = new IntersectionObserver((entries) => entries.forEach(({ target, isIntersecting }) => {
    if (isIntersecting) { target.classList.add("lit"); wordObserver.unobserve(target); }
  }), { rootMargin: "0px 0px -18% 0px", threshold: .5 });
  document.querySelectorAll(".reveal").forEach((el) => revealObserver.observe(el));
  document.querySelectorAll(".word").forEach((el) => wordObserver.observe(el));
  document.body.classList.add("motion-ready");
}
hero.addEventListener("pointerdown", stop); hero.addEventListener("keydown", stop);
replay.addEventListener("click", play);
toggle.addEventListener("click", () => { manuallyPaused = !manuallyPaused; applyMotion(); });
reduced.addEventListener("change", applyMotion);
document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
document.addEventListener("langchange", applyMotion);
const mount = document.querySelector(".photo-mount");
if (matchMedia("(hover: hover) and (pointer: fine)").matches) {
  let pending = 0;
  mount.addEventListener("pointermove", (e) => {
    if (!motionEnabled() || e.buttons) return;
    const box = mount.getBoundingClientRect(), x = (e.clientX - box.left) / box.width - .5, y = (e.clientY - box.top) / box.height - .5;
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(() => { if (motionEnabled()) mount.style.transform = `rotate(${x * 2 - 2}deg) translate(${x * 4}px,${y * 4}px)`; });
  });
  mount.addEventListener("pointerleave", () => { cancelAnimationFrame(pending); mount.style.removeProperty("transform"); });
}
applyMotion();
if (motionEnabled()) { const im = hero.querySelector("img"); if (im.complete) play(); else im.addEventListener("load", play, { once: true }); }
enableZoom();
