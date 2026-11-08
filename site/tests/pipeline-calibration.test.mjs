import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { img } from "../src/engine/core.js";
import { developFrame } from "../src/engine/pipeline.js";

const require = createRequire(import.meta.url);
const profile = JSON.parse(readFileSync(new URL("../../profiles/generic_color.json", import.meta.url)));
const { cv } = await new Promise((resolve, reject) => {
  const cv = require("@techstark/opencv-js"), start = Date.now();
  const wait = () => cv.Mat ? resolve({ cv }) : Date.now() - start > 30000 ? reject(new Error("OpenCV timeout")) : setTimeout(wait, 20);
  wait();
});
test("a separately framed film-edge photo can have different dimensions from the light field", () => {
  const negative = img(32, 24, 3), light = img(32, 24, 3), baseImg = img(16, 12, 3);
  for (let i = 0; i < light.data.length; i++) light.data[i] = 0.8;
  for (let i = 0; i < baseImg.data.length; i++) baseImg.data[i] = [0.8, 0.5, 0.32][i % 3];
  for (let i = 0; i < negative.data.length; i++) negative.data[i] = [0.8, 0.5, 0.32][i % 3] * (0.05 + 0.7 * Math.floor(i / 3) / (32 * 24));
  for (const colorMode of ["legacy", "natural"]) {
    const out = developFrame(cv, negative, { profile, baseImg, light, crop: false, colorMode });
    assert.ok(out.positive.data.every((v) => Number.isFinite(v) && v >= 0 && v <= 1));
  }
  assert.throws(() => developFrame(cv, negative, { profile, light: img(16, 12, 3), crop: false }), /dimensioni/);
  assert.throws(() => developFrame(cv, negative, { profile, baseImg, light, baseFraming: "negative", crop: false }), /dimensioni/);
});
