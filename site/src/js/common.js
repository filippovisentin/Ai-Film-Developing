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
  el.addEventListener("pointerdown", (e) => { el.setPointerCapture(e.pointerId); from(e); });
  el.addEventListener("pointermove", (e) => { if (el.hasPointerCapture(e.pointerId)) from(e); });
  el.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { set(pos - 5); e.preventDefault(); }
    if (e.key === "ArrowRight") { set(pos + 5); e.preventDefault(); }
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
    dlg.innerHTML = '<img alt="">';
    document.body.append(dlg);
    dlg.addEventListener("click", () => dlg.close());
  }
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-zoom]");
    if (!t) return;
    const im = dlg.querySelector("img");
    im.src = t.dataset.zoom || t.src;
    im.alt = t.alt || "";
    dlg.showModal();
  });
}
