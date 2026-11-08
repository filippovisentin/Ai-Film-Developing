// Export two self-contained, local HTML review files. No server or model needed.
// Usage: node scripts/export_review.mjs <output-directory>
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

if (!process.argv[2]) throw new Error("Provide an output directory");
const output = resolve(process.argv[2]), src = fileURLToPath(new URL("../src/", import.meta.url));
mkdirSync(output, { recursive: true });
const read = (p) => readFileSync(join(src, p), "utf8");
const mime = (p) => p.endsWith(".svg") ? "image/svg+xml" : "image/jpeg";
const uri = (p) => `data:${mime(p)};base64,${readFileSync(join(src, p)).toString("base64")}`;
const galleryAssets = Object.fromEntries(readdirSync(join(src, "img/g")).map((f) => [f, uri(`img/g/${f}`)]));
const colorAssets = Object.fromEntries(readdirSync(join(src, "img/color")).map((f) => [f, uri(`img/color/${f}`)]));
const common = read("js/common.js").replace(/^export /gm, "");
const withoutImports = (js) => js.replace(/^import .*;\r?\n/gm, "");

for (const page of ["index", "galleria"]) {
  let html = read(`${page}.html`);
  html = html.replace(/<link rel="stylesheet" href="(css\/[^"]+)">/g, (_, p) => `<style>${read(p)}</style>`);
  html = html.replace('<script src="js/lang-boot.js"></script>', `<script>${read("js/lang-boot.js")}</script>`);
  html = html.replace(/\b(src|data-zoom)="(img\/[^"]+)"/g, (_, attr, p) => `${attr}="${uri(p)}"`);
  html = html.replace('href="img/favicon.svg"', `href="${uri("img/favicon.svg")}"`);
  html = html.replace(/href="\.\/"/g, 'href="landing-anteprima.html"')
    .replace(/href="galleria\.html/g, 'href="galleria-anteprima.html')
    .replace(/href="app\.html/g, 'href="https://filippovisentin.github.io/Ai-Film-Developing/app.html');
  let script;
  if (page === "index") script = common + "\n" + withoutImports(read("js/home.js"));
  else {
    let lab = withoutImports(read("js/color-lab.js"))
      .replace('await fetch("data/color-comparison.json")', `({ ok: true, json: async () => (${read("data/color-comparison.json")}) })`)
      .replace('el.src = `img/color/${frame[mode]}`;', 'el.src = reviewColorAssets[frame[mode]];');
    let gallery = withoutImports(read("js/gallery.js"))
      .replace('await (await fetch("data/gallery.json")).json()', `(${read("data/gallery.json")})`)
      .replace('const img = (n) => "img/g/" + n;', 'const img = (n) => reviewGalleryAssets[n];');
    script = `${common}\nconst reviewColorAssets=${JSON.stringify(colorAssets)};\nconst reviewGalleryAssets=${JSON.stringify(galleryAssets)};\n{${lab}}\n${gallery}`;
  }
  script = script.replace(/<\/script/gi, "<\\/script");
  html = html.replace(/<script type="module" src="js\/(home|gallery)\.js"><\/script>/, () => `<script type="module">${script}</script>`);
  const filename = page === "index" ? "landing-anteprima.html" : "galleria-anteprima.html";
  writeFileSync(join(output, filename), html);
  console.log(filename, `${(Buffer.byteLength(html) / 1e6).toFixed(1)} MB`);
}
