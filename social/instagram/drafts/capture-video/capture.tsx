/**
 * Field Notes slide 04, "Hold the phone parallel to the film", as a video slide.
 * 12.4 s, 744 frames at 60 fps, 1080x1440 (3:4, the carousel's shape).
 * A phone over a Kodak Ektar 100 strip on a light pad: it tilts right, left, comes back level; the camera then
 * pushes in on the frame it sees, the shutter fires, and the captured frame is shown flat; then it pulls back
 * to the start, so the loop is seamless. Geometry is a 2:1 isometric projection worked out from the frame number.
 * Numbers: layout from build_posts.py (margin 64, title 92 px, header 76, footer 1384); film from the strip photo.
 */
import { AbsoluteFill, Composition, Easing, Img, interpolate, registerRoot, staticFile, useCurrentFrame, useVideoConfig } from "raea";

// ---------------------------------------------------------------- the look (Field Notes)
const LIGHT = "#F3F3F1", INK = "#111113", GREY = "#6C6C72", MUTED = "#606066", RULE = "#CECECA", BLUE = "#2E5BFF";
const PAD_TOP = "#E6EAFB";
const M = 64, W = 1080;
const css = `
@font-face { font-family: "Instrument Sans"; font-weight: 700; src: url("${staticFile("fonts/InstrumentSans-Bold.ttf")}"); }
@font-face { font-family: "Instrument Sans"; font-weight: 400; src: url("${staticFile("fonts/InstrumentSans-Regular.ttf")}"); }
@font-face { font-family: "Plex Mono"; font-weight: 400; src: url("${staticFile("fonts/IBMPlexMono-Regular.ttf")}"); }
@font-face { font-family: "Plex Mono"; font-weight: 700; src: url("${staticFile("fonts/IBMPlexMono-Bold.ttf")}"); }
`;
const STRIP = staticFile("strip.jpg"), FRAME = staticFile("frame.png");
const SANS = "Instrument Sans", MONO = "Plex Mono";

// ---------------------------------------------------------------- helpers
const clampX = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const IO = Easing.inOut(Easing.cubic);
/** A value keyed in seconds, eased in-out between keys and held outside them. */
function keyed(t: number, keys: [number, number][]) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, v0] = keys[i], [t1, v1] = keys[i + 1];
    if (t <= t1) return v0 + (v1 - v0) * IO((t - t0) / (t1 - t0));
  }
  return keys[keys.length - 1][1];
}
const mix = (a: number[], b: number[], u: number) => a.map((v, i) => Math.round(v + (b[i] - v) * u));
const hex = (c: number[]) => `rgb(${c[0]},${c[1]},${c[2]})`;
type Pt = [number, number];

// ---------------------------------------------------------------- the scene, in world units (mm-ish), z up
const PAD = { x: 40, y: 58, z: 6, r: 6 };
const STRIP_W = 35, STRIP_L = 35 * 1360 / 602, ZS = 6.6;           // the strip photo is 1360 x 602
const FOCUS: [number, number, number] = [0, -39.5 + 0.533 * STRIP_L + 0 * 0, ZS]; // frame 22's centre
const YC = FOCUS[1];
const PH = { w: 14, l: 27, t: 3.2, z: 66, r: 4.5 };                  // half width, half length, thickness, height
const TAN_X = 13.8 / (PH.z - ZS), TAN_Y = 20.5 / (PH.z - ZS);

