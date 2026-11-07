import { makeCompare, enableZoom } from "./common.js";

const hero = document.getElementById("heroCmp");
const cmp = makeCompare(hero);
// piccola dimostrazione all'apertura: il cursore scorre e torna, finché non lo tocchi
if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
  let t0 = null, stop = false;
  const off = () => (stop = true);
  hero.addEventListener("pointerdown", off, { once: true });
  hero.addEventListener("keydown", off, { once: true });
  const tick = (t) => {
    if (stop) return;
    t0 ??= t;
    const s = (t - t0) / 1000;
    if (s > 3.2) return cmp.set(50);
    cmp.set(50 + 32 * Math.sin((s / 3.2) * Math.PI * 2));
    requestAnimationFrame(tick);
  };
  setTimeout(() => requestAnimationFrame(tick), 600);
}
enableZoom();
