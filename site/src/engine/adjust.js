import { img, median } from "./core.js";
const weights = [0.2126, 0.7152, 0.0722];
export function applyColorAdjustments(im, { temperature = 0, tint = 0, gains = [1, 1, 1] } = {}) {
  if (!Number.isFinite(temperature) || !Number.isFinite(tint) || Math.abs(temperature) > 100 || Math.abs(tint) > 100 || !Array.isArray(gains) || gains.length !== 3 || gains.some(v => !Number.isFinite(v) || v <= 0 || v > 16)) throw new Error("adjust-invalid-settings");
  const out = img(im.w, im.h, im.c, new Float32Array(im.data));
  if (temperature === 0 && tint === 0 && gains.every(v => v === 1)) return out;
  const t = temperature / 100, m = tint / 100;
  const g = [Math.exp(0.35*t+0.18*m), Math.exp(-0.18*m), Math.exp(-0.35*t+0.18*m)].map((v,k) => v*gains[k]);
  for (let i = 0; i < im.data.length; i += im.c) {
    const rgb = [0,1,2].map(k => Math.max(0, Math.min(1, im.data[i+k])));
    const lum = rgb.reduce((s,v,k) => s+v*weights[k],0);
    const corrected = rgb.map((v,k) => v*g[k]);
    const y = corrected.reduce((s,v,k) => s+v*weights[k],0);
    const scaled = corrected.map(v => y > 0 ? v*lum/y : 0);
    // Compress toward the equal-luminance gray point; preserve luminance in gamut.
    let chroma = 1;
    for (const v of scaled) {
      if (v > 1) chroma = Math.min(chroma, (1-lum)/(v-lum));
      if (v < 0) chroma = Math.min(chroma, -lum/(v-lum));
    }
    for (let k=0;k<3;k++) out.data[i+k] = Math.max(0,Math.min(1,lum+chroma*(scaled[k]-lum)));
  }
  return out;
}
export function sampleNeutralGains(im, { x, y }) {
  if (!Number.isFinite(x) || !Number.isFinite(y) || x<0 || x>1 || y<0 || y>1) throw new Error("neutral-invalid-position");
  const cx = Math.round(x*(im.w-1)), cy = Math.round(y*(im.h-1));
  const channels = [[],[],[]];
  for (let yy=Math.max(0,cy-2);yy<=Math.min(im.h-1,cy+2);yy++) for (let xx=Math.max(0,cx-2);xx<=Math.min(im.w-1,cx+2);xx++) for(let k=0;k<3;k++) channels[k].push(im.data[(yy*im.w+xx)*im.c+k]);
  const rgb=channels.map(v=>median(v));
  if (rgb.some(v=>!Number.isFinite(v))) throw new Error("neutral-invalid-sample");
  if (Math.min(...rgb)<0.01) throw new Error("neutral-too-dark");
  if (Math.max(...rgb)>0.98) throw new Error("neutral-clipped");
  if (Math.max(...rgb)/Math.min(...rgb)>4) throw new Error("neutral-extreme-color");
  const target=rgb.reduce((s,v,k)=>s+v*weights[k],0);
  return rgb.map(v=>target/v);
}
