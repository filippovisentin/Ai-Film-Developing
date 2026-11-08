// Port di filmengine/invert.py: inversione in densità, curve della carta e livelli.
import { img, crop, channelPercentiles, median, percentile } from "./core.js";

const RATIO_MIN = 1e-5, MIN_SPAN = 1e-3, MAX_SAMPLES = 200000;
const LOW_PCT = 0.5, HIGH_PCT = 99.5, EDGE_IGNORE_FRAC = 0.02;
const LUMA = [0.2126, 0.7152, 0.0722];
const AE_POWER_RANGE = [0.5, 2.0];

export function toDensity(im, base) {
  const out = img(im.w, im.h, 3), d = im.data, o = out.data;
  for (let i = 0; i < d.length; i++) {
    const r = Math.min(Math.max(d[i] / Math.fround(base[i % 3]), RATIO_MIN), 1.0);
    o[i] = -Math.log10(r);
  }
  return out;
}

function logExposure(x, profile) {
  const out = img(x.w, x.h, 3), d = x.data, o = out.data;
  if (profile.type === "slide") {
    for (let i = 0; i < d.length; i++) o[i] = Math.log10(Math.min(Math.max(d[i], RATIO_MIN), 1.0));
    return out;
  }
  const g = profile.gamma_rgb;
  for (let i = 0; i < d.length; i++) o[i] = d[i] / Math.fround(g[i % 3]);
  if (profile.type === "bw_negative") {
    for (let i = 0; i < d.length; i += 3) {
      const m = (o[i] + o[i + 1] + o[i + 2]) / 3;
      o[i] = o[i + 1] = o[i + 2] = m;
    }
  }
  return out;
}

function frameCore(im) {
  const my = Math.trunc(EDGE_IGNORE_FRAC * im.h), mx = Math.trunc(EDGE_IGNORE_FRAC * im.w);
  if (im.h - 2 * my > 10 && im.w - 2 * mx > 10) return crop(im, my, im.h - my, mx, im.w - mx);
  return im;
}

function framePercentiles(lexp) {
  const core = frameCore(lexp);
  const step = Math.max(1, Math.floor((core.w * core.h) / MAX_SAMPLES));
  return [channelPercentiles(core, LOW_PCT, step), channelPercentiles(core, HIGH_PCT, step)];
}

export function computeRollLevels(densities, profile) {
  if (!densities.length) throw new Error("Il rullino non contiene fotogrammi");
  const pct = densities.map((d) => framePercentiles(logExposure(d, profile)));
  const med = (j) => [0, 1, 2].map((k) => median(Float64Array.from(pct.map((p) => p[j][k]))));
  return { low: med(0), high: med(1) };
}

export function gamutMap(im) {
  const out = img(im.w, im.h, 3), d = im.data, o = out.data;
  for (let i = 0; i < d.length; i += 3) {
    const r = d[i], g = d[i + 1], b = d[i + 2];
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    if (mx <= 1 && mn >= 0) { o[i] = r; o[i + 1] = g; o[i + 2] = b; continue; }
    const lum = r * LUMA[0] + g * LUMA[1] + b * LUMA[2];
    let t = 1;
    if (mx > 1) t = Math.min(t, (1 - lum) / Math.max(mx - lum, 1e-6));
    if (mn < 0) t = Math.min(t, lum / Math.max(lum - mn, 1e-6));
    t = Math.min(Math.max(t, 0), 1);
    const l = Math.min(Math.max(lum, 0), 1);
    for (let k = 0; k < 3; k++) o[i + k] = Math.min(Math.max(l + t * (d[i + k] - lum), 0), 1);
  }
  return out;
}

function autoExpose(n, strength, target) {
  const my = Math.trunc(EDGE_IGNORE_FRAC * n.h), mx = Math.trunc(EDGE_IGNORE_FRAC * n.w);
  const core = crop(n, my, n.h - my || n.h, mx, n.w - mx || n.w);
  const size = core.w * core.h, step = Math.max(1, Math.floor(size / MAX_SAMPLES));
  const v = new Float32Array(Math.ceil(size / step));
  for (let i = 0, j = 0; i < size; i += step, j++) {
    v[j] = (core.data[3 * i] + core.data[3 * i + 1] + core.data[3 * i + 2]) / 3;
  }
  const m = Math.min(Math.max(median(v), 0.05), 0.95);
  const goal = Math.exp((1 - strength) * Math.log(m) + strength * Math.log(target));
  const p = Math.min(Math.max(Math.log(goal) / Math.log(m), AE_POWER_RANGE[0]), AE_POWER_RANGE[1]);
  const out = img(n.w, n.h, 3);
  for (let i = 0; i < n.data.length; i++) out.data[i] = n.data[i] ** p;
  return out;
}

