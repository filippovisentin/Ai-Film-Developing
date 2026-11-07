import { makeCompare, tr, lang } from "./common.js";

const $ = (s) => document.querySelector(s);
const files = {};
let profiles = [], sr = 2, results = {}, current = "originale", busy = false, ready = false;
const urls = [];

const LABELS = { originale: { it: "Originale", en: "Original" }, migliorata: { it: "Migliorata", en: "Enhanced" }, ai: { it: "AI", en: "AI" } };
const NOTES = {
  originale: { it: "Lo sviluppo fedele: solo ciò che c'è sul negativo.", en: "The faithful development: only what's on the negative." },
  migliorata: { it: "Pulita: polvere e rumore ridotti, nitidezza moderata. Nessun dettaglio inventato. Trascina la barra per confrontare.",
    en: "Cleaned: dust and noise reduced, moderate sharpening. No invented detail. Drag the bar to compare." },
  ai: { it: "Attenzione: i dettagli fini di questa versione sono stati inventati dalla rete neurale (Real-ESRGAN). Belli da vedere, ma non sono sulla pellicola.",
    en: "Note: the fine detail in this version was invented by the neural network (Real-ESRGAN). Nice to look at, but it isn't on the film." },
};
const STAGES = {
  engine: { it: "Avvio del motore (la prima volta scarica ~10 MB)…", en: "Starting the engine (first time downloads ~10 MB)…" },
  decode: { it: "Lettura delle foto…", en: "Reading the photos…" },
  develop: { it: "Ritaglio, inversione in densità, carta da stampa…", en: "Cropping, density inversion, printing paper…" },
  "enhance-polvere": { it: "Migliorata: polvere…", en: "Enhanced: dust…" },
  "enhance-rumore": { it: "Migliorata: rumore…", en: "Enhanced: noise…" },
  "enhance-nitidezza": { it: "Migliorata: nitidezza…", en: "Enhanced: sharpening…" },
  "ai-load": { it: "Carico il modello AI (~5 MB)…", en: "Loading the AI model (~5 MB)…" },
  ai: { it: "Ingrandimento AI…", en: "AI upscaling…" },
};
const ERR = {
  decode: { it: "Questo formato non si apre in questo browser: prova con un JPEG o PNG (le foto HEIC si aprono solo in Safari).",
    en: "This format can't be opened in this browser: try a JPEG or PNG (HEIC photos open in Safari only)." },
};

// ---------- worker ----------
const worker = new Worker("/js/worker.js");
worker.onmessage = (e) => {
  const m = e.data;
  if (m.type === "ready") { ready = true; engineState(); }
  else if (m.type === "progress") setProgress(m.stage, m.frac);
  else if (m.type === "partial") { results[m.key] = wrap(m.result); if (m.warnings) showWarnings(m.warnings); show(m.key === "migliorata" ? "migliorata" : current in results ? current : m.key); }
  else if (m.type === "done") finish(m);
  else if (m.type === "error") fail(m.message);
};
worker.onerror = (e) => fail(e.message || "worker");
// il motore si scarica in anticipo appena la pagina è inattiva
const preload = () => worker.postMessage({ type: "preload" });
if (window.requestIdleCallback) requestIdleCallback(preload, { timeout: 1500 }); else setTimeout(preload, 300);

function engineState() {
  const el = $("#engineState");
  el.className = "engine-state" + (ready ? " ready" : "");
  el.textContent = ready ? tr({ it: "● motore pronto", en: "● engine ready" }) : tr({ it: "○ scarico il motore…", en: "○ downloading the engine…" });
}

// ---------- profili ----------
async function loadProfiles() {
  profiles = await (await fetch("/data/profiles.json")).json();
  const sel = $("#profilo"), prev = sel.value || "generic_color";
  sel.innerHTML = "";
  const groups = { color_negative: { it: "Negativo colore", en: "Colour negative" }, bw_negative: { it: "Bianco e nero", en: "Black and white" }, slide: { it: "Diapositiva", en: "Slide" } };
  for (const [type, label] of Object.entries(groups)) {
    const list = profiles.filter((p) => p.type === type);
    if (!list.length) continue;
    const og = document.createElement("optgroup");
    og.label = tr(label);
    for (const p of list) og.append(new Option(lang() === "en" && p.name_en ? p.name_en : p.name, p.id, false, p.id === prev));
    sel.append(og);
  }
}