/** Iso camera: 45° azimuth, 2:1. */
function camera(S: number, ox: number, oy: number) {
  const c = Math.SQRT1_2;
  return (x: number, y: number, z: number): Pt => [ox + S * (x - y) * c, oy + S * ((x + y) * c * 0.5 - z * 0.866)];
}
function rrect(x0: number, y0: number, x1: number, y1: number, r: number, n = 6): Pt[] {
  const pts: Pt[] = [];
  const cs: [number, number, number][] = [[x1 - r, y0 + r, -90], [x1 - r, y1 - r, 0], [x0 + r, y1 - r, 90], [x0 + r, y0 + r, 180]];
  for (const [cx, cy, a0] of cs) for (let k = 0; k <= n; k++) {
    const a = ((a0 + (90 * k) / n) * Math.PI) / 180;
    pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
  }
  return pts;
}
function hull(p: Pt[]): Pt[] {
  const s = [...p].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cr = (o: Pt, a: Pt, b: Pt) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo: Pt[] = [], up: Pt[] = [];
  for (const q of s) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
  for (const q of s.reverse()) { while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q); }
  return lo.slice(0, -1).concat(up.slice(0, -1));
}
const d = (pts: Pt[], close = true) => "M" + pts.map((q) => `${q[0].toFixed(2)},${q[1].toFixed(2)}`).join("L") + (close ? "Z" : "");
const rad = (deg: number) => (deg * Math.PI) / 180;
/** A point on the phone's plane (u across, v along, w up from its underside), tilted a degrees about the y axis. */
function phonePt(a: number, u: number, v: number, w: number): [number, number, number] {
  const c = Math.cos(rad(a)), s = Math.sin(rad(a));
  return [u * c - w * s, YC + v, PH.z + u * s + w * c];
}
/** Where the camera's view meets the film, for a phone tilted a degrees. */
function footprint(a: number): [number, number, number][] {
  const c = Math.cos(rad(a)), s = Math.sin(rad(a));
  return ([[-1, -1], [1, -1], [1, 1], [-1, 1]] as Pt[]).map(([sx, sy]) => {
    const dx = sx * TAN_X, dy = sy * TAN_Y;
    const rx = dx * c + s, rz = dx * s - c;
    const t = (ZS - PH.z) / rz;
    return [rx * t, YC + dy * t, ZS];
  });
}
/** CSS matrix placing an element of size (w, h) so its corners land on o, o + ex, o + ey (screen points). */
function affine(o: Pt, x: Pt, y: Pt, w: number, h: number) {
  return `matrix(${(x[0] - o[0]) / w},${(x[1] - o[1]) / w},${(y[0] - o[0]) / h},${(y[1] - o[1]) / h},${o[0]},${o[1]})`;
}

// ---------------------------------------------------------------- timing (seconds)
const TILT: [number, number][] = [[0, 0], [1.0, 0], [2.6, 16], [3.5, 16], [5.3, -16], [6.0, -16], [7.4, 0]];
const ZOOM: [number, number][] = [[0, 0], [7.9, 0], [9.3, 1], [11.0, 1], [12.3, 0]];
/** How "level" the moment is: 1 while resting level, 0 through the tilts (so the swing across 0° never flashes blue). */
const LEVEL: [number, number][] = [[0, 1], [1.0, 1], [1.5, 0], [6.9, 0], [7.45, 1]];
const SHOT = 9.3;          // the shutter
const SHOT_OUT = [10.7, 11.0];

// ---------------------------------------------------------------- the figure box on the slide
const FIG = { x: M, y: 352, w: W - 2 * M, h: 600 };
const S_REST = 5.6, S_ZOOM = 13.5;