export function renderPositive(dens, profile, levels, { colorMode = "legacy" } = {}) {
  if (colorMode !== "legacy" && colorMode !== "natural") throw new Error("Unknown color mode");
  if (colorMode === "natural" && profile.type === "color_negative") return renderNatural(dens, profile);
  const lexp = logExposure(dens, profile);
  let low = levels.low, high = levels.high;
  if (profile.frame_balance > 0) {
    const [fl, fh] = framePercentiles(lexp), w = profile.frame_balance;
    low = low.map((v, k) => (1 - w) * v + w * fl[k]);
    high = high.map((v, k) => (1 - w) * v + w * fh[k]);
  }
  const span = [0, 1, 2].map((k) => Math.max(high[k] - low[k], MIN_SPAN));
  let n = img(lexp.w, lexp.h, 3);
  for (let i = 0; i < lexp.data.length; i++) {
    const k = i % 3;
    n.data[i] = Math.min(Math.max((lexp.data[i] - low[k]) / span[k], 0), 1);
  }
  if (profile.auto_exposure > 0) n = autoExpose(n, profile.auto_exposure, profile.exposure_target ?? 0.5);
  const kS = profile.s_curve || 0;
  const lo = 1 / (1 + Math.exp(kS / 2)), hi = 1 / (1 + Math.exp(-kS / 2));
  const rng = profile.paper_range != null ? [profile.paper_range, profile.paper_range, profile.paper_range] : span;
  const M = profile.color_matrix, pc = profile.print_contrast;
  const out = img(n.w, n.h, 3), p = [0, 0, 0];
  for (let i = 0; i < n.data.length; i += 3) {
    for (let k = 0; k < 3; k++) {
      let g = n.data[i + k];
      if (kS > 0) g = (1 / (1 + Math.exp(-kS * (g - 0.5))) - lo) / (hi - lo);
      p[k] = (10 ** ((g - 1) * rng[k])) ** pc;
    }
    for (let r = 0; r < 3; r++) out.data[i + r] = M[r][0] * p[0] + M[r][1] * p[1] + M[r][2] * p[2];
  }
  return gamutMap(out);
}

/** Experimental scene rendering. One luminance curve, rather than three automatic
 * channel stretches. Calibrated RGB ratios survive tone mapping until gamut mapping.
 * No gray-world white balance: a warm scene is allowed to remain warm.
 * It deliberately does not reuse roll/frame RGB endpoints from the legacy renderer.
 */
function renderNatural(dens, profile) {
  const lexp = logExposure(dens, profile), scene = img(dens.w, dens.h, 3);
  const logs = img(dens.w, dens.h, 1), M = profile.color_matrix;
  // Common anchor limits exponent size without changing RGB ratios.
  let anchor = -Infinity;
  for (const v of lexp.data) anchor = Math.max(anchor, v);
  const p = [0, 0, 0];
  for (let i = 0, j = 0; i < scene.data.length; i += 3, j++) {
    for (let k = 0; k < 3; k++) p[k] = 10 ** (lexp.data[i + k] - anchor);
    for (let k = 0; k < 3; k++) scene.data[i + k] = Math.max(0, M[k][0] * p[0] + M[k][1] * p[1] + M[k][2] * p[2]);
    const y = scene.data[i] * LUMA[0] + scene.data[i + 1] * LUMA[1] + scene.data[i + 2] * LUMA[2];
    logs.data[j] = Math.log10(Math.max(y, 1e-20));
  }
  const core = frameCore(logs), step = Math.max(1, Math.floor(core.data.length / MAX_SAMPLES));
  const samples = Float32Array.from({ length: Math.ceil(core.data.length / step) }, (_, i) => core.data[i * step]);
  const low = percentile(samples, LOW_PCT), high = percentile(samples, HIGH_PCT);
  // Do not amplify tiny density differences (noise) into full contrast on flat frames.
  const span = Math.max(high - low, 0.25);
  const clamp = (v) => Math.min(Math.max(v, 0), 1);
  const mid = Math.min(Math.max((median(samples) - low) / span, 0.05), 0.95);
  const strength = profile.auto_exposure || 0;
  const goal = Math.exp((1 - strength) * Math.log(mid) + strength * Math.log(profile.exposure_target ?? 0.5));
  const power = Math.min(Math.max(Math.log(goal) / Math.log(mid), AE_POWER_RANGE[0]), AE_POWER_RANGE[1]);
  const kS = profile.s_curve || 0, lo = 1 / (1 + Math.exp(kS / 2)), hi = 1 / (1 + Math.exp(-kS / 2));
  const range = profile.paper_range ?? span;
  const out = img(dens.w, dens.h, 3);
  for (let i = 0, j = 0; i < out.data.length; i += 3, j++) {
    let n = clamp((logs.data[j] - low) / span) ** power;
    if (kS > 0) n = (1 / (1 + Math.exp(-kS * (n - 0.5))) - lo) / (hi - lo);
    const target = 10 ** ((n - 1) * range * profile.print_contrast);
    const y = Math.max(scene.data[i] * LUMA[0] + scene.data[i + 1] * LUMA[1] + scene.data[i + 2] * LUMA[2], 1e-20);
    for (let k = 0; k < 3; k++) out.data[i + k] = scene.data[i + k] * target / y;
  }
  return gamutMap(out);
}
