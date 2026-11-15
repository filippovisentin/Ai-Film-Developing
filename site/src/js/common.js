// Lingua (IT/EN), cursore di confronto e ingrandimento: comuni a tutte le pagine.
const KEY = "afd-lang";
function store(get, v) {
  try { return get ? localStorage.getItem(KEY) : localStorage.setItem(KEY, v); } catch { return null; }
}
export function lang() { return document.documentElement.dataset.lang || "it"; }
export function setLang(l) {
  document.documentElement.dataset.lang = l;
  document.documentElement.lang = l;
  store(false, l);
  document.querySelectorAll(".langs button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === l)));
  document.querySelectorAll("[data-title-it]").forEach((el) => { document.title = el.dataset[`title${l === "it" ? "It" : "En"}`]; });
  document.querySelectorAll("[data-label-it]").forEach((el) => el.setAttribute("aria-label", el.dataset[l === "it" ? "labelIt" : "labelEn"]));
  document.dispatchEvent(new CustomEvent("langchange", { detail: l }));
}
/** Testo nella lingua attiva: tr({ it: "...", en: "..." }). */
export const tr = (o) => (o && typeof o === "object" ? o[lang()] ?? o.it : o);

setLang(document.documentElement.dataset.lang === "en" ? "en" : "it"); // scelta da lang-boot.js
document.querySelectorAll(".langs button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));


/** Rende trascinabile un confronto prima/dopo (mouse, tocco, tastiera). */
export function makeCompare(el) {
  let pos = 50;
  const set = (p) => { pos = Math.max(0, Math.min(100, p)); el.style.setProperty("--pos", pos + "%"); el.setAttribute("aria-valuenow", String(Math.round(pos))); };
  const from = (e) => { const r = el.getBoundingClientRect(); set(((e.clientX - r.left) / r.width) * 100); };
  el.setAttribute("role", "slider"); el.setAttribute("aria-valuemin", "0"); el.setAttribute("aria-valuemax", "100");
  el.tabIndex = 0;
  el.addEventListener("pointerdown", (e) => { if(el.dataset.pickColor === "true") return; el.setPointerCapture(e.pointerId); from(e); });
  el.addEventListener("pointermove", (e) => { if (el.dataset.pickColor !== "true" && el.hasPointerCapture(e.pointerId)) from(e); });
  el.addEventListener("keydown", (e) => {
    if(el.dataset.pickColor === "true") return;
    if (e.key === "ArrowLeft") { set(pos - 5); e.preventDefault(); }
    if (e.key === "ArrowRight") { set(pos + 5); e.preventDefault(); }
    if (e.key === "Home") { set(0); e.preventDefault(); }
    if (e.key === "End") { set(100); e.preventDefault(); }
  });
  set(50);
  return { set };
}

/** Clic su un'immagine con [data-zoom] la apre a tutto schermo. */
export function enableZoom() {
  let dlg = document.querySelector("dialog.zoom");
  if (!dlg) {
    dlg = document.createElement("dialog");
    dlg.className = "zoom";
    dlg.innerHTML = '<img alt=""><button type="button" class="zoom-close" aria-label="Close / Chiudi"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true" width="20" height="20"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button>';
    dlg.setAttribute("aria-label", "Fotografia / Photograph");
    document.body.append(dlg);
    dlg.addEventListener("click", (e) => { if (e.target === dlg || e.target.closest(".zoom-close")) dlg.close(); });
  }
  const prepare = () => document.querySelectorAll("img[data-zoom]").forEach((im) => {
    if (im.closest("button")) return;
    im.tabIndex = 0; im.setAttribute("role", "button");
    im.setAttribute("aria-label", tr({ it: "Ingrandisci fotografia", en: "Enlarge photograph" }));
  });
  prepare();
  const observer = new MutationObserver(prepare);
  observer.observe(document.querySelector("main") || document.body, { childList: true, subtree: true });
  document.addEventListener("langchange", prepare);
  document.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.matches("img[data-zoom]")) { e.preventDefault(); e.target.click(); }
  });
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-zoom]");
    if (!t) return;
    const im = dlg.querySelector("img");
    im.src = t.dataset.zoom || t.src;
    im.alt = t.alt || t.querySelector("img")?.alt || "";
    dlg.showModal();
  });
}
