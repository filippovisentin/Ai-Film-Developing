// Port di filmengine/enhance.py: versione "Migliorata" (nessun pixel inventato) e ingrandimento AI.
import { img, channel, median, percentile, stdOf, toSrgb, toLinear, meanChannels, gaussian, toMat, fromMat, cvOp } from "./core.js";

const DUST_CONTRAST = 0.25, DUST_RING_STD = 0.03, DUST_CHROMA = 0.25, DUST_MIN_BG = 0.25;
const clip01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

function plane(w, h, data) { return img(w, h, 1, data); }

/** Deviazione standard del rumore (Immerkaer con mediana). */
export function estimateNoise(cv, im) {
  const lap = cv.matFromArray(3, 3, cv.CV_32FC1, [1, -2, 1, -2, 4, -2, 1, -2, 1]);
  const sig = [];
  try {
    for (let k = 0; k < im.c; k++) {
      const r = cvOp(cv, plane(im.w, im.h, channel(im, k)), (s, d) => cv.filter2D(s, d, -1, lap));
      const inner = new Float32Array((im.w - 2) * (im.h - 2));
      let j = 0;
      for (let y = 1; y < im.h - 1; y++) for (let x = 1; x < im.w - 1; x++) inner[j++] = Math.abs(r.data[y * im.w + x]);
      sig.push(median(inner) / 0.6745 / 6.0);
    }
  } finally { lap.delete(); }
  return sig.reduce((a, b) => a + b, 0) / sig.length;
}

function boxFilter(cv, p, r) {
  return cvOp(cv, p, (s, d) => cv.boxFilter(s, d, -1, new cv.Size(2 * r + 1, 2 * r + 1), new cv.Point(-1, -1), true, cv.BORDER_REFLECT));
}

function guided(cv, guide, src, r, eps) {
  const n = guide.data.length, G = guide.data, S = src.data;
  const mul = (a, b) => { const o = new Float32Array(n); for (let i = 0; i < n; i++) o[i] = a[i] * b[i]; return plane(guide.w, guide.h, o); };
  const mg = boxFilter(cv, guide, r).data, ms = boxFilter(cv, src, r).data;
  const mgs = boxFilter(cv, mul(G, S), r).data, mgg = boxFilter(cv, mul(G, G), r).data;
  const a = new Float32Array(n), b = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const cov = mgs[i] - mg[i] * ms[i], v = mgg[i] - mg[i] * mg[i];
    a[i] = cov / (v + eps);
    b[i] = ms[i] - a[i] * mg[i];
  }
  const ma = boxFilter(cv, plane(guide.w, guide.h, a), r).data, mb = boxFilter(cv, plane(guide.w, guide.h, b), r).data;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = ma[i] * G[i] + mb[i];
  return out;
}

export function denoise(cv, rgb, strength = 1.0) {
  const enc = toSrgb(rgb);
  const sigma = estimateNoise(cv, enc) * strength;
  if (sigma < 1e-3) return img(rgb.w, rgb.h, 3, new Float32Array(rgb.data));
  const lum = meanChannels(enc);
  let lumD = lum;
  for (let i = 0; i < 2; i++) lumD = cvOp(cv, lumD, (s, d) => cv.bilateralFilter(s, d, 0, 2.5 * sigma, 2.0, cv.BORDER_DEFAULT));
  const out = img(rgb.w, rgb.h, 3), n = rgb.w * rgb.h, eps = (3 * sigma) ** 2;
  for (let k = 0; k < 3; k++) {
    const chroma = new Float32Array(n);
    for (let i = 0; i < n; i++) chroma[i] = enc.data[3 * i + k] - lum.data[i];
    const g = guided(cv, lumD, plane(rgb.w, rgb.h, chroma), 4, eps);
    for (let i = 0; i < n; i++) out.data[3 * i + k] = clip01(lumD.data[i] + g[i]);
  }
  return toLinear(out);
}

function ellipseOffsets(cv, size) {
  const k = cv.getStructuringElement(cv.MORPH_ELLIPSE, new cv.Size(size, size));
  const offs = [], c = Math.floor(size / 2);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) if (k.data[y * size + x]) offs.push([y - c, x - c]);
  k.delete();
  return offs;
}

function fill(cv, rgb, mask) {
  const { w, h } = rgb, n = w * h;
  const good = new Float32Array(n), weighted = img(w, h, 3);
  let masked = 0;
  for (let i = 0; i < n; i++) {
    good[i] = mask[i] ? 0 : 1;
    if (mask[i]) masked++;
    for (let k = 0; k < 3; k++) weighted.data[3 * i + k] = rgb.data[3 * i + k] * good[i];
  }
  const filled = new Float32Array(rgb.data);
  for (const sigma of [2.0, 4.0, 8.0]) {
    const den = gaussian(cv, plane(w, h, good), sigma).data, num = gaussian(cv, weighted, sigma).data;
    let ok = 0;
    for (let i = 0; i < n; i++) {
      if (mask[i] && den[i] > 1e-3) {
        ok++;
        for (let k = 0; k < 3; k++) filled[3 * i + k] = num[3 * i + k] / den[i];
      }
    }
    if (ok === masked) break;
  }
  const out = img(w, h, 3, new Float32Array(rgb.data));
  for (let i = 0; i < n; i++) if (mask[i]) for (let k = 0; k < 3; k++) out.data[3 * i + k] = filled[3 * i + k];
  return out;
}

