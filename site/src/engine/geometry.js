// Port di filmengine/geometry.py: rilevamento del fotogramma, raddrizzamento e ritaglio.
import { img, crop, meanChannels, median, percentile, stdOf, pyRound, gaussian, resizeArea, toMat, fromMat } from "./core.js";

const MIN_AREA_FRACTION = 0.20;
const MIN_RECT_FILL = 0.90;
const INNER_MIN_FRACTION = 0.5;
const INNER_MAX_FRACTION = 0.85;
const RECT_SIDE_TOL = 0.10;
const RECT_ANGLE_TOL = 8.0;
const ASPECT_SNAP = 0.035;

const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

function isRectangular(q) {
  const sides = [0, 1, 2, 3].map((i) => dist(q[(i + 1) % 4], q[i]));
  for (const [a, b] of [[sides[0], sides[2]], [sides[1], sides[3]]]) {
    if (Math.abs(a - b) > RECT_SIDE_TOL * Math.max(a, b)) return false;
  }
  for (let i = 0; i < 4; i++) {
    const p = q[(i + 3) % 4], c = q[i], n = q[(i + 1) % 4];
    const u = [p[0] - c[0], p[1] - c[1]], v = [n[0] - c[0], n[1] - c[1]];
    const cos = (u[0] * v[0] + u[1] * v[1]) / Math.max(Math.hypot(...u) * Math.hypot(...v), 1e-6);
    const ang = (Math.acos(Math.min(1, Math.max(-1, cos))) * 180) / Math.PI;
    if (Math.abs(ang - 90) > RECT_ANGLE_TOL) return false;
  }
  return true;
}

function inside(cv, inner, outer, tol = 3.0) {
  const poly = cv.matFromArray(4, 1, cv.CV_32FC2, outer.flat());
  try {
    return inner.every(([x, y]) => cv.pointPolygonTest(poly, new cv.Point(x, y), true) >= -tol);
  } finally { poly.delete(); }
}

function order(pts) {
  const f = Math.fround;
  let iMinS = 0, iMaxS = 0, iMinD = 0, iMaxD = 0;
  const s = pts.map((p) => f(p[0] + p[1])), d = pts.map((p) => f(p[1] - p[0]));
  for (let i = 1; i < pts.length; i++) {
    if (s[i] < s[iMinS]) iMinS = i;
    if (s[i] > s[iMaxS]) iMaxS = i;
    if (d[i] < d[iMinD]) iMinD = i;
    if (d[i] > d[iMaxD]) iMaxD = i;
  }
  return [pts[iMinS], pts[iMinD], pts[iMaxS], pts[iMaxD]].map((p) => [f(p[0]), f(p[1])]);
}

function otsu(cv, values) {
  const m = cv.matFromArray(1, values.length, cv.CV_8UC1, values), dst = new cv.Mat();
  try { return cv.threshold(m, dst, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU); }
  finally { m.delete(); dst.delete(); }
}

function touchesBorder(cv, c, w, h, margin = 2) {
  const r = cv.boundingRect(c);
  return r.x <= margin || r.y <= margin || r.x + r.width >= w - margin || r.y + r.height >= h - margin;
}

function quad(cv, c) {
  const approx = new cv.Mat();
  try {
    cv.approxPolyDP(c, approx, 0.02 * cv.arcLength(c, true), true);
    if (approx.rows === 4 && cv.isContourConvex(approx)) {
      const a = approx.data32S;
      return [order([[a[0], a[1]], [a[2], a[3]], [a[4], a[5]], [a[6], a[7]]]), true];
    }
  } finally { approx.delete(); }
  const rect = cv.minAreaRect(c);
  if (cv.contourArea(c) / Math.max(rect.size.width * rect.size.height, 1.0) >= MIN_RECT_FILL) {
    const pts = cv.RotatedRect.points(rect).map((p) => [p.x, p.y]);
    return [order(pts), false];
  }
  return null;
}

