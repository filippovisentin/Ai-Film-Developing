"""Draft slides that explain how to photograph a negative with a phone.

Run from the repository root:
    .venv/Scripts/python social/instagram/drafts/phone_capture.py
Writes social/instagram/drafts/phone/*.png. Uses the Field Notes system from build_posts.py.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_posts as bp  # noqa: E402
from build_posts import (BLUE, BOTTOM, CAP_GAP, F, GAP, INK, LIGHT, M, MUTED_L, RULE_L, S, TITLE, TOP, W,  # noqa: E402
                         WHITE, Slide, p)

OUT = HERE / "phone"
NEG = Image.open(bp.ASSETS / "ektar-frame-negative.png").convert("RGB")
PAD_FILL = (226, 232, 255)     # the light pad's lit top, a pale tint of the accent
LINE = int(2.4 * S)


# ------------------------------------------------------------------ geometry helpers
def dashed(d, a, b, col, width=LINE, dash=9, gap=7):
    (x0, y0), (x1, y1) = a, b
    L = math.hypot(x1 - x0, y1 - y0)
    n = int(L // (dash + gap)) + 1
    for i in range(n):
        t0 = i * (dash + gap) / L
        t1 = min(1, (i * (dash + gap) + dash) / L)
        if t0 >= 1:
            break
        d.line([p(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0), p(x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)],
               fill=col, width=width)


def rot(pt, c, deg):
    a = math.radians(deg)
    x, y = pt[0] - c[0], pt[1] - c[1]
    return (c[0] + x * math.cos(a) - y * math.sin(a), c[1] + x * math.sin(a) + y * math.cos(a))


def rounded_poly(d, pts, col, width=LINE, fill=None):
    d.polygon([p(*q) for q in pts], fill=fill, outline=None)
    d.line([p(*q) for q in pts + [pts[0]]], fill=col, width=width, joint="curve")


def phone_shape(cx, cy, w, h, deg, r=7, n=5):
    """A phone seen edge-on: a thin rounded slab, as a polygon rotated by deg."""
    pts = []
    for (ax, ay, a0) in ((cx + w / 2 - r, cy - h / 2 + r, -90), (cx + w / 2 - r, cy + h / 2 - r, 0),
                         (cx - w / 2 + r, cy + h / 2 - r, 90), (cx - w / 2 + r, cy - h / 2 + r, 180)):
        for k in range(n + 1):
            t = math.radians(a0 + 90 * k / n)
            pts.append((ax + r * math.cos(t), ay + r * math.sin(t)))
    return [rot(q, (cx, cy), deg) for q in pts]


def ray_to_plane(o, ang_deg, y_plane):
    """Point where a ray from o at ang_deg (0 = straight down, positive leans right) meets y = y_plane."""
    a = math.radians(ang_deg)
    t = (y_plane - o[1]) / math.cos(a)
    return (o[0] + t * math.sin(a), y_plane)


# ------------------------------------------------------------------ the section drawing
def section(sl, box, tilt=0.0, lamp=False):
    """Side view: light pad, film on it, phone above it, the phone's field of view in dashed blue."""
    d = sl.d
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2 - (40 if lamp else 0)
    table = y1 - 6
    pad_top, pad_h = table - 34, 24
    film_y = pad_top - 4
    d.line([p(x0, table), p(x1, table)], fill=RULE_L, width=int(2 * S))
    d.rounded_rectangle(p(cx - 190, pad_top, cx + 190, pad_top + pad_h), radius=6 * S, fill=PAD_FILL, outline=INK, width=LINE)
    d.rectangle(p(cx - 174, pad_top + pad_h, cx - 164, table), fill=INK)
    d.rectangle(p(cx + 164, pad_top + pad_h, cx + 174, table), fill=INK)
    half = 134                                        # half the film strip shown
    d.rectangle(p(cx - half, film_y - 4, cx + half, film_y), fill=INK)
    ph_y = y0 + 34
    lens = rot((cx, ph_y + 11), (cx, ph_y), tilt)
    fov = math.degrees(math.atan((half + 6) / (film_y - (ph_y + 11))))
    hits = [ray_to_plane(lens, tilt - fov, film_y - 4), ray_to_plane(lens, tilt + fov, film_y - 4)]
    for h in hits:
        dashed(d, lens, h, BLUE)
    # what the photo covers, marked just above the film
    yb = film_y - 16
    d.line([p(hits[0][0], yb), p(hits[1][0], yb)], fill=BLUE, width=int(3 * S))
    for h in hits:
        d.line([p(h[0], yb - 7), p(h[0], yb + 7)], fill=BLUE, width=int(3 * S))
    rounded_poly(d, phone_shape(cx, ph_y, 224, 22, tilt), INK, fill=WHITE)
    lb = [rot(q, (cx, ph_y), tilt) for q in ((cx - 14, ph_y + 10), (cx + 14, ph_y + 10), (cx + 11, ph_y + 16), (cx - 11, ph_y + 16))]
    d.polygon([p(*q) for q in lb], fill=INK)
    # the level: solid blue ticks when the phone is parallel, a dashed grey line when it is not
    if tilt == 0:
        for a, b in ((cx - 190, cx - 136), (cx + 136, cx + 190)):
            d.line([p(a, ph_y), p(b, ph_y)], fill=BLUE, width=int(3 * S))
    else:
        dashed(d, (cx - 190, ph_y), (cx + 190, ph_y), MUTED_L, width=int(2 * S), dash=5, gap=6)
    if lamp:
        # mirror rule: put the bounce on the film, then place the lamp where its light reflects into the lens
        ly = y0 - 6
        bx = lens[0] + half * 0.85
        hl, hc = film_y - (ly + 30), film_y - lens[1]
        lx = lens[0] + (bx - lens[0]) * (hc + hl) / hc
        d.polygon([p(lx - 28, ly + 30), p(lx + 28, ly + 30), p(lx + 15, ly + 4), p(lx - 15, ly + 4)], fill=INK)
        d.line([p(lx, ly + 4), p(lx, y0 - 14)], fill=INK, width=int(3 * S))
        bounce = (bx, film_y - 4)
        d.line([p(lx, ly + 30), p(*bounce)], fill=INK, width=int(2.4 * S))
        d.line([p(*bounce), p(*lens)], fill=INK, width=int(2.4 * S))
        d.ellipse(p(bx - 6, bounce[1] - 6, bx + 6, bounce[1] + 6), fill=INK)
    return hits


