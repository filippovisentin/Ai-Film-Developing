import { makeCompare, enableZoom, tr, lang } from "./common.js";
import "./color-lab.js";

const $ = (id) => document.getElementById(id);
const G = await (await fetch("data/gallery.json")).json();
const img = (n) => "img/g/" + n;
const fmt = (v) => (v == null ? "—" : lang() === "it" ? v.toFixed(1).replace(".", ",") : v.toFixed(1));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const ORIG = { it: "Sviluppo base", en: "Base development" };
const MODES = {
  originale: { name: ORIG, tag: ["ok", { it: "fedele", en: "faithful" }],
    text: { it: "La conversione del negativo, con grana, polvere e rumore dello scatto.",
            en: "The converted negative, with grain, dust and capture noise." } },
  migliorata: { name: { it: "Migliorata", en: "Enhanced" }, tag: ["ok", { it: "nessun pixel inventato", en: "no invented pixels" }],
    text: { it: "Polvere e rumore colorato ridotti, nitidezza moderata. Nessun dettaglio inventato.",
            en: "Dust and colour noise reduced, moderate sharpening. No invented detail." } },
  restaurata: { name: { it: "Restauro AI", en: "AI restore" }, tag: ["exp", { it: "sperimentale · solo locale", en: "experimental · local only" }],
    text: { it: "Rete addestrata su scatti da telefono simulati. Sui negativi veri dà il dettaglio più fedele (errore 0,0290 → 0,0269), ma non corregge i colori come la Migliorata.",
            en: "Network trained on simulated phone shots. On real negatives it gives the most faithful detail (error 0.0290 → 0.0269), but doesn't fix colour like Enhanced." } },
  ai: { name: { it: "Ingrandimento AI ×2", en: "AI upscale ×2" }, tag: ["ai", { it: "dettagli inventati", en: "invented detail" }],
    text: { it: "Real-ESRGAN inventa dettagli plausibili: belli da vedere, ma non sono sulla pellicola.",
            en: "Real-ESRGAN invents plausible detail: nice to look at, but it isn't on the film." } },
};
const VS = {
  stampa: { it: "Stampa di laboratorio", en: "Lab print" },
  negativo: { it: "Negativo", en: "Negative" },
  telefono: { it: "Scatto col telefono", en: "Phone shot" },
};
const STEPS_EN = [
  ["1. Phone shot", "Film on the light: tilted, uneven light, reflections, noise and JPEG."],
  ["2. Light corrected and cropped", "The bare-light photo corrects the lighting; the frame is found, straightened and trimmed."],
  ["3. Naive inversion", "What a plain 'invert colours' does: the orange mask turns into a blue cast."],
  ["4. Density inversion", "Divide by the film base and invert in density: right colours, but a flat image."],
  ["5. Printing paper", "Neutral blacks and whites, paper gamma and an S-curve: the final result."],
];
const warnText = (w) => (lang() === "en" && /più chiaro della base/.test(w)
  ? "frame brighter than the measured base (different exposure?): base corrected for this frame" : w.replace(/^[^:]+\.tif: /, ""));

let mode = G.modalita.full.migliorata ? "migliorata" : "originale", cur = 0, vs = "stampa";
const modeCmp = makeCompare($("modeCmp"));
makeCompare($("frameCmp"));

function renderStats() {
  const F = G.fotogrammi, avg = (k) => F.reduce((s, f) => s + (f[k] ?? 0), 0) / F.length;
  $("stats").innerHTML = [
    [F.length, { it: "fotogrammi reali, 4 pellicole", en: "real frames, 4 film stocks" }],
    [fmt(avg("dE_scansione")), { it: "ΔE storico rispetto alla scansione · motore di riferimento", en: "historical ΔE against the scan · reference engine" }],
    [fmt(avg("dE_stampa")), { it: "ΔE storico rispetto alla stampa · motore di riferimento", en: "historical ΔE against the print · reference engine" }],
  ].map(([n, l]) => `<div class="stat"><b>${n}</b><span>${tr(l)}</span></div>`).join("");
}

function renderModes() {
  const keys = Object.keys(MODES).filter((k) => G.modalita.full[k]);
  $("modeSeg").innerHTML = keys.map((k) => `<button data-k="${k}" aria-pressed="${k === mode}">${tr(MODES[k].name)}</button>`).join("");
  const m = MODES[mode], M = G.modalita;
  $("modeA").alt = tr(ORIG); $("modeB").alt = tr(m.name);
  $("detA").alt = tr(ORIG); $("detB").alt = tr(m.name);
  $("modeA").src = img(M.full.originale);
  $("modeB").src = img(M.full[mode]);
  $("modeCmp").classList.toggle("single", mode === "originale");
  $("modeCmp").querySelector(".lbl.l").textContent = tr(ORIG);
  $("modeLbl").textContent = tr(m.name);
  $("modeTag").className = "tag " + m.tag[0];
  $("modeTag").textContent = tr(m.tag[1]);
  $("modeTitle").textContent = tr(m.name);
  $("modeText").textContent = tr(m.text);
  $("detA").src = img(M.detail.originale);
  $("detB").src = img(M.detail[mode]);
  $("detA").nextElementSibling.textContent = tr(ORIG);
  $("detLbl").textContent = tr(m.name);
}
$("modeSeg").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) { mode = b.dataset.k; renderModes(); modeCmp.set(50); }
});

