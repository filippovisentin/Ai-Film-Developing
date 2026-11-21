/**
 * Field Notes slide 06, "Inverting is not enough", as a video slide: the colour cloud.
 * 12.6 s, 756 frames at 60 fps, 1080x1440 (3:4, the carousel's shape).
 * 1400 pixels of Kodak Ektar 100 frame 22, each placed in an RGB cube by its colour, with the grey axis (black to
 * white) standing upright. The cloud travels through four states: negative, base removed, inverted, the engine's
 * development; then it rewinds, so the loop is seamless. States 2 and 3 are simplified; 4 is the engine's output.
 * Numbers: pixels and states from prepare.py (data.json, media/state1-4.png); layout from build_posts.py.
 */
import { AbsoluteFill, Composition, Img, interpolate, registerRoot, staticFile, useCurrentFrame, useVideoConfig, Easing } from "raea";
import data from "./data.json";

// ---------------------------------------------------------------- the look (Field Notes, dark slide)
const DARK = "#0E0F11", WHITE = "#FAFAFA", GREY = "#808086", MUTED = "#A0A0A5", RULE = "#34353A", EDGE = "#3E3F45";
const BLUE = "#2E5BFF", BLUE_D = "#7C98FF";
const M = 64, W = 1080;
const css = `
@font-face { font-family: "Instrument Sans"; font-weight: 700; src: url("${staticFile("fonts/InstrumentSans-Bold.ttf")}"); }
@font-face { font-family: "Instrument Sans"; font-weight: 400; src: url("${staticFile("fonts/InstrumentSans-Regular.ttf")}"); }
@font-face { font-family: "Plex Mono"; font-weight: 400; src: url("${staticFile("fonts/IBMPlexMono-Regular.ttf")}"); }
@font-face { font-family: "Plex Mono"; font-weight: 700; src: url("${staticFile("fonts/IBMPlexMono-Bold.ttf")}"); }
`;
const SANS = "Instrument Sans", MONO = "Plex Mono";
const STATE_IMG = [1, 2, 3, 4].map((i) => staticFile(`state${i}.png`));
const STEPS = ["Negative, as photographed", "Film base removed", "Inverted", "Balanced by the engine"];

// ---------------------------------------------------------------- helpers
const clampX = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const IO = Easing.inOut(Easing.cubic);
function keyed(t: number, keys: [number, number][]) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, v0] = keys[i], [t1, v1] = keys[i + 1];
    if (t <= t1) return v0 + (v1 - v0) * IO((t - t0) / (t1 - t0));
  }
  return keys[keys.length - 1][1];
}
type V3 = [number, number, number];

