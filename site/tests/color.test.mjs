import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { img } from "../src/engine/core.js";
import { computeRollLevels, renderPositive, toDensity } from "../src/engine/invert.js";

const profile = JSON.parse(readFileSync(new URL("../../profiles/generic_color.json", import.meta.url)));
const makeDensity = (chroma = [0, 0, 0]) => {
  const d = img(48, 32, 3);
  for (let i = 0; i < d.w * d.h; i++) {
    const v = 0.15 + 0.8 * i / (d.w * d.h - 1);
    for (let k = 0; k < 3; k++) d.data[3 * i + k] = v + chroma[k];
  }
  return d;
};
const render = (d, p = profile, colorMode = "natural") => renderPositive(d, p, computeRollLevels([d], p), { colorMode });
const difference = (a, b) => a.data.reduce((s, v, i) => s + Math.abs(v - b.data[i]), 0) / a.data.length;

test("natural: a neutral wedge stays neutral, finite and monotonic", () => {
  const out = render(makeDensity());
  let last = -1;
  for (let i = 0; i < out.data.length; i += 3) {
    const [r, g, b] = out.data.subarray(i, i + 3);
    assert.ok(Number.isFinite(r) && r >= 0 && r <= 1);
    assert.ok(Math.abs(r - g) < 1e-6 && Math.abs(r - b) < 1e-6);
    assert.ok(r + 1e-6 >= last); last = r;
  }
});

test("natural: a warm scene is not automatically neutralized", () => {
  const d = makeDensity([0.12, 0, -0.06]), natural = render(d), legacy = render(d, profile, "legacy");
  const i = 3 * Math.floor(d.w * d.h / 2);
  assert.ok(natural.data[i] > natural.data[i + 1] * 1.2);
  assert.ok(natural.data[i + 1] > natural.data[i + 2] * 1.1);
  assert.ok(Math.abs(legacy.data[i] - legacy.data[i + 2]) < 1e-5);
});

test("natural: tone changes preserve in-gamut RGB ratios", () => {
  const d = makeDensity([0.03, 0, -0.03]);
  const a = render(d, { ...profile, print_contrast: 1 });
  const b = render(d, { ...profile, print_contrast: 1.3 });
  const i = 3 * 500;
  assert.ok(Math.abs(a.data[i] / a.data[i + 1] - b.data[i] / b.data[i + 1]) < 1e-5);
  assert.ok(difference(a, b) > 0.005);
});

test("natural: channel gamma and calibrated base affect color", () => {
  const d = makeDensity([0.1, 0, -0.04]);
  assert.ok(difference(render(d), render(d, { ...profile, gamma_rgb: [0.5, 0.6, 0.7] })) > 0.01);
  const neg = img(d.w, d.h, 3);
  for (let i = 0; i < neg.data.length; i++) neg.data[i] = [0.8, 0.5, 0.32][i % 3] * 10 ** -d.data[i];
  assert.ok(difference(render(toDensity(neg, [0.8, 0.5, 0.32])), render(toDensity(neg, [0.9, 0.6, 0.4]))) > 0.005);
});

test("natural: constant and almost-flat frames do not produce NaN or full contrast", () => {
  for (const noise of [0, 1e-6]) {
    const d = img(24, 16, 3);
    for (let i = 0; i < d.data.length; i++) d.data[i] = 0.5 + noise * (i % 2);
    const out = render(d);
    assert.ok(out.data.every((v) => Number.isFinite(v) && v >= 0 && v <= 1));
    assert.ok(Math.max(...out.data) - Math.min(...out.data) < 0.001);
  }
});

test("legacy remains the default and monochrome is unchanged", () => {
  const d = makeDensity(), levels = computeRollLevels([d], profile);
  assert.deepEqual(renderPositive(d, profile, levels), render(d, profile, "legacy"));
  const bw = { ...profile, type: "bw_negative" };
  assert.deepEqual(render(d, bw), render(d, bw, "legacy"));
  assert.throws(() => render(d, profile, "unknown"), /Unknown color mode/);
});