function renderFrames() {
  const F = G.fotogrammi;
  $("strip").innerHTML = F.map((f, i) =>
    `<button class="thumb" data-i="${i}" aria-pressed="${i === cur}"><img loading="lazy" src="${img(f.risultato)}" alt=""><span>${esc(f.pellicola)} · ${esc(f.id.split("-")[1])}</span></button>`).join("");
  $("vsSeg").innerHTML = Object.keys(VS).map((k) => `<button data-k="${k}" aria-pressed="${k === vs}">${tr(VS[k])}</button>`).join("");
  const f = F[cur];
  $("frA").alt = tr({ it: "Risultato dello sviluppo", en: "Developed result" });
  $("frB").alt = tr(VS[vs]);
  $("frA").src = img(f.risultato);
  $("frB").src = img(f[vs]);
  $("vsLbl").textContent = tr(VS[vs]);
  const place = f.id.split("-").slice(2).join(" ");
  $("side").innerHTML = `
    <h3>${esc(f.pellicola)}</h3>
    <div class="film">${esc(place.charAt(0).toUpperCase()+place.slice(1))}<br>${tr({ it: "Fotogramma", en: "Frame" })} ${esc(f.id.split("-")[1])}</div>
    <details class="gallery-details"><summary>${tr({ it: "Calibrazione e misure storiche", en: "Calibration and historical measurements" })}</summary><div class="metric"><div>${tr({ it: "Rispetto alla scansione", en: "Against the scan" })}<small>${tr({ it: "quanto pesa lo scatto col telefono", en: "what the phone shot costs" })}</small></div><b>${fmt(f.dE_scansione)}</b></div>
    <div class="metric"><div>${tr({ it: "Rispetto alla stampa", en: "Against the print" })}<small>${tr({ it: "include le scelte dello stampatore", en: "includes the printer's choices" })}</small></div><b>${fmt(f.dE_stampa)}</b></div>
    </details>${f.avvisi.length ? `<ul class="warns">${f.avvisi.map((w) => `<li>${esc(warnText(w))}</li>`).join("")}</ul>` : ""}`;
  $("four").innerHTML = [
    ["negativo", { it: "1 · Negativo", en: "1 · Negative" }, { it: "la pellicola sviluppata", en: "the developed film" }],
    ["telefono", { it: "2 · Scatto col telefono", en: "2 · Phone shot" }, { it: "ingresso del motore", en: "engine input" }],
    ["risultato", { it: "3 · Sviluppo base", en: "3 · Base development" }, { it: "motore di riferimento", en: "reference engine" }],
    ["stampa", { it: "4 · Stampa di laboratorio", en: "4 · Lab print" }, { it: "riferimento d'epoca", en: "period reference" }],
  ].map(([k, t, s]) => `<figure><img loading="lazy" src="${img(f[k])}" alt="${esc(tr(t))}" data-zoom><figcaption>${tr(t)}<span>${tr(s)}</span></figcaption></figure>`).join("");
}
$("strip").addEventListener("click", (e) => { const b = e.target.closest(".thumb"); if (b) { cur = +b.dataset.i; renderFrames(); } });
$("vsSeg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { vs = b.dataset.k; renderFrames(); } });

function renderSteps() {
  $("steps").innerHTML = G.passi.passi.map((p, i) => {
    const [t, d] = lang() === "en" ? STEPS_EN[i] || [p.titolo, p.testo] : [p.titolo, p.testo];
    return `<li class="${i === 2 ? "bad" : ""}"><img loading="lazy" src="${img(p.img)}" alt="${esc(t)}" data-zoom><div class="t">${esc(t)}</div><div class="d">${esc(d)}</div></li>`;
  }).join("");
}

function renderAll() { renderStats(); renderModes(); renderFrames(); renderSteps(); }
document.addEventListener("langchange", renderAll);
renderAll();
enableZoom();

const tabs = [...document.querySelectorAll('.gallery-tabs [role="tab"]')];
function activateTab(id, updateHistory = false) {
  const active = tabs.find(t => t.getAttribute('aria-controls') === id) || tabs[0];
  for (const tab of tabs) {
    const selected = tab === active;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    $(tab.getAttribute('aria-controls')).hidden = !selected;
  }
  if (updateHistory) {
    const url = new URL(location.href); url.hash = active.getAttribute('aria-controls');
    history.pushState(null, '', url);
  }
}
tabs.forEach((tab, i) => {
  tab.addEventListener('click', () => activateTab(tab.getAttribute('aria-controls'), true));
  tab.addEventListener('keydown', e => {
    let next;
    if (e.key === 'ArrowRight') next = (i + 1) % tabs.length;
    if (e.key === 'ArrowLeft') next = (i + tabs.length - 1) % tabs.length;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = tabs.length - 1;
    if (next === undefined) return;
    e.preventDefault(); tabs[next].focus();
    activateTab(tabs[next].getAttribute('aria-controls'), true);
  });
});
const syncTab = () => activateTab(location.hash.slice(1));
window.addEventListener('hashchange', syncTab);
window.addEventListener('popstate', syncTab);
syncTab();
