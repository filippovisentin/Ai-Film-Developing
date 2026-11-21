/**
 * Copystand: a strip of film on a light pad, and a phone held above it. The
 * pointer's place on the ground, left or right of the pad, tilts the phone on
 * a spring. The camera's footprint on the film follows: a true rectangle over
 * the middle frame when the phone is level, a trapezoid when it is not, and
 * bright only when it is level. The slider is the steepest tilt, in degrees.
 *
 * The pattern: a continuous field (Terrain), with one part answering. The hit
 * test is the ground plane, which never moves.
 */
const {
  Cam, clamp, facing, fit, hull, open, poly, prism, proj, rad, rings, rrect, unproj,
  spring, stepS, mk, place, pointer, put, register, disposer, solid,
} = HL;

const PAD = [-52, -88, 52, 88], PAD_Z = 7, STRIP = [-17, -74, 17, 74], STRIP_Z = 8.4;
const FRAMES = [-56, -18, 20], FRAME_L = 36, FRAME_W = 24;
const PH_W = 25, PH_L = 50, PH_T = 4.5, PH_Z = 76, REST_TILT = 0;
const TAN_X = 21 / (PH_Z - STRIP_Z), TAN_Y = 25 / (PH_Z - STRIP_Z);

/** The phone's frame, tilted a degrees about the y axis: a world point for (u, v) on its plane at offset w. */
const phonePt = (a, u, v, w) => {
  const c = Math.cos(rad(a)), s = Math.sin(rad(a));
  return [u * c - w * s, v, PH_Z + u * s + w * c];
};

/** Where the camera's view meets the film: the four corners, for a phone tilted a degrees. */
function footprint(a) {
  const c = Math.cos(rad(a)), s = Math.sin(rad(a));
  return [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([sx, sy]) => {
    const dx = sx * TAN_X, dy = sy * TAN_Y, dz = -1;
    const rx = dx * c - dz * s, rz = dx * s + dz * c;
    const t = (STRIP_Z - PH_Z) / rz;
    return [rx * t, dy * t, STRIP_Z];
  });
}

