// Worker dell'applicativo: tutto il calcolo avviene qui, sul dispositivo. Nessuna foto viene inviata.
/* global cv, ort */
const MAX_SIDE = 3000;      // lato lungo massimo elaborato nel browser (memoria dei telefoni)
const AI_MAX_IN = 1024;     // l'AI lavora su una versione ridotta: risultato fino a 4096 px

let engine = null, cvReady = null, ortSession = null;
let activeSource = null, developmentRevision = 0, editRevision = 0;
let pristine = {}, packed = {};
// percorsi relativi a questo file (js/): il sito può stare in una sottocartella (GitHub Pages)
const at = (p) => new URL(p, self.location.href).href;
const post = (m, transfer) => self.postMessage(m, transfer || []);
const progress = (stage, frac) => post({ type: "progress", stage, frac });

function loadCv() {
  if (cvReady) return cvReady;
  cvReady = new Promise((resolve, reject) => {
    try { importScripts(at("../vendor/opencv.js")); } catch (e) { reject(e); return; }
    const t0 = Date.now();
    // cv è un oggetto "thenable": non va passato a resolve(), si aspetta che sia pronto
    const wait = () => (self.cv && self.cv.Mat ? resolve(true)
      : Date.now() - t0 > 60000 ? reject(new Error("OpenCV non si è avviato")) : setTimeout(wait, 30));
    wait();
  });
  return cvReady;
}

async function loadEngine() {
  if (engine) return engine;
  await loadCv();
  const [core, pipeline, enhance, adjust, geometry] = await Promise.all([
    import(at("../engine/core.js")), import(at("../engine/pipeline.js")), import(at("../engine/enhance.js")), import(at("../engine/adjust.js")), import(at("../engine/geometry.js"))]);
  engine = { core, pipeline, enhance, adjust, geometry };
  return engine;
}

async function loadAi() {
  if (ortSession) return ortSession;
  if (!self.ort) importScripts(at("../vendor/ort.wasm.min.js"));
  ort.env.wasm.wasmPaths = at("../vendor/");
  // un solo thread: con più thread ONNX Runtime si blocca quando gira dentro un worker
  ort.env.wasm.numThreads = 1;
  ortSession = await ort.InferenceSession.create(at("../models/real_esrgan_general_x4v3.onnx"), {
    executionProviders: ["wasm"],
    externalData: [{ path: "real_esrgan_general_x4v3.data", data: at("../models/real_esrgan_general_x4v3.data") }],
  });
  return ortSession;
}

/** Decode through the browser's color management into an explicit sRGB canvas. */
async function decode(blob, maxSide, forceSize) {
  let bmp;
  try {
    bmp = await createImageBitmap(blob, { imageOrientation: "from-image", colorSpaceConversion: "default", premultiplyAlpha: "none" });
  } catch {
    throw new Error("decode");
  }
  const w0 = bmp.width, h0 = bmp.height;
  const canvas = new OffscreenCanvas(w0, h0);
  const ctx = canvas.getContext("2d", { willReadFrequently: true, colorSpace: "srgb" });
  ctx.drawImage(bmp, 0, 0);
  bmp.close();
  const px = ctx.getImageData(0, 0, w0, h0).data;
  const { core } = engine;
  const lut = new Float32Array(256);
  for (let i = 0; i < 256; i++) lut[i] = core.srgbToLinear(i / 255);
  let im = core.img(w0, h0, 3);
  for (let i = 0, j = 0; i < px.length; i += 4, j += 3) {
    im.data[j] = lut[px[i]]; im.data[j + 1] = lut[px[i + 1]]; im.data[j + 2] = lut[px[i + 2]];
  }
  const orig = { w: w0, h: h0 };
  if (forceSize && forceSize.from.w === w0 && forceSize.from.h === h0) {
    if (forceSize.to.w !== w0) im = core.resizeArea(cv, im, forceSize.to.w, forceSize.to.h);
  } else if (Math.max(w0, h0) > maxSide) {
    const s = maxSide / Math.max(w0, h0);
    im = core.resizeArea(cv, im, Math.round(w0 * s), Math.round(h0 * s));
  }
  return { im, orig };
}

function toRgba8(im) {
  const { core } = engine, n = im.w * im.h, out = new Uint8ClampedArray(n * 4);
  const lut = new Uint8ClampedArray(4097);
  for (let i = 0; i <= 4096; i++) lut[i] = Math.round(core.linearToSrgb(i / 4096) * 255);
  for (let i = 0; i < n; i++) {
    for (let k = 0; k < 3; k++) {
      const v = im.data[3 * i + k];
      // la curva è ripida vicino al nero: lì si calcola esatto, altrove basta la tabella
      out[4 * i + k] = v < 0.02 ? Math.round(core.linearToSrgb(v) * 255) : lut[Math.round(Math.min(v, 1) * 4096)];
    }
    out[4 * i + 3] = 255;
  }
  return out;
}