/** The isometric figure: pad, the real strip, footprint and guides, the phone with its live screen. */
function Figure({ t }: { t: number }) {
  const a = keyed(t, TILT);
  const z = keyed(t, ZOOM);
  // camera: at rest the whole stand is centred; zoomed, frame 22 sits in the middle of the box
  const S = S_REST + (S_ZOOM - S_REST) * z;
  const rest = camera(S_REST, 0, 0);
  const restBox = [rest(-PAD.x, PAD.y, 0)[0], rest(PAD.x, -PAD.y, 0)[0], rest(0, YC - PH.l, PH.z + 8)[1], rest(PAD.x, PAD.y, 0)[1]];
  const restOff: Pt = [FIG.w / 2 - (restBox[0] + restBox[1]) / 2 + 40, FIG.h / 2 - (restBox[2] + restBox[3]) / 2];
  const fRest = camera(S_REST, restOff[0], restOff[1])(...FOCUS);
  const fTo: Pt = [fRest[0] + (FIG.w / 2 - fRest[0]) * z, fRest[1] + (FIG.h / 2 + 30 - fRest[1]) * z];
  const base = camera(S, 0, 0)(...FOCUS);
  const P = camera(S, fTo[0] - base[0], fTo[1] - base[1]);
  const W3 = (q: [number, number, number]) => P(q[0], q[1], q[2]);

  // light pad: silhouette from top and bottom rings, a lit top, the panel crease
  const padRing = rrect(-PAD.x, -PAD.y, PAD.x, PAD.y, PAD.r);
  const padSil = hull(padRing.map((q) => P(q[0], q[1], 0)).concat(padRing.map((q) => P(q[0], q[1], PAD.z))));
  const padTop = padRing.map((q) => P(q[0], q[1], PAD.z));
  const panel = rrect(-PAD.x + 5, -PAD.y + 5, PAD.x - 5, PAD.y - 5, 3).map((q) => P(q[0], q[1], PAD.z));

  // the strip photo, laid on the pad: image x runs along world y, image y along world x
  const sO = P(-STRIP_W / 2, -STRIP_L / 2, ZS), sX = P(-STRIP_W / 2, STRIP_L / 2, ZS), sY = P(STRIP_W / 2, -STRIP_L / 2, ZS);
  const stripM = affine(sO, sX, sY, 1360, 602);
  const stripEdge = [sO, sX, P(STRIP_W / 2, STRIP_L / 2, ZS), sY];

  // footprint and guides
  const fp = footprint(a).map(W3);
  const lens = W3(phonePt(a, 0, 0, 0));
  const lvl = 1 - keyed(t, LEVEL);                       // 0 level .. 1 tilting
  const fpCol = hex(mix([46, 91, 255], [17, 17, 19], lvl));
  const pulse = interpolate(t, [7.3, 7.55, 7.9], [0, 1, 0], clampX);
  const fpW = 3 + 2.2 * pulse - 1.2 * lvl;

  // phone
  const outer = rrect(-PH.w, -PH.l, PH.w, PH.l, PH.r);
  const ring = (r: Pt[], w: number) => r.map((q) => W3(phonePt(a, q[0], q[1], w)));
  const phoneSil = hull(ring(outer, 0).concat(ring(outer, PH.t)));
  const phoneTop = ring(rrect(-PH.w + 1, -PH.l + 1, PH.w - 1, PH.l - 1, PH.r - 1), PH.t);
  const sw = PH.w - 2.2, sl = PH.l - 5.5;
  const scrO = W3(phonePt(a, -sw, -sl, PH.t)), scrX = W3(phonePt(a, -sw, sl, PH.t)), scrY = W3(phonePt(a, sw, -sl, PH.t));
  const scrM = affine(scrO, scrX, scrY, 600, 388);
  const scrEdge = [scrO, scrX, W3(phonePt(a, sw, sl, PH.t)), scrY];
  const slot = [W3(phonePt(a, -3, -PH.l + 2.6, PH.t)), W3(phonePt(a, 3, -PH.l + 2.6, PH.t))];

  const svg = { position: "absolute" as const, left: 0, top: 0, width: FIG.w, height: FIG.h };
  return (
    <div style={{ position: "absolute", left: FIG.x, top: FIG.y, width: FIG.w, height: FIG.h, overflow: "hidden" }}>
      <svg {...svg} viewBox={`0 0 ${FIG.w} ${FIG.h}`} style={svg}>
        <path d={d(padSil)} fill={LIGHT} stroke={INK} strokeWidth={2} strokeLinejoin="round" />
        <path d={d(padTop)} fill={PAD_TOP} stroke="none" />
        <path d={d(panel)} fill="none" stroke="#A9AFC6" strokeWidth={1.4} />
      </svg>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1360, height: 602, transformOrigin: "0 0", transform: stripM }}>
        <Img src={STRIP} style={{ width: 1360, height: 602 }} />
      </div>
      <svg {...svg} viewBox={`0 0 ${FIG.w} ${FIG.h}`} style={svg}>
        <path d={d(stripEdge)} fill="none" stroke={INK} strokeWidth={1.6} strokeLinejoin="round" />
        {fp.map((q, i) => (
          <path key={i} d={d([lens, q], false)} fill="none" stroke={fpCol} strokeWidth={1.6} strokeDasharray="5 6" opacity={0.85} />
        ))}
        <path d={d(fp)} fill="none" stroke={fpCol} strokeWidth={fpW} strokeLinejoin="round" />
        <path d={d(phoneSil)} fill={LIGHT} stroke={INK} strokeWidth={2} strokeLinejoin="round" />
        <path d={d(phoneTop)} fill="none" stroke="#9C9CA3" strokeWidth={1.3} />
        <path d={d(scrEdge)} fill={INK} stroke="none" />
      </svg>
      <div style={{ position: "absolute", left: 0, top: 0, width: 600, height: 388, transformOrigin: "0 0", transform: scrM, overflow: "hidden" }}>
        <Recorded tilt={a} w={600} h={388} />
      </div>
      <svg {...svg} viewBox={`0 0 ${FIG.w} ${FIG.h}`} style={svg}>
        <path d={d(scrEdge)} fill="none" stroke={fpCol} strokeWidth={1.4} />
        <path d={d(slot, false)} fill="none" stroke="#9C9CA3" strokeWidth={1.6} strokeLinecap="round" />
      </svg>
    </div>
  );
}

