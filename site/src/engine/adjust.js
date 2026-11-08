import { img, median } from "./core.js";
const weights = [0.2126, 0.7152, 0.0722];
export function applyColorAdjustments(im, { exposure = 0, contrast = 0, temperature = 0, tint = 0, gains = [1, 1, 1] } = {}) {
  if (!Number.isFinite(exposure) || Math.abs(exposure) > 3 || !Number.isFinite(contrast) || Math.abs(contrast) > 100 || !Number.isFinite(temperature) || !Number.isFinite(tint) || Math.abs(temperature) > 100 || Math.abs(tint) > 100 || !Array.isArray(gains) || gains.length !== 3 || gains.some(v => !Number.isFinite(v) || v <= 0 || v > 16)) throw new Error("adjust-invalid-settings");
  const out = img(im.w, im.h, im.c, new Float32Array(im.data));
  if (exposure === 0 && contrast === 0 && temperature === 0 && tint === 0 && gains.every(v => v === 1)) return out;
  const t = temperature / 100, m = tint / 100;
  const exposureGain = 2 ** exposure, slope = 2 ** (contrast / 100);
  const g = [Math.exp(0.35*t+0.18*m), Math.exp(-0.18*m), Math.exp(-0.35*t+0.18*m)].map((v,k) => v*gains[k]);
  const toneIdentity = exposure === 0 && contrast === 0;
  for (let i = 0; i < im.data.length; i += im.c) {
    const r = Math.max(0, Math.min(1, im.data[i]));
    const green = Math.max(0, Math.min(1, im.data[i+1]));
    const b = Math.max(0, Math.min(1, im.data[i+2]));
    const lum = r*weights[0]+green*weights[1]+b*weights[2];
    const cr = r*g[0], cg = green*g[1], cb = b*g[2];
    const y = cr*weights[0]+cg*weights[1]+cb*weights[2];
    // Exposure is measured in stops in linear light. Contrast pivots at 18% gray.
    const target = toneIdentity ? lum : Math.min(1, 0.18*(lum*exposureGain/0.18)**slope);
    const scale = y > 0 ? target/y : 0;
    const sr = cr*scale, sg = cg*scale, sb = cb*scale;
    // Compress chroma toward equal-luminance gray instead of clipping channels.
    const max = Math.max(sr,sg,sb), chroma = max > 1 ? (1-target)/(max-target) : 1;
    out.data[i] = Math.max(0,Math.min(1,target+chroma*(sr-target)));
    out.data[i+1] = Math.max(0,Math.min(1,target+chroma*(sg-target)));
    out.data[i+2] = Math.max(0,Math.min(1,target+chroma*(sb-target)));
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