# ------------------------------------------------------------------ the captured image
def perspective_coeffs(src, dst):
    """Coefficients for Image.transform(PERSPECTIVE) mapping output points dst to input points src."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def captured(kind, w, h):
    """What the phone records: the negative as framed (a), keystoned (b) or with a lamp's reflection (c)."""
    w2, h2 = int(w * S), int(h * S)
    base = bp.cover(NEG, w2, h2)
    if kind == "parallel":
        return base
    if kind == "tilted":
        canvas = Image.new("RGB", (w2, h2), (238, 238, 235))
        # the far edge of the film shrinks: a trapezoid, simulated
        inset = 0.13 * w2
        dst = [(inset, h2 * 0.07), (w2 - inset, h2 * 0.07), (w2, h2), (0, h2)]
        src = [(0, 0), (w2, 0), (w2, h2), (0, h2)]
        warped = base.transform((w2, h2), Image.PERSPECTIVE, perspective_coeffs(src, dst), Image.BICUBIC,
                                fillcolor=(238, 238, 235))
        mask = Image.new("L", (w2, h2), 0)
        ImageDraw.Draw(mask).polygon(dst, fill=255)
        canvas.paste(warped, (0, 0), mask)
        return canvas
    # lamp: a soft hot spot with a hard core, screened over the image (simulated)
    glare = Image.new("L", (w2, h2), 0)
    g = ImageDraw.Draw(glare)
    gx, gy = w2 * 0.62, h2 * 0.38
    g.ellipse((gx - w2 * 0.30, gy - h2 * 0.36, gx + w2 * 0.30, gy + h2 * 0.36), fill=150)
    glare = glare.filter(ImageFilter.GaussianBlur(w2 * 0.08))
    core = Image.new("L", (w2, h2), 0)
    ImageDraw.Draw(core).ellipse((gx - w2 * 0.07, gy - h2 * 0.08, gx + w2 * 0.07, gy + h2 * 0.08), fill=255)
    core = core.filter(ImageFilter.GaussianBlur(w2 * 0.015))
    a = np.asarray(base, float) / 255
    gl = np.maximum(np.asarray(glare, float), np.asarray(core, float))[..., None] / 255
    out = 1 - (1 - a) * (1 - gl)
    return Image.fromarray((out * 255).astype(np.uint8))