// ---------------------------------------------------------------- data
const PTS: number[][] = (data as { points: number[][] }).points;
/** Each point's delay in seconds: darker pixels of the negative set off first, so the cloud moves like a flock. */
const DELAY = PTS.map((q) => 0.85 * (1 - (q[0] + q[1] + q[2]) / 3));
/** A fixed pseudo-random number per point and channel, seeded from the index (holds still across frames). */
const hash = (i: number, k: number) => { const x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return x - Math.floor(x); };
/** Drift: each point breathes on three slow sines whose periods divide the loop, so frame 0 and the last frame meet. */
const DRIFT = PTS.map((_, i) => [0, 1, 2].map((k) => ({ n: 2 + Math.floor(hash(i, k) * 4), ph: hash(i, k + 3) * 2 * Math.PI })));
const U3: V3 = [1 / Math.sqrt(3), 1 / Math.sqrt(3), 1 / Math.sqrt(3)];
/** Where point i is drawn: its true colour, swung round the grey axis and pushed outward while it travels, plus drift. */
function placeAt(i: number, c: V3, p: number, t: number): V3 {
  const frac = p - Math.floor(p);
  const travel = Math.sin(Math.PI * frac);                    // 0 at each state, 1 mid-way
  const theta = 1.15 * travel * (hash(i, 7) > 0.5 ? 1 : -1) * (0.6 + 0.4 * hash(i, 8));
  const bulge = 1 + 0.75 * travel;
  const v: V3 = [c[0] - 0.5, c[1] - 0.5, c[2] - 0.5];
  const along = v[0] * U3[0] + v[1] * U3[1] + v[2] * U3[2];
  const perp: V3 = [v[0] - along * U3[0], v[1] - along * U3[1], v[2] - along * U3[2]];
  const cr: V3 = [U3[1] * perp[2] - U3[2] * perp[1], U3[2] * perp[0] - U3[0] * perp[2], U3[0] * perp[1] - U3[1] * perp[0]];
  const ct = Math.cos(theta) * bulge, st = Math.sin(theta) * bulge;
  const amp = 0.011 + 0.02 * travel;
  return [0, 1, 2].map((k) => {
    const d = DRIFT[i][k];
    return 0.5 + along * U3[k] + perp[k] * ct + cr[k] * st + amp * Math.sin((2 * Math.PI * d.n * t) / T + d.ph);
  }) as V3;
}
/** The colour of point q at state p (0..3), straight between neighbouring states. */
function colourAt(q: number[], p: number): V3 {
  const k = Math.min(2, Math.floor(p)), u = p - k;
  const a = k * 3, b = (k + 1) * 3;
  return [q[a] + (q[b] - q[a]) * u, q[a + 1] + (q[b + 1] - q[a + 1]) * u, q[a + 2] + (q[b + 2] - q[a + 2]) * u];
}

// ---------------------------------------------------------------- timing (seconds)
const STATE: [number, number][] = [[0, 0], [1.4, 0], [3.0, 1], [3.7, 1], [5.3, 2], [6.0, 2], [7.8, 3], [10.0, 3], [11.7, 0], [12.6, 0]];
const T = 12.6;

// ---------------------------------------------------------------- the cube: grey axis up, then yaw and a downward look
function rotation(yaw: number, pitch: number) {
  // Rodrigues: take (1,1,1)/√3 onto +y
  const u: V3 = [1 / Math.sqrt(3), 1 / Math.sqrt(3), 1 / Math.sqrt(3)];
  const axis: V3 = [-u[2], 0, u[0]];                    // u × y
  const an = Math.hypot(...axis), ang = Math.acos(u[1]);
  const [kx, ky, kz] = axis.map((v) => v / an);
  const c = Math.cos(ang), s = Math.sin(ang), v = 1 - c;
  const R = [
    [c + kx * kx * v, kx * ky * v - kz * s, kx * kz * v + ky * s],
    [ky * kx * v + kz * s, c + ky * ky * v, ky * kz * v - kx * s],
    [kz * kx * v - ky * s, kz * ky * v + kx * s, c + kz * kz * v],
  ];
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  return (p: V3): V3 => {
    const q = [p[0] - 0.5, p[1] - 0.5, p[2] - 0.5];
    const r = R.map((row) => row[0] * q[0] + row[1] * q[1] + row[2] * q[2]);
    const x1 = r[0] * cy + r[2] * sy, z1 = -r[0] * sy + r[2] * cy, y1 = r[1];
    return [x1, y1 * cp - z1 * sp, y1 * sp + z1 * cp];
  };
}

const AREA = { x: 0, y: 330, w: W, h: 594 };
const SCALE = 300, FOCAL = 3.4;

