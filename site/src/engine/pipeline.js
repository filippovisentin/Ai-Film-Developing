// Port di filmengine/pipeline.py per un singolo fotogramma (ciò che fa tools/server.py).
import { channelPercentiles } from "./core.js";
import { correctLight, estimateBaseFromBorder, lightIsClipped, measureBase } from "./calibration.js";
import { findFrameCorners, snapAspect, trimDarkEdges, trimRebateEdges, warpFrame } from "./geometry.js";
import { computeRollLevels, renderPositive, toDensity } from "./invert.js";

const BRIGHTER_TOLERANCE = 1.02, FRAME_BASE_PCT = 99.9;

function frameBase(img, base, warnings, t) {
  const brightest = channelPercentiles(img, FRAME_BASE_PCT).map(Math.fround);
  if (brightest.some((v, k) => v > base[k] * BRIGHTER_TOLERANCE)) {
    warnings.push(t("warnBrighter"));
    return base.map((v, k) => Math.max(v, brightest[k]));
  }
  return base;
}

/**
 * Sviluppa un negativo (immagini lineari). Restituisce il positivo lineare e gli avvisi.
 * opts: { light, baseImg, baseFraming="closeup", profile, colorMode="legacy", crop=true, t }
 */
export function developFrame(cv, negative, opts) {
  const { profile, crop = true } = opts;
  const t = opts.t || ((k) => k);
  const warnings = [];
  let light = opts.light || null;
  if (light && lightIsClipped(light)) {
    light = null;
    warnings.push(t("warnLightClipped"));
  }
  let base = null;
  // Equal dimensions do not imply equal framing. A separate edge close-up cannot
  // use the negative's spatial light field. Full-frame fixtures/captures may opt in.
  if (opts.baseImg) base = measureBase(opts.baseFraming === "negative"
    ? correctLight(cv, opts.baseImg, light) : opts.baseImg);

  let img = correctLight(cv, negative, light);
  let candidate = null;
  if (!base && profile.type !== "slide") candidate = estimateBaseFromBorder(img);
  if (crop) {
    const corners = findFrameCorners(cv, img);
    if (!corners) warnings.push(t("warnNoFrame"));
    else img = snapAspect(cv, trimRebateEdges(cv, warpFrame(cv, img, corners)));
  }
  img = trimDarkEdges(img);

  let data = img;
  if (profile.type !== "slide") {
    if (!base) {
      base = candidate;
      warnings.push(t("warnBaseEstimated"));
    }
    data = toDensity(img, frameBase(img, base.map(Math.fround), warnings, t));
  }
  const levels = computeRollLevels([data], profile);
  return { positive: renderPositive(data, profile, levels, { colorMode: opts.colorMode }), warnings };
}