# ------------------------------------------------------------------ test B: three sections
def test_b():
    sl = Slide()
    sl.frame(4, 13, "Method 01 / Capture", bp.CREDIT_EKTAR)
    y = sl.title(TOP + 10, "Hold the phone", "parallel to the film.", TITLE)
    cap = ("Side view and what the phone records. (a) Parallel: a true rectangle. (b) Tilted 15°: "
           "the far edge shrinks. (c) Lamp above: its reflection lands in the photo. (b), (c) simulated.")
    ch = sl.caption_h("Fig. 3", cap)
    top = y + GAP
    bot = BOTTOM - ch - CAP_GAP
    g = 22
    rh = (bot - top - 2 * g) / 3
    iw = rh * NEG.width / NEG.height
    sw = W - 2 * M - iw - 28
    rows = (("parallel", "a", 0, False), ("tilted", "b", 15, False), ("lamp", "c", 0, True))
    for i, (kind, lab, tilt, lamp) in enumerate(rows):
        ry = top + i * (rh + g)
        if i:
            sl.rule(ry - g / 2)
        section(sl, (M, ry + 8, M + sw, ry + rh), tilt=tilt, lamp=lamp)
        ix = W - M - iw
        sl.im.paste(captured(kind, iw, rh), p(ix, ry))
        sl.d = ImageDraw.Draw(sl.im)
        ok = kind == "parallel"
        if ok:
            sl.d.rectangle(p(ix - 2, ry - 2, ix + iw + 2, ry + rh + 2), outline=BLUE, width=int(3 * S))
        sl.tag(ix + 12, ry + 12, lab)
        sl.mono(M, ry + 22, {"parallel": "parallel", "tilted": "tilted 15°", "lamp": "lamp above"}[kind], 22,
                BLUE if ok else MUTED_L, bold=ok)
    sl.caption(bot + CAP_GAP, "Fig. 3", cap)
    return sl


# ------------------------------------------------------------------ tests A and C: the Hairline copystand
FIG_DIR = OUT / "frames"


def union_box(paths, bg=(243, 243, 241), pad=24):
    """The box holding every drawn pixel across the given images, so stills and frames crop alike."""
    box = None
    for path in paths:
        a = np.asarray(Image.open(path).convert("RGB"), int)
        ink = (np.abs(a - np.array(bg)).sum(2) > 24)
        ys, xs = np.where(ink)
        b = (xs.min(), ys.min(), xs.max(), ys.max())
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return (max(0, box[0] - pad), max(0, box[1] - pad), box[2] + pad, box[3] + pad)


NOTES = ["Keep the phone parallel to the film.",
         "Fill the frame, with some film edge in it.",
         "Light from below only: turn off lamps above."]
CAP_A = ("A phone over a strip on a light pad. Dashed: what the camera sees. Level, it frames the "
         "film as a rectangle (blue). Tilted, the frame turns into a trapezoid. Inset simulated.")


def recorded(deg, w, h):
    """What the phone records at a sideways tilt of deg: the far side of the frame shrinks (simulated)."""
    w2, h2 = int(w * S), int(h * S)
    base = bp.cover(NEG, w2, h2)
    if abs(deg) < 0.05:
        return base
    k = 0.16 * min(1, abs(deg) / 18) * h2
    dst = [(0, 0), (w2, k), (w2, h2 - k), (0, h2)] if deg > 0 else [(0, k), (w2, 0), (w2, h2), (0, h2 - k)]
    src = [(0, 0), (w2, 0), (w2, h2), (0, h2)]
    warped = base.transform((w2, h2), Image.PERSPECTIVE, perspective_coeffs(src, dst), Image.BICUBIC, fillcolor=LIGHT)
    mask = Image.new("L", (w2, h2), 0)
    ImageDraw.Draw(mask).polygon(dst, fill=255)
    out = Image.new("RGB", (w2, h2), LIGHT)
    out.paste(warped, (0, 0), mask)
    return out


