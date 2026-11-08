// Il motore JavaScript deve dare gli stessi risultati di filmengine (Python).
// Dati: python site/scripts/export_fixtures.py (negativi BlueNeg, Copyrighted by Tien-Tsin Wong).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { img, srgbToLinear, linearToSrgb } from "../src/engine/core.js";
import { developFrame } from "../src/engine/pipeline.js";
import { enhance, superResolve } from "../src/engine/enhance.js";

const require = createRequire(import.meta.url);
const FIX = new URL("./fixtures/", import.meta.url);
const has = existsSync(new URL("meta.json", FIX));
const meta = has ? JSON.parse(readFileSync(new URL("meta.json", FIX), "utf8")) : [];
const profile = (id) => JSON.parse(readFileSync(new URL(`../../profiles/${id}.json`, import.meta.url), "utf8"));

const cvReady = has ? new Promise((resolve) => {
  const cv = require("@techstark/opencv-js");
  const wait = () => (cv.Mat ? resolve({ cv }) : setTimeout(wait, 20)); // cv è "thenable": va incartato
  wait();
}) : null;

test("fixture fotografiche Python disponibili", { skip: has ? false : "Fixture private assenti: eseguire scripts/export_fixtures.py" }, () => {
  assert.ok(meta.length > 0);
});

const LUT = Float32Array.from({ length: 256 }, (_, i) => srgbToLinear(i / 255));
function loadU8(name, [h, w]) {
  const b = readFileSync(new URL(name, FIX));
  const d = new Float32Array(b.length);
  for (let i = 0; i < b.length; i++) d[i] = LUT[b[i]];
  return img(w, h, 3, d);
}
function loadF32(name, [h, w]) {
  const b = readFileSync(new URL(name, FIX));
  return img(w, h, 3, new Float32Array(b.buffer, b.byteOffset, b.length / 4));
}
/** Differenza media e 99° percentile in livelli sRGB 0..255. */
function diff(a, b) {
  assert.equal(`${a.w}x${a.h}`, `${b.w}x${b.h}`, "dimensioni diverse");
  const d = new Float32Array(a.data.length);
  let s = 0;
  for (let i = 0; i < d.length; i++) { d[i] = Math.abs(linearToSrgb(a.data[i]) - linearToSrgb(b.data[i])) * 255; s += d[i]; }
  d.sort();
  return { mean: s / d.length, p99: d[Math.floor(0.99 * d.length)] };
}

for (const m of meta) {
  test(`sviluppo ${m.stem} (${m.profile}) uguale a Python`, async () => {
    const { cv } = await cvReady;
    const neg = loadU8(`${m.stem}_neg.u8`, m.neg);
    // The simulator's base patch shares the negative's spatial light field.
    const opts = { profile: profile(m.profile), baseFraming: "negative" };
    if (m.calib) { opts.light = loadU8(`${m.stem}_light.u8`, m.light); opts.baseImg = loadU8(`${m.stem}_base.u8`, m.base); }
    const t0 = Date.now();
    const { positive, warnings } = developFrame(cv, neg, opts);
    const t1 = Date.now();
    const d = diff(positive, loadF32(`${m.stem}_pos.f32`, m.pos));
    console.log(m.stem, "originale", d, `${t1 - t0} ms`, warnings);
    assert.ok(d.mean < 1.0 && d.p99 < 4, JSON.stringify(d));

    const better = enhance(cv, positive);
    const e = diff(better, loadF32(`${m.stem}_enh.f32`, m.pos));
    console.log(m.stem, "migliorata", e, `${Date.now() - t1} ms`);
    assert.ok(e.mean < 1.5 && e.p99 < 6, JSON.stringify(e));
  });
}

const sr = meta.find((m) => m.sr);
const model = new URL("../../models/real_esrgan_general_x4v3.onnx", import.meta.url);
test("ingrandimento AI uguale a Python", { skip: !sr || !existsSync(model) }, async () => {
  const { cv } = await cvReady;
  const ort = await import("onnxruntime-web");
  ort.env.wasm.numThreads = 1;
  const session = await ort.InferenceSession.create(readFileSync(model), {
    externalData: [{ path: "real_esrgan_general_x4v3.data", data: readFileSync(new URL("../../models/real_esrgan_general_x4v3.data", import.meta.url)) }],
  });
  const out = await superResolve(cv, ort, session, loadF32(`${sr.stem}_srin.f32`, sr.sr), 4);
  const d = diff(out, loadF32(`${sr.stem}_sr.f32`, [sr.sr[0] * 4, sr.sr[1] * 4]));
  console.log("AI x4", d);
  assert.ok(d.mean < 1.0, JSON.stringify(d));
});
