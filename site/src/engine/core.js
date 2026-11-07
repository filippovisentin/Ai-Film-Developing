// Strumenti di base del motore nel browser: immagini float32, statistiche come numpy, ponte con OpenCV.js.
// Un'immagine è { w, h, c, data: Float32Array } con canali interlacciati (come un array numpy h×w×c).

export const img = (w, h, c, data) => ({ w, h, c, data: data || new Float32Array(w * h * c) });

export function crop(im, y0, y1, x0, x1) {
  const w = x1 - x0, h = y1 - y0, c = im.c, out = img(w, h, c);
  for (let y = 0; y < h; y++) {
    const s = ((y + y0) * im.w + x0) * c;
    out.data.set(im.data.subarray(s, s + w * c), y * w * c);
  }
  return out;
}

export function meanChannels(im) {
  const n = im.w * im.h, out = img(im.w, im.h, 1), d = im.data, c = im.c;
  for (let i = 0; i < n; i++) {
    let s = 0;
    for (let k = 0; k < c; k++) s += d[i * c + k];
    out.data[i] = s / c;
  }
  return out;
}

export function channel(im, k) {
  const n = im.w * im.h, out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = im.data[i * im.c + k];
  return out;
}

// numpy round(): metà verso il pari
export function pyRound(x) {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 ? 2 * Math.round(x / 2) : r;
}

// --- percentili esatti come numpy (interpolazione lineare), con selezione in O(n) ---
function select(a, k, lo, hi) {
  while (hi > lo) {
    const pivot = a[(lo + hi) >> 1];
    let i = lo, j = hi;
    while (i <= j) {
      while (a[i] < pivot) i++;
      while (a[j] > pivot) j--;
      if (i <= j) { const t = a[i]; a[i] = a[j]; a[j] = t; i++; j--; }
    }
    if (k <= j) hi = j; else if (k >= i) lo = i; else return;
  }
}

/** Percentile q (0..100) di un array (copiato: l'originale non cambia). */
export function percentile(values, q) {
  const n = values.length;
  if (!n) return NaN;
  const a = values instanceof Float64Array ? new Float64Array(values) : Float32Array.from(values);
  const idx = (q / 100) * (n - 1), lo = Math.floor(idx), frac = idx - lo;
  select(a, lo, 0, n - 1);
  const vlo = a[lo];
  if (frac === 0 || lo + 1 >= n) return vlo;
  let vhi = Infinity;
  for (let i = lo + 1; i < n; i++) if (a[i] < vhi) vhi = a[i];
  return vlo + (vhi - vlo) * frac;
}
export const median = (v) => percentile(v, 50);

/** Percentile per canale di un'immagine, prendendo un pixel ogni `step`. */
export function channelPercentiles(im, q, step = 1) {
  const n = Math.ceil((im.w * im.h) / step), out = [];
  for (let k = 0; k < im.c; k++) {
    const v = new Float32Array(n);
    for (let i = 0, j = 0; j < n; i += step, j++) v[j] = im.data[i * im.c + k];
    out.push(percentile(v, q));
  }
  return out;
}

export function stdOf(v) {
  let m = 0;
  for (let i = 0; i < v.length; i++) m += v[i];
  m /= v.length;
  let s = 0;
  for (let i = 0; i < v.length; i++) s += (v[i] - m) ** 2;
  return Math.sqrt(s / v.length);
}

// --- sRGB ---
export function srgbToLinear(v) {
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}
export function linearToSrgb(v) {
  v = v < 0 ? 0 : v > 1 ? 1 : v;
  return v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055;
}
export function mapImage(im, f) {
  const out = img(im.w, im.h, im.c), d = im.data, o = out.data;
  for (let i = 0; i < d.length; i++) o[i] = f(d[i]);
  return out;
}
export const toSrgb = (im) => mapImage(im, linearToSrgb);
export const toLinear = (im) => mapImage(im, (v) => srgbToLinear(v < 0 ? 0 : v > 1 ? 1 : v));

// --- ponte OpenCV.js ---
export function toMat(cv, im) {
  const type = [0, cv.CV_32FC1, cv.CV_32FC2, cv.CV_32FC3][im.c];
  const m = new cv.Mat(im.h, im.w, type);
  m.data32F.set(im.data);
  return m;
}
export function fromMat(m) {
  const c = m.channels();
  return img(m.cols, m.rows, c, new Float32Array(m.data32F));
}
/** Esegue f(src, dst) su Mat temporanei e restituisce l'immagine risultato. */
export function cvOp(cv, im, f) {
  const src = toMat(cv, im), dst = new cv.Mat();
  try { f(src, dst); return fromMat(dst); } finally { src.delete(); dst.delete(); }
}
export function gaussian(cv, im, sigma) {
  return cvOp(cv, im, (s, d) => cv.GaussianBlur(s, d, new cv.Size(0, 0), sigma, sigma, cv.BORDER_DEFAULT));
}
export function resizeArea(cv, im, w, h) {
  return cvOp(cv, im, (s, d) => cv.resize(s, d, new cv.Size(w, h), 0, 0, cv.INTER_AREA));
}