function mount({ stage, svg, read }, value) {
  const bag = disposer();
  let maxTilt = value;

  const C = Cam(45, 0.5, 1.42);
  const ext = [phonePt(32, -PH_W, -PH_L, PH_T), phonePt(32, PH_W, PH_L, PH_T), phonePt(-32, -PH_W, PH_L, PH_T),
    phonePt(-32, PH_W, -PH_L, 0)];
  fit(C, [[PAD[0], PAD[1], 0], [PAD[2], PAD[3], 0], [PAD[0], PAD[3], 0], [PAD[2], PAD[1], 0], ...ext], 200, 162);
  const P = proj(C), front = facing(C);
  const W = (pt) => P(pt[0], pt[1], pt[2]);
  const g = mk("g", {}, svg);

  // the light pad: a thin slab, its lit panel set into the top, a switch on the near side
  const [padRing, padIn] = rings(PAD[0], PAD[1], PAD[2], PAD[3], 7, 1.6);
  put(solid(g), prism(P, front, padRing, padIn, 0, PAD_Z));
  mk("path", { d: poly(rrect(PAD[0] + 6, PAD[1] + 6, PAD[2] - 6, PAD[3] - 6, 4, 4).map((q) => P(q.u, q.v, PAD_Z))), class: "nf lo" }, g);
  const sw = mk("circle", { r: 1.6, class: "dot off" }, g);
  place(sw, P(PAD[2], PAD[3] - 12, PAD_Z / 2));

  // the strip: a thin plate with three frames and two rows of sprocket holes
  const [stRing, stIn] = rings(STRIP[0], STRIP[1], STRIP[2], STRIP[3], 1.2, 0.6);
  put(solid(g), prism(P, front, stRing, stIn, PAD_Z, STRIP_Z));
  for (const y0 of FRAMES)
    mk("path", { d: poly(rrect(-FRAME_W / 2, y0, FRAME_W / 2, y0 + FRAME_L, 1, 3).map((q) => P(q.u, q.v, STRIP_Z))), class: "nf lo" }, g);
  for (let k = 0; k < 24; k++)
    for (const x of [-14.6, 14.6]) {
      const dot = mk("circle", { r: 0.9, class: "dot off" }, g);
      place(dot, P(x, STRIP[1] + 3 + k * 6.1, STRIP_Z));
    }

  // the footprint on the film, the four guides up to the lens, then the phone over them
  const foot = mk("path", { class: "nf dash" }, g);
  const guides = mk("path", { class: "nf dash" }, g);
  const ph = solid(g);
  const screen = mk("path", { class: "nf lo" }, g);
  const finder = mk("path", { class: "nf lo" }, g);
  const slot = mk("path", { class: "nf lo" }, g);

  const outer = rrect(-PH_W, -PH_L, PH_W, PH_L, 7, 5), inner = rrect(-PH_W + 1.6, -PH_L + 1.6, PH_W - 1.6, PH_L - 1.6, 5.4, 5);
  const scr = rrect(-PH_W + 2.8, -PH_L + 7, PH_W - 2.8, PH_L - 7, 2.2, 3);
  const fin = rrect(-PH_W + 6, -15, PH_W - 6, 15, 1, 2);

  let last = null;
  function draw(a) {
    if (last !== null && Math.abs(a - last) < 0.01) return;
    last = a;
    svg.setAttribute("data-tilt", a.toFixed(3));   // the live angle, read by the video capture
    const ring = (r, w) => r.map((q) => W(phonePt(a, q.u, q.v, w)));
    put(ph, { sil: poly(hull(ring(outer, 0).concat(ring(outer, PH_T)))), crease: poly(ring(inner, PH_T)) });
    screen.setAttribute("d", poly(ring(scr, PH_T)));
    finder.setAttribute("d", poly(ring(fin, PH_T)));
    slot.setAttribute("d", open([W(phonePt(a, -5, -PH_L + 4, PH_T)), W(phonePt(a, 5, -PH_L + 4, PH_T))]));
    const fp = footprint(a), lens = W(phonePt(a, 0, 0, 0));
    foot.setAttribute("d", poly(fp.map(W)));
    guides.setAttribute("d", fp.map((q) => "M" + lens.join(",") + "L" + W(q).join(",")).join(""));
    const level = Math.abs(a) < 1.5;
    foot.classList.toggle("hi", level);
    finder.classList.toggle("hi", level);
  }

  const tilt = spring(REST_TILT);
  let active = false;
  const B = register(stage, (dt) => {
    const moving = stepS(tilt, dt);
    draw(tilt.x);
    return moving;
  });
  bag.add(B.unregister);

  /** Pointer to tilt: the ground point's x, beyond the pad's middle third, tips the phone toward it. */
  function aim(pt) {
    const [x] = unproj(C, pt[0], pt[1], 0);
    const k = clamp((Math.abs(x) - 12) / 48, 0, 1) * Math.sign(x);
    tilt.t = k * maxTilt;
    active = true;
    const deg = Math.round(Math.abs(tilt.t));
    read.textContent = deg < 2 ? "level" : `tilt ${deg}°`;
    B.wake();
  }
  function leave() {
    tilt.t = REST_TILT;
    active = false;
    read.textContent = "rest";
    B.wake();
  }

  read.textContent = "rest";
  draw(REST_TILT);
  bag.add(pointer(stage, { move: aim, leave }));
  bag.add(() => svg.replaceChildren());

  return {
    set: (v) => { maxTilt = v; if (active) B.wake(); },
    destroy: bag.dispose,
  };
}

hairline({
  name: "copystand",
  means: "A phone over film on a light pad: tip it and the frame it sees turns into a trapezoid; hold it level and the frame is true.",
  rules: [1, 3, 5, 8],
  range: [10, 20, 32],
  tour: [[110, 200], [300, 130], [200, 160], null],
  mount,
});