// ---------- file ----------
function setFile(drop, file, name) {
  const key = drop.dataset.key;
  files[key] = file;
  drop.querySelector(".ok").textContent = file ? "✓ " + (name || file.name || key) : "";
  const im = drop.querySelector("img");
  if (im.src.startsWith("blob:")) URL.revokeObjectURL(im.src);
  drop.classList.toggle("has", !!file);
  if (file) { im.src = URL.createObjectURL(file); im.hidden = false; im.onerror = () => (im.hidden = true); }
  else { im.removeAttribute("src"); im.hidden = true; }
  let clear = drop.querySelector(".clear");
  if (file && !clear) {
    clear = document.createElement("button");
    clear.type = "button"; clear.className = "clear"; clear.textContent = "×";
    clear.setAttribute("aria-label", tr({ it: "Rimuovi", en: "Remove" }));
    clear.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); setFile(drop, null); drop.querySelector("input").value = ""; });
    drop.append(clear);
  } else if (!file && clear) clear.remove();
  $("#go").disabled = busy || !files.negativo;
}
document.querySelectorAll(".drop").forEach((drop) => {
  const input = drop.querySelector("input");
  input.addEventListener("change", () => input.files[0] && setFile(drop, input.files[0]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) setFile(drop, f); });
});
$("#sample").addEventListener("click", async () => {
  const load = async (k, url) => setFile(document.querySelector(`.drop[data-key="${k}"]`), await (await fetch(url)).blob(), url.split("/").pop());
  await Promise.all([load("negativo", "/img/esempio/negativo.jpg"), load("luce", "/img/esempio/luce.jpg"), load("bordo", "/img/esempio/bordo.jpg")]);
  $("#profilo").value = "generic_color";
  $("#msg").className = "msg";
  $("#msg").textContent = tr({ it: "Scatto di esempio caricato (Fuji 100, Tokyo 1994 · BlueNeg, Copyrighted by Tien-Tsin Wong). Premi Sviluppa.",
    en: "Sample shot loaded (Fuji 100, Tokyo 1994 · BlueNeg, Copyrighted by Tien-Tsin Wong). Press Develop." });
});

// ---------- modalità ----------
$("#ai").addEventListener("change", (e) => document.querySelectorAll("#sr button").forEach((b) => (b.disabled = !e.target.checked)));
document.querySelectorAll("#sr button").forEach((b) => b.addEventListener("click", (e) => {
  e.preventDefault();
  sr = +b.dataset.sr;
  document.querySelectorAll("#sr button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
}));

// ---------- sviluppo ----------
$("#form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (!files.negativo || busy) return;
  busy = true;
  $("#go").disabled = true;
  results = {};
  urls.splice(0).forEach((u) => URL.revokeObjectURL(u));
  $("#warns").innerHTML = "";
  $("#msg").className = "msg"; $("#msg").textContent = "";
  $("#progress").hidden = false;
  setProgress("engine", 0);
  const profile = profiles.find((p) => p.id === $("#profilo").value);
  worker.postMessage({ type: "develop", lang: lang(), profile,
    files: { negativo: files.negativo, luce: files.luce || null, bordo: files.bordo || null },
    migliora: $("#migliora").checked, ai: $("#ai").checked ? sr : 0 });
});

let lastStage = "engine";
function setProgress(stage, frac) {
  lastStage = stage;
  $("#fill").style.width = Math.round(Math.max(0.03, frac) * 100) + "%";
  const pct = stage === "ai" ? ` ${Math.round(((frac - 0.6) / 0.38) * 100)}%` : "";
  $("#stage").textContent = tr(STAGES[stage] || { it: stage, en: stage }) + pct;
}
function finish(m) {
  for (const [k, r] of Object.entries(m.results)) if (!results[k]) results[k] = wrap(r);
  busy = false;
  $("#go").disabled = !files.negativo;
  $("#progress").hidden = true;
  showWarnings(m.warnings);
  $("#msg").textContent = tr({ it: `Fatto in ${(m.ms / 1000).toFixed(1)} s.`, en: `Done in ${(m.ms / 1000).toFixed(1)} s.` });
  show(results.ai ? "ai" : results.migliorata ? "migliorata" : "originale");
  if (matchMedia("(max-width: 980px)").matches) document.querySelector(".result").scrollIntoView({ behavior: "smooth", block: "start" });
}
function fail(message) {
  busy = false;
  $("#go").disabled = !files.negativo;
  $("#progress").hidden = true;
  $("#msg").className = "msg err";
  $("#msg").textContent = tr({ it: "Non riuscito: ", en: "Failed: " }) + (ERR[message] ? tr(ERR[message]) : message);
}
function showWarnings(list) {
  $("#warns").innerHTML = "";
  for (const w of list || []) { const li = document.createElement("li"); li.textContent = "⚠ " + w; $("#warns").append(li); }
}
function wrap(r) {
  const jpg = URL.createObjectURL(r.jpg), tif = URL.createObjectURL(r.tif);
  urls.push(jpg, tif);
  return { jpg, tif, w: r.w, h: r.h };
}

