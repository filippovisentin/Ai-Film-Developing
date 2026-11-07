// Port di filmengine/calibration.py
import { img, crop, gaussian, channelPercentiles, percentile, median, pyRound } from "./core.js";

const EPS = 1e-4;
const BARE_LIGHT = 0.97;
const LIGHT_CLIP_LEVEL = 0.99;
const LIGHT_CLIP_FRACTION = 0.005;

export function correctLight(cv, im, light) {
  if (!light) return im;
  if (light.w !== im.w || light.h !== im.h) {
    throw new Error(`La foto della luce ha dimensioni ${light.w}x${light.h}, il fotogramma ${im.w}x${im.h}: ` +
      "scattale con lo stesso orientamento e la stessa risoluzione");
  }
  const sigma = Math.max(1, 0.02 * Math.min(light.w, light.h));
  const blurred = gaussian(cv, light, sigma);
  const norm = channelPercentiles(blurred, 99);
  const out = img(im.w, im.h, 3), d = im.data, b = blurred.data, o = out.data;
  for (let i = 0; i < d.length; i++) {
    const f = Math.max(b[i] / Math.max(norm[i % 3], EPS), EPS);
    o[i] = d[i] / f;
  }
  return out;
}

export function measureBase(baseImg) {
  const { w, h } = baseImg;
  const c = crop(baseImg, Math.floor(h / 4), h - Math.floor(h / 4), Math.floor(w / 4), w - Math.floor(w / 4));
  return [0, 1, 2].map((k) => {
    const v = new Float32Array(c.w * c.h);
    for (let i = 0; i < v.length; i++) v[i] = c.data[i * 3 + k];
    return Math.max(median(v), EPS);
  });
}

export function estimateBaseFromBorder(im) {
  const { w, h } = im;
  const b = Math.max(1, pyRound(0.05 * Math.min(h, w)));
  const px = [];
  const push = (y, x) => { const i = (y * w + x) * 3; px.push(im.data[i], im.data[i + 1], im.data[i + 2]); };
  for (let y = 0; y < b; y++) for (let x = 0; x < w; x++) push(y, x);
  for (let y = h - b; y < h; y++) for (let x = 0; x < w; x++) push(y, x);
  for (let y = 0; y < h; y++) for (let x = 0; x < b; x++) push(y, x);
  for (let y = 0; y < h; y++) for (let x = w - b; x < w; x++) push(y, x);
  const n = px.length / 3;
  let film = [];
  for (let i = 0; i < n; i++) {
    if (!(px[3 * i] >= BARE_LIGHT && px[3 * i + 1] >= BARE_LIGHT && px[3 * i + 2] >= BARE_LIGHT)) film.push(i);
  }
  if (!film.length) film = Array.from({ length: n }, (_, i) => i);
  return [0, 1, 2].map((k) => {
    const v = new Float32Array(film.length);
    film.forEach((i, j) => (v[j] = px[3 * i + k]));
    return Math.max(percentile(v, 99.5), EPS);
  });
}

export function lightIsClipped(light) {
  const n = light.w * light.h, d = light.data;
  let clipped = 0;
  for (let i = 0; i < n; i++) {
    if (d[3 * i] >= LIGHT_CLIP_LEVEL || d[3 * i + 1] >= LIGHT_CLIP_LEVEL || d[3 * i + 2] >= LIGHT_CLIP_LEVEL) clipped++;
  }
  return clipped / n > LIGHT_CLIP_FRACTION;
}