/** Cerca il fotogramma: la zona scura più grande che non tocca i bordi della foto. */
export function findFrameCorners(cv, im) {
  const { w, h } = im;
  const mean = meanChannels(im).data;
  const lum = new Float32Array(w * h);
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i < lum.length; i++) {
    const v = Math.log10(Math.max(mean[i], 1e-4));
    lum[i] = v;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (Math.fround(hi - lo) < 1e-3) return null;
  const scale = 255 / (hi - lo);
  const raw8 = new Uint8Array(lum.length);
  for (let i = 0; i < lum.length; i++) raw8[i] = Math.max(0, Math.min(255, Math.trunc(Math.fround((lum[i] - lo) * scale))));
  const m8 = cv.matFromArray(h, w, cv.CV_8UC1, raw8), b8 = new cv.Mat();
  const s = Math.max(1.0, 0.003 * Math.min(h, w));
  cv.GaussianBlur(m8, b8, new cv.Size(0, 0), s, s, cv.BORDER_DEFAULT);
  const lum8 = new Uint8Array(b8.data);
  m8.delete();
  b8.delete();

  const t1 = otsu(cv, lum8);
  const thresholds = new Set([t1]);
  for (const below of [true, false]) {
    const part = lum8.filter((v) => (below ? v <= t1 : v > t1));
    if (part.length) {
      let mn = 255, mx = 0;
      for (const v of part) { if (v < mn) mn = v; if (v > mx) mx = v; }
      if (mn !== mx) thresholds.add(otsu(cv, part));
    }
  }
  const minArea = MIN_AREA_FRACTION * h * w;
  const candidates = [];
  const kernel = cv.Mat.ones(5, 5, cv.CV_8U);
  const maskData = new Uint8Array(w * h);
  for (const t of [...thresholds].sort((a, b) => a - b)) {
    for (let i = 0; i < lum8.length; i++) maskData[i] = lum8[i] <= t ? 255 : 0;
    const mask = cv.matFromArray(h, w, cv.CV_8UC1, maskData), closed = new cv.Mat();
    cv.morphologyEx(mask, closed, cv.MORPH_CLOSE, kernel);
    const contours = new cv.MatVector(), hier = new cv.Mat();
    cv.findContours(closed, contours, hier, cv.RETR_CCOMP, cv.CHAIN_APPROX_SIMPLE);
    const n = contours.size(), H = hier.data32S;
    const pick = [];
    for (let i = 0; i < n; i++) if (H[4 * i + 3] === -1) pick.push(i);
    for (let i = 0; i < n; i++) {
      if (H[4 * i + 3] !== -1) continue;
      const c = contours.get(i);
      const touches = touchesBorder(cv, c, w, h);
      c.delete();
      if (!touches) continue;
      let child = H[4 * i + 2];
      while (child !== -1) { pick.push(child); child = H[4 * child]; }
    }
    for (const i of pick) {
      const c = contours.get(i);
      const area = cv.contourArea(c);
      if (area >= minArea && !touchesBorder(cv, c, w, h)) {
        const q = quad(cv, c);
        if (q) candidates.push([area, q[0], q[1]]);
      }
      c.delete();
    }
    mask.delete(); closed.delete(); contours.delete(); hier.delete();
  }
  kernel.delete();
  if (!candidates.length) return null;
  candidates.sort((a, b) => b[0] - a[0]);
  let [bestArea, best] = candidates[0];
  for (const [area, q, clean] of candidates.slice(1)) {
    if (clean && isRectangular(q) && INNER_MIN_FRACTION * bestArea <= area && area <= INNER_MAX_FRACTION * bestArea &&
        inside(cv, q, best)) {
      bestArea = area;
      best = q;
    }
  }
  return best;
}

/** Raddrizza il quadrilatero; il formato 3:2 si impone solo se quello misurato è vicino. */
export function warpFrame(cv, im, corners, aspect = 1.5) {
  const [tl, tr, br, bl] = corners;
  const width = Math.max(dist(tr, tl), dist(br, bl));
  const height = Math.max(dist(bl, tl), dist(br, tr));
  const measured = Math.max(width, height) / Math.max(Math.min(width, height), 1.0);
  const ratio = aspect !== null && Math.abs(measured / aspect - 1) <= ASPECT_SNAP ? aspect : measured;
  let ow, oh;
  if (width >= height) { ow = pyRound(width); oh = pyRound(width / ratio); }
  else { oh = pyRound(height); ow = pyRound(height / ratio); }
  const src = cv.matFromArray(4, 1, cv.CV_32FC2, corners.flat());
  const dst = cv.matFromArray(4, 1, cv.CV_32FC2, [0, 0, ow - 1, 0, ow - 1, oh - 1, 0, oh - 1]);
  const M = cv.getPerspectiveTransform(src, dst);
  const a = toMat(cv, im), out = new cv.Mat();
  try {
    cv.warpPerspective(a, out, M, new cv.Size(ow, oh), cv.INTER_LINEAR, cv.BORDER_REPLICATE, new cv.Scalar());
    return fromMat(out);
  } finally { [src, dst, M, a, out].forEach((m) => m.delete()); }
}