/** What the phone records at a sideways tilt: the frame turning in perspective about its long axis (simulated). */
function Recorded({ tilt, w, h, bg = "#1a1a1c" }: { tilt: number; w: number; h: number; bg?: string }) {
  return (
    <div style={{ position: "absolute", left: 0, top: 0, width: w, height: h, backgroundColor: bg }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: w, height: h, transform: `perspective(${w * 1.6}px) rotateX(${(-tilt * 1.15).toFixed(3)}deg) scale(${1 - Math.abs(tilt) * 0.004})` }}>
        <Img src={FRAME} style={{ width: w, height: h }} />
      </div>
    </div>
  );
}

/** The captured frame, shown flat over the figure after the shutter. */
function Captured({ t }: { t: number }) {
  const op = interpolate(t, [SHOT, SHOT + 0.25, SHOT_OUT[0], SHOT_OUT[1]], [0, 1, 1, 0], clampX);
  const flash = interpolate(t, [SHOT - 0.02, SHOT + 0.05, SHOT + 0.4], [0, 0.9, 0], clampX);
  const scale = interpolate(t, [SHOT, SHOT + 0.5], [0.96, 1], { ...clampX, easing: Easing.out(Easing.cubic) });
  const iw = 700, ih = iw * 388 / 600;
  const x = (FIG.w - iw) / 2, y = (FIG.h - ih) / 2 + 10;
  const mk = 18, gap = 10;
  return (
    <div style={{ position: "absolute", left: FIG.x, top: FIG.y, width: FIG.w, height: FIG.h }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: FIG.w, height: FIG.h, backgroundColor: LIGHT, opacity: op }} />
      <div style={{ position: "absolute", left: x, top: y, width: iw, height: ih, opacity: op, transform: `scale(${scale})` }}>
        <Img src={FRAME} style={{ width: iw, height: ih }} />
        <div style={{ position: "absolute", left: -3, top: -3, width: iw + 6, height: ih + 6, borderWidth: 3, borderStyle: "solid", borderColor: BLUE, boxSizing: "border-box" }} />
      </div>
      <svg width={FIG.w} height={FIG.h} viewBox={`0 0 ${FIG.w} ${FIG.h}`} style={{ position: "absolute", left: 0, top: 0, width: FIG.w, height: FIG.h, opacity: op }}>
        {([[x, y, -1, -1], [x + iw, y, 1, -1], [x, y + ih, -1, 1], [x + iw, y + ih, 1, 1]] as number[][]).map(([px, py, sx, sy], i) => (
          <path key={i} d={`M${px + sx * gap},${py}L${px + sx * (gap + mk)},${py}M${px},${py + sy * gap}L${px},${py + sy * (gap + mk)}`} stroke={MUTED} strokeWidth={2} fill="none" />
        ))}
      </svg>
      <div style={{ position: "absolute", left: x, top: y + ih + 22, fontFamily: MONO, fontSize: 22, color: BLUE, opacity: op }}>captured · frame 22 · a true rectangle</div>
      <div style={{ position: "absolute", left: 0, top: 0, width: FIG.w, height: FIG.h, backgroundColor: "#FFFFFF", opacity: flash }} />
    </div>
  );
}

