// Reproducible visual comparison using only JPEGs already shipped with the site.
// These are not the private/raw fixtures and cannot reproduce the historical ΔE.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import jpeg from "jpeg-js";
import { img, srgbToLinear, linearToSrgb } from "../src/engine/core.js";
import { developFrame } from "../src/engine/pipeline.js";

const require = createRequire(import.meta.url), root = new URL("../src/", import.meta.url);
const { cv } = await new Promise((resolve, reject) => {
  const cv = require("@techstark/opencv-js"), started = Date.now();
  const wait = () => cv.Mat ? resolve({ cv }) : Date.now() - started > 60000 ? reject(new Error("OpenCV timeout")) : setTimeout(wait, 20);
  wait();
});
const gallery = JSON.parse(readFileSync(new URL("data/gallery.json", root)));
const outDir = new URL("img/color/", root);
mkdirSync(outDir, { recursive: true });
const results = [];
for (const f of gallery.fotogrammi) {
  const decoded = jpeg.decode(readFileSync(new URL(`img/g/${f.telefono}`, root)), { useTArray: true });
  const input = img(decoded.width, decoded.height, 3);
  for (let i = 0, j = 0; i < decoded.data.length; i += 4, j += 3) {
    for (let k = 0; k < 3; k++) input.data[j + k] = srgbToLinear(decoded.data[i + k] / 255);
  }
  const profile = JSON.parse(readFileSync(new URL(`../../profiles/${f.profilo}.json`, import.meta.url)));
  const record = { id: f.id, film: f.pellicola, source: f.telefono, profile: f.profilo };
  for (const colorMode of ["legacy", "natural"]) {
    const { positive, warnings } = developFrame(cv, input, { profile, colorMode });
    const rgba = new Uint8Array(positive.w * positive.h * 4);
    for (let i = 0, j = 0; i < positive.data.length; i += 3, j += 4) {
      for (let k = 0; k < 3; k++) rgba[j + k] = Math.round(255 * linearToSrgb(positive.data[i + k]));
      rgba[j + 3] = 255;
    }
    const file = `${f.id}_${colorMode}.jpg`;
    writeFileSync(new URL(file, outDir), jpeg.encode({ width: positive.w, height: positive.h, data: rgba }, 94).data);
    record[colorMode] = file;
    record.width = positive.w; record.height = positive.h;
    record.warnings = warnings;
  }
  results.push(record);
  console.log(f.id, `${record.width}×${record.height}`);
}
writeFileSync(new URL("data/color-comparison.json", root), JSON.stringify({
  schema: 1, input: "Included simulated-phone JPEGs; automatic border calibration; no denoising or AI.",
  qualityClaim: "Visual experiment only. Historical gallery metrics do not apply to these renders.",
  frames: results,
}, null, 2) + "\n");
console.log(`Wrote ${results.length} pairs to ${fileURLToPath(outDir)}`);
