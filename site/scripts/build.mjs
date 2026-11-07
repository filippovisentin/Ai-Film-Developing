// Assembla il sito statico in site/dist (Cloudflare Pages: comando "npm run build", cartella "dist").
// - pagine, stile, script e motore da site/src
// - profili pellicola da profiles/*.json
// - OpenCV.js e ONNX Runtime Web da node_modules
// - modello Real-ESRGAN General x4v3 (Qualcomm AI Hub, BSD-3-Clause), scaricato e verificato con SHA-256
import { cpSync, mkdirSync, rmSync, readdirSync, readFileSync, writeFileSync, existsSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { inflateRawSync } from "node:zlib";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = join(SITE, "..");
const DIST = join(SITE, "dist");
const CACHE = join(SITE, ".cache");

const MODEL_URL = "https://qaihub-public-assets.s3.us-west-2.amazonaws.com/qai-hub-models/models/" +
  "real_esrgan_general_x4v3/releases/v0.66.0/real_esrgan_general_x4v3-onnx-float.zip";
const MODEL_SHA256 = "fc094329b24a00c936ebc1cc4c51bc59633e7dc36f4a553344342171cbd3c7cf"; // come tools/get_model.py
const MODEL_FILES = ["real_esrgan_general_x4v3.onnx", "real_esrgan_general_x4v3.data"];

const NAMES_EN = {
  generic_color: "Generic colour negative",
  generic_bw: "Generic black-and-white negative",
  kodak_gold_100: "Kodak Gold 100 (preliminary calibration)",
};

/** Estrae dallo zip solo i file voluti (formato zip: directory centrale in fondo al file). */
function unzip(buf, wanted) {
  const out = {};
  let eocd = buf.length - 22;
  while (eocd >= 0 && buf.readUInt32LE(eocd) !== 0x06054b50) eocd--;
  if (eocd < 0) throw new Error("zip non valido");
  let p = buf.readUInt32LE(eocd + 16);
  const n = buf.readUInt16LE(eocd + 10);
  for (let i = 0; i < n; i++) {
    const method = buf.readUInt16LE(p + 10), csize = buf.readUInt32LE(p + 20);
    const nlen = buf.readUInt16LE(p + 28), elen = buf.readUInt16LE(p + 30), clen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42);
    const name = buf.toString("utf8", p + 46, p + 46 + nlen).split("/").pop();
    if (wanted.includes(name)) {
      const start = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
      const data = buf.subarray(start, start + csize);
      out[name] = method === 0 ? Buffer.from(data) : method === 8 ? inflateRawSync(data) : null;
      if (!out[name]) throw new Error(`compressione non supportata (${method}) per ${name}`);
    }
    p += 46 + nlen + elen + clen;
  }
  return out;
}

async function model() {
  const dir = join(CACHE, "model");
  if (MODEL_FILES.every((f) => existsSync(join(dir, f)))) return dir;
  console.log("scarico il modello AI:", MODEL_URL);
  const res = await fetch(MODEL_URL);
  if (!res.ok) throw new Error(`download del modello non riuscito: ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  const digest = createHash("sha256").update(buf).digest("hex");
  if (digest !== MODEL_SHA256) throw new Error(`impronta del modello errata (${digest}): file rifiutato`);
  const files = unzip(buf, MODEL_FILES);
  mkdirSync(dir, { recursive: true });
  for (const f of MODEL_FILES) {
    if (!files[f]) throw new Error(`${f} assente nello zip`);
    writeFileSync(join(dir, f), files[f]);
  }
  return dir;
}

function size(dir) {
  let s = 0;
  for (const e of readdirSync(dir, { withFileTypes: true })) s += e.isDirectory() ? size(join(dir, e.name)) : statSync(join(dir, e.name)).size;
  return s;
}

rmSync(DIST, { recursive: true, force: true });
cpSync(join(SITE, "src"), DIST, { recursive: true });

const profiles = readdirSync(join(ROOT, "profiles")).filter((f) => f.endsWith(".json")).sort().map((f) => {
  const p = JSON.parse(readFileSync(join(ROOT, "profiles", f), "utf8"));
  return { ...p, name_en: NAMES_EN[p.id] || p.name };
});
mkdirSync(join(DIST, "data"), { recursive: true });
writeFileSync(join(DIST, "data", "profiles.json"), JSON.stringify(profiles));

const vendor = join(DIST, "vendor");
mkdirSync(vendor, { recursive: true });
cpSync(join(SITE, "node_modules/@techstark/opencv-js/dist/opencv.js"), join(vendor, "opencv.js"));
for (const f of ["ort.wasm.min.js", "ort-wasm-simd-threaded.mjs", "ort-wasm-simd-threaded.wasm"]) {
  cpSync(join(SITE, "node_modules/onnxruntime-web/dist", f), join(vendor, f));
}

const mdir = await model();
mkdirSync(join(DIST, "models"), { recursive: true });
for (const f of MODEL_FILES) cpSync(join(mdir, f), join(DIST, "models", f));
writeFileSync(join(DIST, "models", "LICENSE.txt"),
  "Real-ESRGAN General x4v3, ONNX export by Qualcomm AI Hub (https://huggingface.co/qualcomm/Real-ESRGAN-General-x4v3).\n" +
  "License: BSD-3-Clause. Source: " + MODEL_URL + "\nSHA-256 of the release zip: " + MODEL_SHA256 + "\n");

// Cloudflare Pages rifiuta file oltre 25 MiB
for (const dir of [DIST]) {
  const walk = (d) => readdirSync(d, { withFileTypes: true }).forEach((e) => {
    const p = join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (statSync(p).size > 25 * 1024 * 1024) throw new Error(`file troppo grande per Cloudflare Pages: ${p}`);
  });
  walk(dir);
}
console.log(`dist pronto: ${(size(DIST) / 1e6).toFixed(1)} MB`);