/** The live read-out and the inset of what the phone records. */
function Readout({ t }: { t: number }) {
  const a = keyed(t, TILT);
  const z = keyed(t, ZOOM);
  const level = keyed(t, LEVEL) > 0.5;
  const fade = 1 - z;
  const text = t >= SHOT && t < SHOT_OUT[1] ? "captured" : level ? "level" : `tilt ${Math.abs(a).toFixed(1)}°`;
  const iw = 244, ih = iw * 388 / 600;
  return (
    <>
      <div style={{ position: "absolute", right: M, top: FIG.y + 4, fontFamily: MONO, fontWeight: 700, fontSize: 28, color: level || text === "captured" ? BLUE : INK, textAlign: "right" }}>{text}</div>
      <div style={{ position: "absolute", right: M, top: FIG.y + 44, fontFamily: MONO, fontSize: 20, color: MUTED, textAlign: "right", opacity: fade }}>phone to film</div>
      <div style={{ position: "absolute", left: M, top: FIG.y, width: iw, height: ih, opacity: fade, overflow: "hidden" }}>
        <Recorded tilt={a} w={iw} h={ih} bg={LIGHT} />
        <div style={{ position: "absolute", left: 0, top: 0, width: iw, height: ih, borderWidth: 3, borderStyle: "solid", borderColor: level ? BLUE : "rgba(0,0,0,0)", boxSizing: "border-box" }} />
      </div>
      <div style={{ position: "absolute", left: M, top: FIG.y + ih + 10, fontFamily: MONO, fontSize: 20, color: level ? BLUE : MUTED, opacity: fade }}>what the phone records</div>
    </>
  );
}

// ---------------------------------------------------------------- the static page around it
const rule = (top: number) => <div style={{ position: "absolute", left: M, right: M, top, height: 1, backgroundColor: RULE }} />;
const NOTES = ["Keep the phone parallel to the film.", "Fill the frame, with some film edge in it.", "Light from below only: turn off lamps above."];

function Page() {
  return (
    <>
      <div style={{ position: "absolute", left: M, top: 56, fontFamily: MONO, fontSize: 21, color: INK }}>StudioLLM / Ai-Film-Developing</div>
      <div style={{ position: "absolute", right: M, top: 56, fontFamily: MONO, fontSize: 21, color: MUTED, textAlign: "right" }}>Method 01 / Capture</div>
      {rule(100)}
      <div style={{ position: "absolute", left: M - 3, top: 140, fontFamily: SANS, fontWeight: 700, fontSize: 92, lineHeight: "90px", letterSpacing: -4.1, color: GREY }}>Hold the phone</div>
      <div style={{ position: "absolute", left: M - 3, top: 230, fontFamily: SANS, fontWeight: 700, fontSize: 92, lineHeight: "90px", letterSpacing: -4.1, color: BLUE }}>parallel to the film.</div>
      <div style={{ position: "absolute", left: M, top: 978, width: 110, fontFamily: MONO, fontWeight: 700, fontSize: 24, color: INK }}>Fig. 3</div>
      <div style={{ position: "absolute", left: M + 116, top: 978, width: W - 2 * M - 116, fontFamily: MONO, fontSize: 24, lineHeight: "35px", color: MUTED }}>
        A phone over a strip on a light pad. Dashed: what the camera sees. Level, it frames the film as a rectangle (blue); tilted, as a trapezoid. Inset simulated.
      </div>
      {NOTES.map((n, i) => (
        <div key={i}>
          {rule(1122 + i * 62)}
          <div style={{ position: "absolute", left: M, top: 1140 + i * 62, fontFamily: MONO, fontSize: 22, color: BLUE }}>{`0${i + 1}`}</div>
          <div style={{ position: "absolute", left: M + 64, top: 1134 + i * 62, fontFamily: SANS, fontSize: 30, color: INK }}>{n}</div>
        </div>
      ))}
      {rule(1344)}
      <div style={{ position: "absolute", left: M, top: 1364, fontFamily: MONO, fontSize: 19, color: MUTED }}>Negative: LoMit, CC BY 4.0, via Wikimedia Commons</div>
      <div style={{ position: "absolute", right: M, top: 1363, fontFamily: MONO, fontSize: 21, color: INK, textAlign: "right" }}>04 / 13</div>
    </>
  );
}

export default function Capture() {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = f / fps;
  return (
    <AbsoluteFill style={{ backgroundColor: LIGHT }}>
      <style>{css}</style>
      <Page />
      <Figure t={t} />
      <Captured t={t} />
      <Readout t={t} />
    </AbsoluteFill>
  );
}

registerRoot(() => <Composition id="capture" component={Capture} width={1080} height={1440} fps={60} durationInFrames={744} />);