def copystand_slide(fig_img, tilt, crop):
    """The slide around one picture of the figure; read is the figure's read-out for that picture."""
    sl = Slide()
    sl.frame(4, 13, "Method 01 / Capture", bp.CREDIT_EKTAR)
    y = sl.title(TOP + 10, "Hold the phone", "parallel to the film.", TITLE)
    ch = sl.caption_h("Fig. 3", CAP_A)
    notes_h = 3 * 62
    top = y + GAP
    bot = BOTTOM - notes_h - 30 - ch - CAP_GAP
    cw, chh = crop[2] - crop[0], crop[3] - crop[1]
    fw = W - 2 * M
    fh = min(bot - top, fw * chh / cw)
    fw2 = fh * cw / chh
    x0 = (W - fw2) / 2
    im = fig_img.crop(crop).resize((int(fw2 * S), int(fh * S)), Image.LANCZOS)
    sl.im.paste(im, p(x0, top))
    sl.d = ImageDraw.Draw(sl.im)
    level = abs(tilt) < 1.5
    read = f"tilt {abs(tilt):4.1f}°"
    sl.mono(W - M, top + 26, "level" if level else read, 26, BLUE if level else INK, anchor="rs", bold=True)
    sl.mono(W - M, top + 58, "phone to film", 20, MUTED_L, anchor="rs")
    # inset: what the phone records at this tilt
    deg = tilt
    iw, ih = 244, 244 * NEG.height / NEG.width
    sl.im.paste(recorded(deg, iw, ih), p(M, top))
    sl.d = ImageDraw.Draw(sl.im)
    if level:
        sl.d.rectangle(p(M - 2, top - 2, M + iw + 2, top + ih + 2), outline=BLUE, width=int(3 * S))
    sl.mono(M, top + ih + 30, "what the phone records", 20, BLUE if level else MUTED_L)
    yc = sl.caption(top + fh + CAP_GAP, "Fig. 3", CAP_A)
    ny = BOTTOM - notes_h
    for i, n in enumerate(NOTES):
        sl.rule(ny)
        sl.mono(M, ny + 42, f"{i + 1:02d}", 22, BLUE)
        sl.text(M + 64, ny + 42, n, F("body", 30), INK)
        ny += 62
    return sl


def test_a_and_c():
    import json
    import subprocess
    frames = sorted(FIG_DIR.glob("*.png"))
    reads = json.loads((FIG_DIR / "reads.json").read_text(encoding="utf-8"))
    crop = union_box([OUT / "a-rest.png", OUT / "a-tilt.png"] + frames[::10])
    sl = copystand_slide(Image.open(OUT / "a-rest.png").convert("RGB"), 0.0, crop)
    sl.im.resize((W, bp.H), Image.LANCZOS).save(OUT / "a-isometric.png")
    print("saved", OUT / "a-isometric.png")
    vid = OUT / "c-frames"
    vid.mkdir(exist_ok=True)
    for i, f in enumerate(frames):
        sl = copystand_slide(Image.open(f).convert("RGB"), reads[i], crop)
        sl.im.resize((W, bp.H), Image.LANCZOS).save(vid / f"{i:04d}.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "60", "-i", str(vid / "%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow",
                    "-movflags", "+faststart", str(OUT / "c-animated.mp4")], check=True)
    print("saved", OUT / "c-animated.mp4")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    s = test_b()
    s.im.resize((W, bp.H), Image.LANCZOS).save(OUT / "b-sections.png")
    print("saved", OUT / "b-sections.png")
    if (OUT / "frames").exists():
        test_a_and_c()