async function toJpeg(im) {
  const c = new OffscreenCanvas(im.w, im.h);
  c.getContext("2d").putImageData(new ImageData(toRgba8(im), im.w, im.h), 0, 0);
  return c.convertToBlob({ type: "image/jpeg", quality: 0.95 });
}

/** TIFF RGB 16 bit non compresso, sRGB: per l'archivio e la post-produzione. */
function toTiff16(im) {
  const { core } = engine, { w, h } = im;
  const software = "Ai-Film-Developing (browser)\0";
  const tags = [[256, 4, 1, w], [257, 4, 1, h], [258, 3, 3, "bps"], [259, 3, 1, 1], [262, 3, 1, 2], [273, 4, 1, "data"],
    [277, 3, 1, 3], [278, 4, 1, h], [279, 4, 1, w * h * 6], [284, 3, 1, 1], [305, 2, software.length, "sw"]];
  const ifdSize = 2 + tags.length * 12 + 4;
  const bpsOff = 8 + ifdSize, swOff = bpsOff + 6, dataOff = (swOff + software.length + 1) & ~1;
  const buf = new ArrayBuffer(dataOff + w * h * 6), v = new DataView(buf);
  v.setUint16(0, 0x4949); v.setUint16(2, 42, true); v.setUint32(4, 8, true);
  v.setUint16(8, tags.length, true);
  tags.forEach(([tag, type, count, val], i) => {
    const o = 10 + i * 12;
    v.setUint16(o, tag, true); v.setUint16(o + 2, type, true); v.setUint32(o + 4, count, true);
    const value = val === "bps" ? bpsOff : val === "data" ? dataOff : val === "sw" ? swOff : val;
    if (type === 3 && count === 1) v.setUint16(o + 8, value, true); else v.setUint32(o + 8, value, true);
  });
  v.setUint32(10 + tags.length * 12, 0, true);
  for (let k = 0; k < 3; k++) v.setUint16(bpsOff + 2 * k, 16, true);
  for (let i = 0; i < software.length; i++) v.setUint8(swOff + i, software.charCodeAt(i));
  const px = new Uint16Array(buf, dataOff, w * h * 3);
  for (let i = 0; i < px.length; i++) px[i] = Math.round(core.linearToSrgb(im.data[i]) * 65535);
  return new Blob([buf], { type: "image/tiff" });
}

async function pack(im) {
  return { jpg: await toJpeg(im), tif: toTiff16(im), w: im.w, h: im.h };
}

const T = {
  it: {
    warnBrighter: "fotogramma più chiaro della base misurata (esposizione diversa?): base corretta per questo fotogramma",
    warnLightClipped: "foto della luce saturata (zone bruciate): ignorata. Rifalla con meno esposizione per correggere la luce non uniforme",
    warnNoFrame: "fotogramma non trovato: uso l'immagine intera",
    warnBaseEstimated: "base stimata dai bordi del fotogramma (manca la foto del bordo: risultato meno preciso)",
    warnResized: (a, b) => `immagine ridotta da ${a} a ${b} px sul lato lungo per lavorare nel browser`,
    warnAiResized: (b) => `l'AI ha lavorato su una versione ridotta a ${b} px (la versione locale lavora a piena risoluzione)`,
  },
  en: {
    warnBrighter: "frame brighter than the measured base (different exposure?): base corrected for this frame",
    warnLightClipped: "light photo is clipped (blown-out areas): ignored. Retake it with less exposure to correct uneven light",
    warnNoFrame: "frame not found: using the whole image",
    warnBaseEstimated: "base estimated from the frame edges (no edge photo: less accurate result)",
    warnResized: (a, b) => `image reduced from ${a} to ${b} px on the long side to work in the browser`,
    warnAiResized: (b) => `the AI worked on a version reduced to ${b} px (the local version works at full resolution)`,
  },
};