/** Toglie i puntini chiari di polvere. */
export function removeDust(cv, rgb, maxArea = 80) {
  const { w, h } = rgb, n = w * h;
  const lumD = new Float32Array(n);
  for (let i = 0; i < n; i++) lumD[i] = Math.sqrt(clip01((rgb.data[3 * i] + rgb.data[3 * i + 1] + rgb.data[3 * i + 2]) / 3));
  const lum = plane(w, h, lumD);
  const k11 = cv.getStructuringElement(cv.MORPH_ELLIPSE, new cv.Size(11, 11));
  const opened = cvOp(cv, lum, (s, d) => cv.morphologyEx(s, d, cv.MORPH_OPEN, k11));
  k11.delete();
  const thr = Math.max(0.12, 8 * estimateNoise(cv, lum));
  const bin = new Uint8Array(n);
  for (let i = 0; i < n; i++) bin[i] = lumD[i] - opened.data[i] > thr ? 1 : 0;
  const binM = cv.matFromArray(h, w, cv.CV_8UC1, bin), labM = new cv.Mat(), stM = new cv.Mat(), cenM = new cv.Mat();
  const ncomp = cv.connectedComponentsWithStats(binM, labM, stM, cenM, 8, cv.CV_32S);
  const lab = new Int32Array(labM.data32S), st = new Int32Array(stM.data32S);
  [binM, labM, stM, cenM].forEach((m) => m.delete());
  const ring7 = ellipseOffsets(cv, 7);
  const mask = new Uint8Array(n);
  let count = 0;
  for (let i = 1; i < ncomp; i++) {
    const [x, y, cw, ch, area] = st.subarray(5 * i, 5 * i + 5);
    if (area > maxArea) continue;
    const y0 = Math.max(y - 6, 0), y1 = Math.min(y + ch + 6, h), x0 = Math.max(x - 6, 0), x1 = Math.min(x + cw + 6, w);
    const ww = x1 - x0, wh = y1 - y0;
    const comp = new Uint8Array(ww * wh);
    for (let yy = 0; yy < wh; yy++) for (let xx = 0; xx < ww; xx++) comp[yy * ww + xx] = lab[(yy + y0) * w + xx + x0] === i ? 1 : 0;
    const ringV = [], ins = [];
    for (let yy = 0; yy < wh; yy++) for (let xx = 0; xx < ww; xx++) {
      const j = yy * ww + xx;
      if (comp[j]) { ins.push(j); continue; }
      for (const [dy, dx] of ring7) {
        const sy = yy - dy, sx = xx - dx;
        if (sy >= 0 && sy < wh && sx >= 0 && sx < ww && comp[sy * ww + sx]) { ringV.push(lumD[(yy + y0) * w + xx + x0]); break; }
      }
    }
    if (!ringV.length) continue;
    const ring = Float32Array.from(ringV);
    let inMax = -Infinity;
    for (const j of ins) inMax = Math.max(inMax, lumD[(Math.floor(j / ww) + y0) * w + (j % ww) + x0]);
    if (inMax - percentile(ring, 90) < Math.max(thr, DUST_CONTRAST)) continue;
    if (median(ring) < DUST_MIN_BG) continue;
    if (stdOf(ring) > DUST_RING_STD) continue;
    let chroma = 0, total = 0;
    for (const j of ins) {
      const p = 3 * ((Math.floor(j / ww) + y0) * w + (j % ww) + x0);
      const r = rgb.data[p], g = rgb.data[p + 1], b = rgb.data[p + 2];
      chroma += Math.max(r, g, b) - Math.min(r, g, b);
      total += r + g + b;
    }
    if (chroma / ins.length > DUST_CHROMA * (total / (3 * ins.length))) continue;
    for (const j of ins) mask[(Math.floor(j / ww) + y0) * w + (j % ww) + x0] = 1;
    count++;
  }
  if (!count) return { out: rgb, count };
  const k5 = cv.getStructuringElement(cv.MORPH_ELLIPSE, new cv.Size(5, 5));
  const mM = cv.matFromArray(h, w, cv.CV_8UC1, mask), dM = new cv.Mat();
  cv.dilate(mM, dM, k5);
  const dil = new Uint8Array(dM.data);
  [k5, mM, dM].forEach((m) => m.delete());
  return { out: fill(cv, rgb, dil), count };
}

