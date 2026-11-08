import { makeCompare, tr } from "./common.js";

const select = document.getElementById("colorFrame"), status = document.getElementById("colorStatus");
const container = document.getElementById("colorCmp"), retry = document.getElementById("colorRetry");
const comparison = makeCompare(container);
let frames = [], current = "", revision = 0;
function labels() {
  container.setAttribute("aria-label", tr({ it: "Confronto tra livelli RGB e curva sulla luminanza", en: "Compare RGB levels with a luminance curve" }));
  document.getElementById("colorNatural").alt = tr({ it: "Resa sperimentale sulla luminanza", en: "Experimental luminance rendering" });
  document.getElementById("colorLegacy").alt = tr({ it: "Resa del motore di riferimento", en: "Reference engine rendering" });
}
async function show(id, updateUrl = true) {
  const frame = frames.find((f) => f.id === id) || frames[0];
  if (!frame) return;
  current = frame.id; select.value = current;
  const request = ++revision;
  container.setAttribute("aria-busy", "true");
  status.textContent = tr({ it: "Caricamento del fotogramma…", en: "Loading frame…" });
  retry.hidden = true;
  if (updateUrl) { const url = new URL(location.href); url.searchParams.set("frame", current); history.replaceState(null, "", url); }
  container.style.aspectRatio = `${frame.width} / ${frame.height}`;
  try {
    await Promise.all([["colorNatural", "natural"], ["colorLegacy", "legacy"]].map(async ([id, mode]) => {
      const el = document.getElementById(id); el.width = frame.width; el.height = frame.height;
      el.src = `img/color/${frame[mode]}`;
      await el.decode();
    }));
    if (request !== revision) return;
    comparison.set(50);
    status.textContent = `${frame.film} · ${frame.id} · ${frame.width} × ${frame.height} px`;
  } catch {
    if (request !== revision) return;
    status.textContent = tr({ it: "Immagine non caricata. Riprova o scegli un altro fotogramma.", en: "Image could not load. Retry or choose another frame." });
    retry.hidden = false;
  } finally { if (request === revision) container.setAttribute("aria-busy", "false"); }
}
async function init() {
  try {
    retry.hidden = true;
    const response = await fetch("data/color-comparison.json");
    if (!response.ok) throw new Error("comparison unavailable");
    frames = (await response.json()).frames;
    if (!frames.length) throw new Error("no comparison frames");
    select.replaceChildren(...frames.map((f) => new Option(`${f.film} · ${f.id}`, f.id)));
    select.disabled = false;
    await show(new URL(location.href).searchParams.get("frame") || "19941218C-04-tokyo", false);
  } catch {
    container.setAttribute("aria-busy", "false");
    status.textContent = tr({ it: "Confronti non disponibili. Riprova tra poco.", en: "Comparisons unavailable. Please retry shortly." });
    retry.hidden = false;
  }
}
select.addEventListener("change", () => show(select.value));
retry.addEventListener("click", () => frames.length ? show(current) : init());
window.addEventListener("popstate", () => show(new URL(location.href).searchParams.get("frame"), false));
document.addEventListener("langchange", () => { labels(); if (frames.length) show(current, false); });
labels(); init();