// righe/colonne lette dal lato indicato verso l'interno
function lineReader(lum, side) {
  const { w, h, data } = lum;
  const vertical = side === "top" || side === "bottom";
  const count = vertical ? h : w, len = vertical ? w : h;
  const get = (i) => {
    const out = new Float32Array(len);
    if (vertical) {
      const y = side === "top" ? i : h - 1 - i;
      out.set(data.subarray(y * w, y * w + w));
    } else {
      const x = side === "left" ? i : w - 1 - i;
      for (let y = 0; y < h; y++) out[y] = data[y * w + x];
    }
    return out;
  };
  return { count, get };
}

const DARK_EDGE_RATIO = 0.25, DARK_EDGE_MAX_FRAC = 0.05, DARK_EDGE_OUTER_FRAC = 0.02, DARK_EDGE_SOFT = 2.0;

/** Rifila le strisce quasi nere sui bordi (porta-negativi, bordo dello scanner). */
export function trimDarkEdges(im, ratio = DARK_EDGE_RATIO, maxFrac = DARK_EDGE_MAX_FRAC) {
  const lum = meanChannels(im);
  const limit = ratio * median(lum.data);
  const count = (side) => {
    const r = lineReader(lum, side);
    const n = Math.trunc(maxFrac * r.count);
    const outer = Math.max(2, Math.trunc(DARK_EDGE_OUTER_FRAC * r.count));
    const L = Math.min(n + 1, r.count);
    let k = 0, seen = false;
    for (let i = 0; i < L; i++) {
      const med = median(r.get(i));
      const dark = med < limit, soft = med < DARK_EDGE_SOFT * limit;
      if (dark) seen = true;
      else if (!(soft && i < outer && !seen)) break;
      k = i + 1;
    }
    return seen && k <= n ? k : 0;
  };
  const top = count("top"), bottom = count("bottom"), left = count("left"), right = count("right");
  return crop(im, top, im.h - bottom, left, im.w - right);
}

const REBATE_MAX_FRAC = 0.15, REBATE_UNIFORMITY = 0.02, REBATE_BRIGHTNESS = 0.9, REBATE_LEVEL_TOL = 0.03,
  REBATE_OUTER_FRAC = 0.02, REBATE_SAFETY_FRAC = 0.005, REBATE_SAFETY_MIN_PX = 4;

/** Rifila il bordo non esposto della pellicola rimasto nel ritaglio. */
export function trimRebateEdges(cv, im, maxFrac = REBATE_MAX_FRAC) {
  const lum = gaussian(cv, meanChannels(im), 1.5);
  const { w, h } = lum;
  const oh = Math.max(2, Math.trunc(REBATE_OUTER_FRAC * h)), ow = Math.max(2, Math.trunc(REBATE_OUTER_FRAC * w));
  const bright = REBATE_BRIGHTNESS * percentile(crop(lum, oh, h - oh, ow, w - ow).data, 99.5);
  const count = (side) => {
    const r = lineReader(lum, side);
    const n = Math.trunc(maxFrac * r.count);
    const outer = Math.max(2, Math.trunc(REBATE_OUTER_FRAC * r.count));
    const L = Math.min(n + 1, r.count);
    const med = [], uniform = [];
    for (let i = 0; i < L; i++) {
      const line = r.get(i), m = median(line);
      med.push(m);
      uniform.push(m >= bright && stdOf(line) <= REBATE_UNIFORMITY * Math.max(m, 1e-6));
    }
    let k = 0, seen = false;
    for (let i = 0; i < L; i++) {
      if (uniform[i]) seen = true;
      else if (!(med[i] >= bright && i < outer && !seen)) break;
      k = i + 1;
    }
    if (!seen || k > n) return 0;
    if (k > outer + 2) {
      const ref = median(Float64Array.from(med.slice(outer, outer + Math.max(3, Math.floor((k - outer) / 3)))));
      for (let i = outer; i < k; i++) {
        if (Math.abs(med[i] / ref - 1) > REBATE_LEVEL_TOL) { k = i; break; }
      }
    }
    return Math.min(k + Math.max(REBATE_SAFETY_MIN_PX, pyRound(REBATE_SAFETY_FRAC * r.count)), n);
  };
  const top = count("top"), bottom = count("bottom"), left = count("left"), right = count("right");
  return crop(im, top, h - bottom, left, w - right);
}

/** Riporta al formato nominale un fotogramma che ne differisce di poco. */
export function snapAspect(cv, im, aspect = 1.5) {
  const { w, h } = im;
  const long = Math.max(h, w), short = Math.min(h, w);
  if (Math.abs(long / short / aspect - 1) > ASPECT_SNAP) return im;
  const ns = pyRound(long / aspect);
  return w >= h ? resizeArea(cv, im, long, ns) : resizeArea(cv, im, ns, long);
}

export { img };

export { validateManualCorners, manualCornersToPixels } from "./selection.js";