export function sharpen(cv, rgb, amount = 1.0, radius = 1.5, noise = null) {
  const enc = toSrgb(rgb), lum = meanChannels(enc), blur = gaussian(cv, lum, radius);
  const t = Math.max(0.006, 3 * (noise == null ? estimateNoise(cv, enc) : noise));
  const out = img(rgb.w, rgb.h, 3), n = rgb.w * rgb.h;
  for (let i = 0; i < n; i++) {
    const detail = lum.data[i] - blur.data[i];
    const gain = amount * clip01((Math.abs(detail) - t) / t);
    for (let k = 0; k < 3; k++) out.data[3 * i + k] = clip01(enc.data[3 * i + k] + gain * detail);
  }
  return toLinear(out);
}

/** Versione migliorata senza pixel inventati: polvere → rumore → nitidezza. */
export function enhance(cv, rgb, progress = () => {}) {
  const sigma = estimateNoise(cv, toSrgb(rgb));
  progress("polvere");
  let out = removeDust(cv, rgb).out;
  progress("rumore");
  out = denoise(cv, out);
  progress("nitidezza");
  out = sharpen(cv, out, 0.5, 1.5, sigma);
  return out;
}

// --- Ingrandimento AI (Real-ESRGAN General x4v3, BSD-3): aggiunge dettagli inventati ---
const SR_TILE = 128, SR_SCALE = 4, SR_OVERLAP = 16;

function reflectIndex(i, n) {
  // cv2.BORDER_REFLECT: fedcba|abcdef|fedcba
  if (n === 1) return 0;
  while (i < 0 || i >= n) i = i < 0 ? -i - 1 : 2 * n - i - 1;
  return i;
}

export async function superResolve(cv, ort, session, rgb, scale = 4, progress = () => {}) {
  if (scale !== 2 && scale !== 4) throw new Error("scala ammessa: 2 o 4");
  const enc = toSrgb(rgb), { w, h } = enc;
  const step = SR_TILE - 2 * SR_OVERLAP;
  const ny = Math.max(1, Math.ceil((h - 2 * SR_OVERLAP) / step)), nx = Math.max(1, Math.ceil((w - 2 * SR_OVERLAP) / step));
  const ph = ny * step + 2 * SR_OVERLAP, pw = nx * step + 2 * SR_OVERLAP;
  const S = SR_SCALE, O = SR_OVERLAP * S, T = SR_TILE * S;
  const W = pw * S, H = ph * S;
  const acc = new Float32Array(W * H * 3), wsum = new Float32Array(W * H);
  const ramp = new Float32Array(T).fill(1);
  for (let i = 0; i < O; i++) { ramp[i] = (i + 0.5) / O; ramp[T - 1 - i] = (i + 0.5) / O; }
  const name = session.inputNames[0];
  const tile = new Float32Array(3 * SR_TILE * SR_TILE);
  let done = 0;
  for (let ty = 0; ty < ny; ty++) {
    for (let tx = 0; tx < nx; tx++) {
      const y = ty * step, x = tx * step;
      for (let yy = 0; yy < SR_TILE; yy++) {
        const sy = reflectIndex(y + yy, h);
        for (let xx = 0; xx < SR_TILE; xx++) {
          const sx = reflectIndex(x + xx, w), p = 3 * (sy * w + sx);
          for (let k = 0; k < 3; k++) tile[k * SR_TILE * SR_TILE + yy * SR_TILE + xx] = enc.data[p + k];
        }
      }
      const res = await session.run({ [name]: new ort.Tensor("float32", tile, [1, 3, SR_TILE, SR_TILE]) });
      const up = res[session.outputNames[0]].data;
      for (let yy = 0; yy < T; yy++) {
        for (let xx = 0; xx < T; xx++) {
          const wgt = ramp[yy] * ramp[xx], q = (y * S + yy) * W + x * S + xx;
          for (let k = 0; k < 3; k++) acc[3 * q + k] += up[k * T * T + yy * T + xx] * wgt;
          wsum[q] += wgt;
        }
      }
      progress(++done / (nx * ny));
    }
  }
  let out = img(w * S, h * S, 3);
  for (let yy = 0; yy < h * S; yy++) for (let xx = 0; xx < w * S; xx++) {
    const q = yy * W + xx, o = yy * w * S + xx, d = Math.max(wsum[q], 1e-6);
    for (let k = 0; k < 3; k++) out.data[3 * o + k] = acc[3 * q + k] / d;
  }
  if (scale === 2) {
    out = cvOp(cv, out, (s, d) => cv.resize(s, d, new cv.Size(w * 2, h * 2), 0, 0, cv.INTER_AREA));
  }
  return toLinear(out);
}

export { toMat, fromMat };