// ---------- risultato ----------
const cmp = makeCompare($("#cmp"));
function show(key) {
  current = key;
  $("#empty").hidden = true;
  $("#out").hidden = false;
  const tabs = $("#tabs");
  tabs.innerHTML = "";
  for (const k of Object.keys(LABELS)) if (results[k]) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = tr(LABELS[k]) + (k === "ai" ? ` ×${results.ai.w / results.originale.w > 3 ? 4 : 2}` : "");
    if (k === "ai") b.className = "ai";
    b.setAttribute("aria-pressed", String(k === key));
    b.onclick = () => show(k);
    tabs.append(b);
  }
  $("#imgA").src = results.originale.jpg;
  $("#imgB").src = results[key].jpg;
  $("#cmp").classList.toggle("single", key === "originale");
  $("#lblA").textContent = tr(LABELS.originale);
  $("#lblB").textContent = tr(LABELS[key]);
  const note = $("#note");
  note.textContent = tr(NOTES[key]);
  note.className = "note" + (key === "ai" ? " ai" : "");
  const dl = $("#dl");
  dl.innerHTML = "";
  for (const k of Object.keys(LABELS)) if (results[k]) {
    const r = results[k], name = tr(LABELS[k]);
    const a = document.createElement("a");
    a.href = r.jpg; a.download = `negativo_${k}.jpg`;
    a.textContent = `${tr({ it: "Scarica", en: "Download" })} ${name} · JPEG`;
    const t = document.createElement("a");
    t.href = r.tif; t.download = `negativo_${k}_16bit.tif`; t.className = "tif";
    t.textContent = `${name} · TIFF 16 bit`;
    dl.append(a, t);
  }
  const r = results[key];
  $("#meta").textContent = `${r.w} × ${r.h} px`;
  $("#lens").hidden = key === "originale";
  if (key !== "originale") {
    $("#capA").textContent = tr(LABELS.originale) + tr({ it: " (ingrandita)", en: " (zoomed)" });
    $("#capB").textContent = tr(LABELS[key]) + tr({ it: " (ingrandita)", en: " (zoomed)" });
    lensAt(0.5, 0.5);
  }
}

// lente: lo stesso punto delle due versioni a confronto, ingrandito
const imgs = {};
function load(src) { if (!imgs[src]) { imgs[src] = new Image(); imgs[src].src = src; } return imgs[src]; }
function draw(canvas, src, fx, fy, side) {
  const im = load(src);
  const paint = () => {
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    const s = side * (im.naturalWidth / results.originale.w);
    const x = Math.min(Math.max(fx * im.naturalWidth - s / 2, 0), im.naturalWidth - s);
    const y = Math.min(Math.max(fy * im.naturalHeight - s / 2, 0), im.naturalHeight - s);
    ctx.drawImage(im, x, y, s, s, 0, 0, canvas.width, canvas.height);
  };
  im.complete && im.naturalWidth ? paint() : im.addEventListener("load", paint, { once: true });
}
function lensAt(fx, fy) {
  if (current === "originale") return;
  const side = Math.max(24, Math.round(results.originale.w / 12));
  draw($("#lensA"), results.originale.jpg, fx, fy, side);
  draw($("#lensB"), results[current].jpg, fx, fy, side);
}
$("#cmp").addEventListener("pointermove", (e) => {
  const im = $("#imgB"), r = im.getBoundingClientRect();
  // l'immagine è "contain": si calcola il rettangolo effettivo
  const ar = im.naturalWidth / im.naturalHeight || 1.5, boxAr = r.width / r.height;
  const w = boxAr > ar ? r.height * ar : r.width, h = boxAr > ar ? r.height : r.width / ar;
  const x0 = r.left + (r.width - w) / 2, y0 = r.top + (r.height - h) / 2;
  lensAt(Math.min(Math.max((e.clientX - x0) / w, 0), 1), Math.min(Math.max((e.clientY - y0) / h, 0), 1));
});

document.addEventListener("langchange", () => {
  engineState();
  loadProfiles();
  if (busy) setProgress(lastStage, parseFloat($("#fill").style.width) / 100);
  if (Object.keys(results).length) show(current);
});
engineState();
loadProfiles();
cmp.set(50);
