// Renders the Hairline copystand figure in the Field Notes palette:
// stills (rest, tilted) and a deterministic frame sequence for the video slide.
//   node social/instagram/drafts/capture_copystand.mjs
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(process.env.LOCALAPPDATA, "hairline-look", "package.json"));
const { chromium } = require("playwright-core");

const PAGE = pathToFileURL(join(here, "hairline-copystand.html")).href;
const OUT = join(here, "phone");
const FRAMES = join(OUT, "frames");
const SIZE = { width: 952, height: 762 };   // the figure box on the slide, 5:4 like the stage

// Field Notes palette on the figure's own variables; the bench's chrome hidden, the stage filling the page.
const STYLE = `
  html, body { margin: 0 !important; padding: 0 !important; background: #F3F3F1 !important; overflow: hidden; }
  main { margin: 0 !important; padding: 0 !important; max-width: none !important; width: ${SIZE.width}px !important; }
  .plate { border: 0 !important; padding: 0 !important; margin: 0 !important; border-radius: 0 !important; background: transparent !important; }
  .controls, #means, #rules, #error, .tag, form, label, input, output, button { display: none !important; }
  [data-hairline], #stage { width: ${SIZE.width}px !important; height: ${SIZE.height}px !important; aspect-ratio: auto !important; }
  [data-hairline] {
    --hl-plate: #F3F3F1 !important; --hl-edge: #111113 !important; --hl-mid: #3a3a40 !important;
    --hl-lo: #9c9ca3 !important; --hl-hi: #2E5BFF !important; --hairline-stroke: 1.5 !important;
  }
  svg .hi { stroke-width: 2.6 !important; }
  svg * { transition: none !important; }
  svg .dash { stroke-dasharray: 2 4 !important; }
`;

async function open(browser, query = "") {
  const page = await browser.newPage({ viewport: SIZE, deviceScaleFactor: 2 });
  await page.clock.install({ time: 0 });
  await page.goto(PAGE + "?theme=light" + query);
  await page.addStyleTag({ content: STYLE });
  await page.clock.runFor(2500);
  return page;
}

/** viewBox point -> page pixel, from the stage's own box. */
async function toPx(page, [x, y]) {
  const b = await page.locator("#stage").boundingBox();
  return [b.x + (x / 400) * b.width, b.y + (y / 320) * b.height];
}

const browser = await chromium.launch({ channel: "chrome" }).catch(() => chromium.launch());
mkdirSync(OUT, { recursive: true });

// stills
for (const [name, at] of [["a-rest", null], ["a-tilt", [345, 170]]]) {
  const page = await open(browser);
  if (at) {
    const [px, py] = await toPx(page, at);
    await page.mouse.move(px, py);
    await page.clock.runFor(3000);
  }
  await page.locator("#stage").screenshot({ path: join(OUT, `${name}.png`) });
  console.log("still", name, await page.locator("#read").textContent());
  await page.close();
}

// the animation: level, tip right, tip left, back to level; 30 fps, the page's clock stepped by hand
rmSync(FRAMES, { recursive: true, force: true });
mkdirSync(FRAMES, { recursive: true });
const FPS = 60;
const keys = [            // [seconds, viewBox point or null for "pointer away"]
  [0.0, null], [1.0, null], [2.6, [345, 168]], [4.2, [345, 168]], [6.2, [52, 204]], [7.8, [52, 204]], [8.8, null], [10.4, null],
];
const ease = (t) => 1 - Math.pow(1 - t, 3);
const page = await open(browser);
const away = [SIZE.width + 40, SIZE.height / 2];
const stage = await page.locator("#stage").boundingBox();
const total = Math.round(keys[keys.length - 1][0] * FPS);
const reads = [];
let inside = false;
for (let f = 0; f < total; f++) {
  const t = f / FPS;
  let k = 0;
  while (k < keys.length - 2 && keys[k + 1][0] <= t) k++;
  const [t0, a] = keys[k], [t1, b] = keys[k + 1];
  if (a || b) {
    const pa = a ? await toPx(page, a) : null, pb = b ? await toPx(page, b) : null;
    const u = ease(Math.min(1, (t - t0) / (t1 - t0)));
    // entering from the side or leaving: move from the stage centre line, so the phone eases in and out
    const from = pa || [pb[0] > stage.x + stage.width / 2 ? stage.x + stage.width * 0.52 : stage.x + stage.width * 0.48, pb[1]];
    const to = pb || [pa[0] > stage.x + stage.width / 2 ? stage.x + stage.width * 0.52 : stage.x + stage.width * 0.48, pa[1]];
    const x = from[0] + (to[0] - from[0]) * u, y = from[1] + (to[1] - from[1]) * u;
    if (!b && u >= 1) { if (inside) { await page.mouse.move(...away); inside = false; } }
    else { await page.mouse.move(x, y); inside = true; }
  } else if (inside) { await page.mouse.move(...away); inside = false; }
  await page.clock.runFor(1000 / FPS);
  await page.locator("#stage").screenshot({ path: join(FRAMES, `${String(f).padStart(4, "0")}.png`) });
  reads.push(parseFloat(await page.locator("#stage svg").getAttribute("data-tilt")));
}
writeFileSync(join(FRAMES, "reads.json"), JSON.stringify(reads));
console.log("frames", total);
await browser.close();