function Cloud({ t }: { t: number }) {
  const yaw = 0.9 + (2 * Math.PI * t) / T;              // one full turn per loop
  const rot = rotation(yaw, 0.32);
  const cx = AREA.w / 2, cy = AREA.h / 2 + 8;
  const proj = (p: V3) => {
    const r = rot(p), k = FOCAL / (FOCAL - r[2]);
    return { x: cx + r[0] * SCALE * k, y: cy - r[1] * SCALE * k, z: r[2], k };
  };
  // cube edges and corners
  const C: Record<string, V3> = { K: [0, 0, 0], R: [1, 0, 0], G: [0, 1, 0], B: [0, 0, 1], Y: [1, 1, 0], M: [1, 0, 1], C: [0, 1, 1], W: [1, 1, 1] };
  const E = [["K", "R"], ["K", "G"], ["K", "B"], ["R", "Y"], ["R", "M"], ["G", "Y"], ["G", "C"], ["B", "M"], ["B", "C"], ["Y", "W"], ["M", "W"], ["C", "W"]];
  const P2 = Object.fromEntries(Object.entries(C).map(([k, v]) => [k, proj(v)]));
  const centre = proj([0.5, 0.5, 0.5]);
  // points, depth sorted far to near
  const pts = PTS.map((q, i) => {
    const p = keyed(t - DELAY[i], STATE);
    const c = colourAt(q, p);
    const s = proj(placeAt(i, c, p, t));
    return { ...s, c };
  }).sort((a, b) => a.z - b.z);
  const rgb = (c: V3) => `rgb(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)})`;
  const NAMES: Record<string, string> = { K: "black", W: "white", R: "R", G: "G", B: "B", Y: "", M: "", C: "" };
  return (
    <svg width={AREA.w} height={AREA.h} viewBox={`0 0 ${AREA.w} ${AREA.h}`} style={{ position: "absolute", left: AREA.x, top: AREA.y, width: AREA.w, height: AREA.h }}>
      {E.map(([a, b], i) => (
        <path key={i} d={`M${P2[a].x},${P2[a].y}L${P2[b].x},${P2[b].y}`} stroke={EDGE} strokeWidth={1.4} fill="none" />
      ))}
      <path d={`M${P2.K.x},${P2.K.y}L${P2.W.x},${P2.W.y}`} stroke={BLUE_D} strokeWidth={1.8} strokeDasharray="6 7" fill="none" />
      {pts.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3.6 * p.k} fill={rgb(p.c)} stroke="rgba(255,255,255,0.14)" strokeWidth={0.6} />
      ))}
      {Object.entries(P2).filter(([k]) => NAMES[k]).map(([k, p]) => {
        const dx = p.x - centre.x, dy = p.y - centre.y, L = Math.hypot(dx, dy) || 1;
        return (
          <text key={k} x={p.x + (dx / L) * 26} y={p.y + (dy / L) * 26 + 7} fill={k === "K" || k === "W" ? BLUE_D : MUTED} fontFamily={MONO} fontSize={20} textAnchor="middle">{NAMES[k]}</text>
        );
      })}
    </svg>
  );
}

/** Mean distance of the cloud from the grey axis: the number the engine drives down. */
function offGrey(t: number) {
  let s = 0;
  for (let i = 0; i < PTS.length; i++) {
    const c = colourAt(PTS[i], keyed(t - DELAY[i], STATE));
    const m = (c[0] + c[1] + c[2]) / 3;
    s += (Math.abs(c[0] - m) + Math.abs(c[1] - m) + Math.abs(c[2] - m)) / 3;
  }
  return s / PTS.length;
}