async function develop(msg, revision) {
  const current = () => revision === developmentRevision && activeSource === msg.sourceId;
  const send = m => { if (current()) post({ ...m, sourceId: msg.sourceId }); };
  const progress = (stage, frac) => send({ type: "progress", stage, frac });
  const t0 = performance.now();
  const L = T[msg.lang] || T.it;
  progress("engine", 0);
  await loadEngine();
  const { core, pipeline, enhance } = engine;
  progress("decode", 0.05);
  const neg = await decode(msg.files.negativo, MAX_SIDE);
  if (!current()) return;
  const warnings = [];
  if (Math.max(neg.orig.w, neg.orig.h) > MAX_SIDE) warnings.push(L.warnResized(Math.max(neg.orig.w, neg.orig.h), Math.max(neg.im.w, neg.im.h)));
  const size = { from: neg.orig, to: { w: neg.im.w, h: neg.im.h } };
  const light = msg.files.luce ? (await decode(msg.files.luce, MAX_SIDE, size)).im : null;
  const baseImg = msg.files.bordo ? (await decode(msg.files.bordo, MAX_SIDE)).im : null;
  if (!current()) return;
  progress("develop", 0.15);
  const { positive, warnings: w } = pipeline.developFrame(cv, neg.im, { light, baseImg, profile: msg.profile, colorMode: msg.colorMode, manualCorners: msg.manualCorners, t: (k) => L[k] || k });
  warnings.push(...w);
  const results = { originale: await pack(positive) };
  if (!current()) return;
  pristine.originale = positive; packed.originale = results.originale;
  send({ type: "partial", key: "originale", result: results.originale, warnings });
  let better = null;
  if (msg.migliora || msg.ai) {
    better = enhance.enhance(cv, positive, (s) => progress("enhance-" + s, 0.45));
    if (msg.migliora) {
      results.migliorata = await pack(better);
      if (!current()) return;
      pristine.migliorata = better; packed.migliorata = results.migliorata;
      send({ type: "partial", key: "migliorata", result: results.migliorata });
    }
  }
  if (msg.ai) {
    progress("ai-load", 0.6);
    const session = await loadAi();
    if (!current()) return;
    let src = better;
    if (Math.max(src.w, src.h) > AI_MAX_IN) {
      const s = AI_MAX_IN / Math.max(src.w, src.h);
      src = core.resizeArea(cv, src, Math.round(src.w * s), Math.round(src.h * s));
      warnings.push(L.warnAiResized(Math.max(src.w, src.h)));
    }
    const up = await enhance.superResolve(cv, ort, session, src, msg.ai, (f) => progress("ai", 0.6 + 0.38 * f));
    results.ai = await pack(up);
    if (!current()) return;
    pristine.ai = up; packed.ai = results.ai;
  }
  send({ type: "done", results, warnings, ms: Math.round(performance.now() - t0) });
}

self.onmessage = async (e) => {
  const msg = e.data;
  if (msg.type === "detect-crop") {
    try {
      await loadEngine();
      const { im } = await decode(msg.file, MAX_SIDE);
      const q = engine.geometry.findFrameCorners(cv, im);
      post({ type: "crop-detected", sourceId: msg.sourceId, requestId: msg.requestId,
        corners: q ? q.map(([x,y]) => [Math.max(0, Math.min(1,x/(im.w-1))), Math.max(0, Math.min(1,y/(im.h-1)))]) : null });
    } catch (err) { post({ type: "edit-error", sourceId: msg.sourceId, requestId: msg.requestId, message: err.message }); }
    return;
  }
  if (msg.type === "adjust" || msg.type === "neutral") {
    if (msg.sourceId !== activeSource) return;
    const revision = ++editRevision, dev = developmentRevision;
    const current = () => revision === editRevision && dev === developmentRevision && msg.sourceId === activeSource;
    try {
      if (msg.type === "neutral") {
        if (!pristine.originale) throw new Error("edit-source-unavailable");
        const gains = engine.adjust.sampleNeutralGains(pristine.originale, msg);
        if (current()) post({ type: "neutral-picked", sourceId: msg.sourceId, requestId: msg.requestId, gains });
      } else {
        if (!pristine[msg.key]) throw new Error("edit-source-unavailable");
        const settings = msg.settings || {};
        const identity = (settings.temperature || 0) === 0 && (settings.tint || 0) === 0 && (!settings.gains || settings.gains.every(v => v === 1));
        // Validate settings even when the pristine packed output can be reused.
        const adjusted = engine.adjust.applyColorAdjustments(pristine[msg.key], settings);
        const result = identity ? packed[msg.key] : await pack(adjusted);
        if (current()) post({ type: "adjusted", sourceId: msg.sourceId, requestId: msg.requestId, key: msg.key, result });
      }
    } catch (err) {
      if (current()) post({ type: "edit-error", sourceId: msg.sourceId, requestId: msg.requestId, key: msg.key, message: err.message });
    }
    return;
  }
  let revision;
  try {
    if (msg.type === "preload") { await loadEngine(); post({ type: "ready" }); }
    else if (msg.type === "develop") {
      revision = ++developmentRevision; ++editRevision;
      activeSource = msg.sourceId; pristine = {}; packed = {};
      await develop(msg, revision);
    }
  } catch (err) {
    if (revision == null || revision === developmentRevision) post({ type: "error", sourceId: msg.sourceId, message: err && err.message ? err.message : String(err) });
  }
};