/** The frame in its current state, and the four steps with the active one lit. */
function Steps({ t }: { t: number }) {
  const p = keyed(t, STATE);
  const iw = 380, ih = iw * 388 / 600, top = 938;
  const active = Math.round(p);
  return (
    <>
      <div style={{ position: "absolute", left: M, top, width: iw, height: ih, backgroundColor: "#000" }}>
        {STATE_IMG.map((src, i) => (
          <Img key={i} src={src} style={{ position: "absolute", left: 0, top: 0, width: iw, height: ih, opacity: interpolate(p, [i - 1, i, i + 1], [0, 1, 0], clampX) }} />
        ))}
      </div>
      <div style={{ position: "absolute", left: M, top: top + ih + 10, fontFamily: MONO, fontSize: 20, color: MUTED }}>frame 22, in this state</div>
      {STEPS.map((s, i) => {
        const on = i === active;
        const done = Math.max(0, Math.min(1, p - (i - 1)));
        const y = top + i * 62;
        return (
          <div key={i}>
            <div style={{ position: "absolute", left: 480, right: M, top: y, height: 1, backgroundColor: RULE }} />
            <div style={{ position: "absolute", left: 480, top: y, height: 2, width: (W - M - 480) * (i === 0 ? 1 : done), backgroundColor: i <= p + 0.001 ? BLUE : "rgba(0,0,0,0)", opacity: i === 0 ? (p < 0.5 ? 1 : 0) : 1 }} />
            <div style={{ position: "absolute", left: 480, top: y + 19, fontFamily: MONO, fontSize: 22, color: on ? BLUE_D : MUTED }}>{`0${i + 1}`}</div>
            <div style={{ position: "absolute", left: 536, top: y + 14, fontFamily: SANS, fontSize: 29, color: on ? WHITE : MUTED }}>{s}</div>
          </div>
        );
      })}
    </>
  );
}

const rule = (top: number) => <div style={{ position: "absolute", left: M, right: M, top, height: 1, backgroundColor: RULE }} />;

function Page({ t }: { t: number }) {
  const og = offGrey(t);
  return (
    <>
      <div style={{ position: "absolute", left: M, top: 56, fontFamily: MONO, fontSize: 21, color: WHITE }}>StudioLLM / Ai-Film-Developing</div>
      <div style={{ position: "absolute", right: M, top: 56, fontFamily: MONO, fontSize: 21, color: MUTED, textAlign: "right" }}>Method 03 / Inversion</div>
      {rule(100)}
      <div style={{ position: "absolute", left: M - 3, top: 140, fontFamily: SANS, fontWeight: 700, fontSize: 92, lineHeight: "90px", letterSpacing: -4.1, color: GREY }}>Inverting is</div>
      <div style={{ position: "absolute", left: M - 3, top: 230, fontFamily: SANS, fontWeight: 700, fontSize: 92, lineHeight: "90px", letterSpacing: -4.1, color: BLUE }}>not enough.</div>
      <div style={{ position: "absolute", right: M, top: 352, fontFamily: MONO, fontWeight: 700, fontSize: 28, color: WHITE, textAlign: "right" }}>{og.toFixed(3)}</div>
      <div style={{ position: "absolute", right: M, top: 392, fontFamily: MONO, fontSize: 20, color: MUTED, textAlign: "right" }}>mean distance from grey</div>
      <div style={{ position: "absolute", left: M, top: 1232, width: 110, fontFamily: MONO, fontWeight: 700, fontSize: 22, color: WHITE }}>Fig. 4</div>
      <div style={{ position: "absolute", left: M + 104, top: 1232, width: W - 2 * M - 104, fontFamily: MONO, fontSize: 22, lineHeight: "32px", color: MUTED }}>
        Each dot is a pixel of frame 22, placed by its red, green and blue. Dashed: the grey axis. Steps 02, 03 simplified; 04 is the engine's output.
      </div>
      {rule(1344)}
      <div style={{ position: "absolute", left: M, top: 1364, fontFamily: MONO, fontSize: 19, color: MUTED }}>Negative: LoMit, CC BY 4.0, via Wikimedia Commons</div>
      <div style={{ position: "absolute", right: M, top: 1363, fontFamily: MONO, fontSize: 21, color: WHITE, textAlign: "right" }}>06 / 13</div>
    </>
  );
}

export default function ColourCloud() {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = f / fps;
  return (
    <AbsoluteFill style={{ backgroundColor: DARK }}>
      <style>{css}</style>
      <Cloud t={t} />
      <Page t={t} />
      <Steps t={t} />
    </AbsoluteFill>
  );
}

registerRoot(() => <Composition id="colour-cloud" component={ColourCloud} width={1080} height={1440} fps={60} durationInFrames={756} />);
