"""Instagram carousel for Ai-Film-Developing, StudioLLM research-notes system (13 slides, 1080x1440, 3:4).

Run from the repository root:
    .venv/Scripts/python social/instagram/build_posts.py
Inputs live in social/instagram/assets (see assets/SOURCES.md). Run prepare_ektar.py,
prepare_frames.py and prepare_plates.py first if the developed files are missing.
"""
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = HERE / "assets"
PLATES = ASSETS / "plates"
OUT = HERE / "export"
FONTS = Path(
    "C:/Users/filip/AppData/Roaming/Claude/local-agent-mode-sessions/skills-plugin/"
    "dc6b188b-d5d2-4bd3-aa0c-05ba93e17414/9da99d3c-7b86-400f-b3da-817216493a35/"
    "skills/canvas-design/canvas-fonts"
)

S = 2
W, H = 1080, 1440
M = 64

HEAD_Y = 76            # header baseline
HEAD_RULE = 100        # hairline under the header
FOOT_RULE = H - 96     # hairline above the footer
FOOT_Y = H - 56        # footer baseline
TOP = 136              # first content line
BOTTOM = FOOT_RULE - 36
TITLE = 92             # one title size on every slide
GAP = 40               # title to content
CAP_GAP = 24           # figure to caption

DARK = (14, 15, 17)
LIGHT = (243, 243, 241)
INK = (17, 17, 19)
WHITE = (250, 250, 250)
GREY_D = (128, 128, 134)     # title first part on dark
GREY_L = (108, 108, 114)     # title first part on light
MUTED_D = (160, 160, 165)    # captions and metadata on dark
MUTED_L = (96, 96, 102)      # captions and metadata on light
RULE_D = (52, 53, 58)
RULE_L = (206, 206, 202)
BLUE = (46, 91, 255)         # title second part, fills, small text on light
BLUE_D = (124, 152, 255)     # small text on dark

SITE = "filippovisentin.github.io/Ai-Film-Developing"
CODE = "github.com/filippovisentin/Ai-Film-Developing"
STUDIO = "StudioLLM"
PROJECT = "Ai-Film-Developing"

FACES = {
    "title": "InstrumentSans-Bold.ttf",
    "body": "InstrumentSans-Regular.ttf",
    "bodyb": "InstrumentSans-Bold.ttf",
    "mono": "IBMPlexMono-Regular.ttf",
    "monob": "IBMPlexMono-Bold.ttf",
}
_cache = {}


def F(role, size):
    key = (FACES[role], int(round(size * S)))
    if key not in _cache:
        _cache[key] = ImageFont.truetype(str(FONTS / key[0]), key[1])
    return _cache[key]


def p(*v):
    return tuple(int(round(x * S)) for x in v)


class Slide:
    def __init__(self, dark=False):
        self.dark = dark
        self.bg = DARK if dark else LIGHT
        self.fg = WHITE if dark else INK
        self.grey = GREY_D if dark else GREY_L
        self.muted = MUTED_D if dark else MUTED_L
        self.rule_c = RULE_D if dark else RULE_L
        self.blue = BLUE_D if dark else BLUE
        self.im = Image.new("RGB", (W * S, H * S), self.bg)
        self.d = ImageDraw.Draw(self.im)

    # ---------------------------------------------------------------- text
    def w(self, s, f, track=0):
        return self.d.textlength(s, font=f) / S + track * max(len(s) - 1, 0)

    def text(self, x, y, s, f, fill=None, anchor="ls", track=0):
        fill = fill or self.fg
        if not track:
            self.d.text(p(x, y), s, font=f, fill=fill, anchor=anchor)
            return
        if anchor[0] == "m":
            x -= self.w(s, f, track) / 2
        elif anchor[0] == "r":
            x -= self.w(s, f, track)
        for i, ch in enumerate(s):
            cx = x + self.d.textlength(s[:i], font=f) / S + track * i
            self.d.text(p(cx, y), ch, font=f, fill=fill, anchor="l" + anchor[1])

    def mono(self, x, y, s, size=22, fill=None, anchor="ls", bold=False):
        self.text(x, y, s, F("monob" if bold else "mono", size), fill or self.muted, anchor=anchor)

    def title(self, y, first, second, size=104, maxw=W - 2 * M):
        """Two-tone title, as on the studio's other posts: grey first part, blue second part.
        y is the top. Returns the bottom."""
        f = F("title", size)
        tr = -0.045 * size
        lh = 0.98 * size
        lines = [(ln, self.grey) for ln in wrap_balanced(self, first, f, maxw, tr)]
        lines += [(ln, BLUE) for ln in wrap_balanced(self, second, f, maxw, tr)]
        for i, (ln, col) in enumerate(lines):
            self.text(M - size * 0.03, y + size * 0.78 + i * lh, ln, f, col, track=tr)
        return y + size * 0.78 + (len(lines) - 1) * lh + size * 0.24

    def para(self, x, y, s, size, maxw, fill=None, lh=1.36, role="body"):
        """y is the top of the block. Returns the bottom."""
        f = F(role, size)
        lines = wrap(self, s, f, maxw)
        for i, line in enumerate(lines):
            self.text(x, y + size * 0.8 + i * size * lh, line, f, fill or self.fg)
        return y + size * 0.8 + (len(lines) - 1) * size * lh + size * 0.3

    def para_h(self, s, size, maxw, lh=1.36, role="body"):
        n = len(wrap(self, s, F(role, size), maxw))
        return size * 0.8 + (n - 1) * size * lh + size * 0.3

    def rule(self, y, x0=M, x1=W - M, col=None):
        self.d.rectangle(p(x0, y, x1, y + 1), fill=col or self.rule_c)

    # ---------------------------------------------------------------- frame
    def frame(self, idx, total, section, credit=None):
        """Header: studio / project left, section right. Footer: credit left, page right."""
        self.mono(M, HEAD_Y, f"{STUDIO} / {PROJECT}", 21, self.fg)
        self.mono(W - M, HEAD_Y, section, 21, anchor="rs")
        self.rule(HEAD_RULE)
        self.rule(FOOT_RULE)
        self.mono(W - M, FOOT_Y, f"{idx:02d} / {total:02d}", 21, self.fg, anchor="rs")
        if credit:
            self.mono(M, FOOT_Y, credit, 19)

    def next_cue(self, y=None):
        """Quiet swipe cue on first slides."""
        self.mono(W - M, y or BOTTOM + 4, "next \u2192", 22, self.fg, anchor="rs")

    # ---------------------------------------------------------------- images
    def place(self, img, box, focus=(0.5, 0.5)):
        x0, y0, x1, y1 = box
        im = cover(img, int(round((x1 - x0) * S)), int(round((y1 - y0) * S)), focus)
        self.im.paste(im, p(x0, y0))
        self.d = ImageDraw.Draw(self.im)

    def marks(self, box, l=16, gap=8, col=None):
        """Registration corner marks just outside a figure."""
        col = col or self.muted
        x0, y0, x1, y1 = box
        wd = int(1.5 * S)
        for (x, y, sx, sy) in ((x0, y0, -1, -1), (x1, y0, 1, -1), (x0, y1, -1, 1), (x1, y1, 1, 1)):
            self.d.line(p(x + sx * gap, y, x + sx * (gap + l), y), fill=col, width=wd)
            self.d.line(p(x, y + sy * gap, x, y + sy * (gap + l)), fill=col, width=wd)

    def split(self, neg, dev, box, frac=0.5, labels=("a", "b")):
        """Same frame, negative left of the line and developed right of it."""
        x0, y0, x1, y1 = box
        self.place(dev, box)
        bw, bh = int(round((x1 - x0) * S)), int(round((y1 - y0) * S))
        n = cover(neg, bw, bh)
        cut = int(bw * frac)
        self.im.paste(n.crop((0, 0, cut, bh)), p(x0, y0))
        self.d = ImageDraw.Draw(self.im)
        hx = x0 + (x1 - x0) * frac
        self.d.rectangle(p(hx - 1, y0, hx + 1, y1), fill=WHITE)
        if labels:
            self.tag(x0 + 14, y0 + 14, labels[0])
            self.tag(hx + 14, y0 + 14, labels[1])

    def tag(self, x, y, s):
        f = F("mono", 22)
        tw = self.w(s, f)
        self.d.rectangle(p(x, y, x + tw + 20, y + 36), fill=DARK)
        self.text(x + 10, y + 26, s, f, WHITE)

    def caption(self, y, label, s, maxw=W - 2 * M, size=24):
        """Figure caption: bold mono label, then the text. y is the top. Returns the bottom."""
        f = F("mono", size)
        lw = self.w(label + "  ", F("monob", size))
        self.text(M, y + size * 0.8, label, F("monob", size), self.fg)
        lines = wrap(self, s, f, maxw - lw)
        for i, ln in enumerate(lines):
            self.text(M + lw, y + size * 0.8 + i * size * 1.45, ln, f, self.muted)
        return y + size * 0.8 + (len(lines) - 1) * size * 1.45 + size * 0.3

    def caption_h(self, label, s, maxw=W - 2 * M, size=24):
        lw = self.w(label + "  ", F("monob", size))
        n = len(wrap(self, s, F("mono", size), maxw - lw))
        return size * 0.8 + (n - 1) * size * 1.45 + size * 0.3

    def save(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.im.resize((W, H), Image.LANCZOS).save(path, quality=95)
        print("saved", path.relative_to(ROOT))


def wrap(sl, s, f, maxw, track=0):
    lines, cur = [], ""
    for word in s.split():
        t = (cur + " " + word).strip()
        if not cur or sl.w(t, f, track) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def wrap_balanced(sl, s, f, maxw, track=0):
    """Same line count as a greedy wrap, at the narrowest measure (no orphans)."""
    n = len(wrap(sl, s, f, maxw, track))
    lo, hi = maxw * 0.4, maxw
    for _ in range(18):
        mid = (lo + hi) / 2
        if len(wrap(sl, s, f, mid, track)) > n:
            lo = mid
        else:
            hi = mid
    return wrap(sl, s, f, hi, track)


def cover(img, w, h, focus=(0.5, 0.5)):
    r = max(w / img.width, h / img.height)
    im = img.resize((max(w, int(img.width * r + 0.5)), max(h, int(img.height * r + 0.5))), Image.LANCZOS)
    x = int((im.width - w) * focus[0])
    y = int((im.height - h) * focus[1])
    return im.crop((x, y, x + w, y + h))


def fit(img, maxw, maxh):
    r = min(maxw / img.width, maxh / img.height)
    return img.width * r, img.height * r


# -------------------------------------------------------------------- assets
def load_ektar():
    neg = Image.open(ASSETS / "ektar-frame-negative.png").convert("RGB")
    dev = Image.open(ASSETS / "ektar-frame-developed.jpg").convert("RGB").resize(neg.size, Image.LANCZOS)
    return neg, dev


def load_plate(item):
    return (Image.open(PLATES / f"{item}-negative.jpg").convert("RGB"),
            Image.open(PLATES / f"{item}-developed.jpg").convert("RGB"))


CREDIT_EKTAR = "Negative: LoMit, CC BY 4.0, via Wikimedia Commons"
CREDIT_SUPERIA = "Negative: Florian Schott, CC BY-SA 3.0, via Wikimedia Commons"
CREDIT_MV = "Glass negatives: Museums Victoria, public domain"


# ==================================================================== 01 field notes
SEC01 = "Field notes"


def n1_cover(idx, total):
    neg, dev = load_ektar()
    sl = Slide(dark=True)
    sl.frame(idx, total, SEC01, CREDIT_EKTAR)
    y = sl.title(TOP + 10, "Film negatives,", "developed in a browser.", TITLE)
    cap = ("Kodak Ektar 100, frame 22. (a) Phone photograph of the negative. "
           "(b) Base development in the browser, no manual edits.")
    ch = sl.caption_h("Fig. 1", cap)
    box = (M, y + GAP, W - M, BOTTOM - 40 - ch - CAP_GAP)
    sl.split(neg, dev, box, frac=0.5)
    sl.marks(box)
    sl.caption(box[3] + CAP_GAP, "Fig. 1", cap)
    sl.next_cue()
    return sl


def n2_abstract(idx, total):
    sl = Slide()
    sl.frame(idx, total, SEC01)
    y = sl.title(TOP + 10, "A phone, a light,", "a browser.", TITLE)
    sl.mono(M, y + GAP + 6, "Abstract", 22, BLUE, bold=True)
    y = sl.para(M, y + GAP + 22,
                "A phone and an even light can stand in for a film scanner. Ai-Film-Developing turns "
                "the photo of a negative into a positive image, in the browser. The file is processed "
                "on the device and is not uploaded.", 34, W - 2 * M, lh=1.32)
    steps = [("01", "Capture", "Photograph the negative on a light pad or a white screen."),
             ("02", "Profile", "Choose the film stock, or the generic profile."),
             ("03", "Inversion", "The engine estimates the film base from the frame edges, inverts and balances."),
             ("04", "Output", "Adjust if needed, then save a JPEG or a 16-bit TIFF.")]
    block = 22 + sum(sl.para_h(b, 29, W - 2 * M - 290) + 48 for _, _, b in steps) + 4
    y = max(y + 56, BOTTOM - block)
    sl.mono(M, y, "Method", 22, BLUE, bold=True)
    y += 22
    for n, head, body in steps:
        sl.rule(y + 4)
        sl.mono(M, y + 52, n, 24, BLUE)
        sl.text(M + 76, y + 52, head, F("bodyb", 32), INK)
        y = sl.para(M + 290, y + 26, body, 29, W - 2 * M - 290, fill=MUTED_L) + 22
    sl.rule(y + 4)
    return sl


def n3_capture(idx, total):
    kit = Image.open(ASSETS / "ektar-strip-negative.jpg").convert("RGB")
    sl = Slide()
    sl.frame(idx, total, "Method 01 / Capture", CREDIT_EKTAR)
    y = sl.title(TOP + 10, "Capture", "on an even light.", TITLE)
    notes = ["Keep the phone parallel to the film.",
             "Include some film edge: the engine reads the base there.",
             "Avoid reflections and direct light on the negative."]
    cap = "Ektar 100 strip on a window, as photographed. A: frame 22. B: film edge."
    ch = sl.caption_h("Fig. 3", cap)
    notes_h = 3 * 62
    box_top = y + GAP
    box_bot = BOTTOM - notes_h - 30 - ch - CAP_GAP
    src = (0.22, 0.17, 0.98, 0.83)   # strip crop, frames 22 to 21A
    crop = kit.crop((int(src[0] * kit.width), int(src[1] * kit.height), int(src[2] * kit.width), int(src[3] * kit.height)))
    bw = W - 2 * M
    bh = min(box_bot - box_top, bw * crop.height / crop.width)
    box = (M, box_top, W - M, box_top + bh)
    sl.place(crop, box)
    sl.marks(box)

    def to_box(rx, ry):  # strip-relative -> canvas
        return (box[0] + (rx - src[0]) / (src[2] - src[0]) * bw, box[1] + (ry - src[1]) / (src[3] - src[1]) * bh)

    for lab, (a, b) in (("A", ((0.305, 0.325), (0.62, 0.665))), ("B", ((0.305, 0.665), (0.62, 0.745)))):
        ax, ay = to_box(*a)
        bx, by = to_box(*b)
        sl.d.rectangle(p(ax, ay, bx, by), outline=BLUE, width=int(3 * S))
        sl.d.rectangle(p(ax, ay, ax + 34, ay + 34), fill=BLUE)
        sl.text(ax + 17, ay + 26, lab, F("monob", 22), WHITE, anchor="ms")
    sl.caption(box[3] + CAP_GAP, "Fig. 3", cap)
    ny = BOTTOM - notes_h
    for i, n in enumerate(notes):
        sl.rule(ny)
        sl.mono(M, ny + 42, f"{i + 1:02d}", 22, BLUE)
        sl.text(M + 64, ny + 42, n, F("body", 30), INK)
        ny += 62
    return sl


def n4_profile(idx, total):
    sl = Slide()
    sl.frame(idx, total, "Method 02 / Profile", None)
    y = sl.title(TOP + 10, "Tell it", "which film.", TITLE)
    intro = ("Each stock has its own base colour and contrast. The profile sets the starting point "
             "for the inversion.")
    sl.para(M, y + GAP, intro, 32, W - 2 * M, fill=MUTED_L)
    note = "Not sure which film you shot? The generic profiles work for most rolls."
    y = BOTTOM - (20 + 5 * 92 + 40 + sl.para_h(note, 30, W - 2 * M - 100))
    sl.mono(M, y, "Profile", 22, BLUE, bold=True)
    sl.mono(W - M, y, "Film type", 22, BLUE, bold=True, anchor="rs")
    y += 20
    rows = [("Generic colour negative", "colour negative"), ("Kodak Gold 100", "colour negative"),
            ("Kodak Portra 400", "colour negative"), ("Generic black and white", "black and white"),
            ("Ilford HP5 Plus 400", "black and white")]
    for name, kind in rows:
        sl.rule(y)
        sl.text(M, y + 60, name, F("bodyb", 36), INK)
        sl.mono(W - M, y + 58, kind, 24, MUTED_L, anchor="rs")
        y += 92
    sl.rule(y)
    y += 40
    sl.mono(M, y + 26, "Note", 22, BLUE, bold=True)
    sl.para(M + 100, y, note, 30, W - 2 * M - 100, fill=INK)
    return sl


def n5_inversion(idx, total):
    neg, dev = load_ektar()
    sl = Slide(dark=True)
    sl.frame(idx, total, "Method 03 / Inversion", CREDIT_EKTAR)
    y = sl.title(TOP + 10, "Inverting is", "not enough.", TITLE)
    naive = Image.fromarray(255 - np.asarray(neg))
    cap = ("Frame 22. (a) Negative. (b) Plain inversion: the orange base turns into a "
           "blue cast. (c) Engine: base estimated from the film edge, then inverted and balanced.")
    ch = sl.caption_h("Fig. 4", cap)
    top = y + GAP
    gap = 12
    bh = (BOTTOM - ch - CAP_GAP - top - 2 * gap) / 3
    for i, (img, lab) in enumerate(((neg, "a"), (naive, "b"), (dev, "c"))):
        box = (M, top + i * (bh + gap), W - M, top + i * (bh + gap) + bh)
        sl.place(img, box, focus=(0.5, 0.45))
        sl.tag(box[0] + 14, box[1] + 14, lab)
    sl.marks((M, top, W - M, top + 3 * bh + 2 * gap))
    sl.caption(top + 3 * bh + 2 * gap + CAP_GAP, "Fig. 4", cap)
    return sl


def histogram(img, bins=64):
    a = np.asarray(img.convert("L"), dtype=np.float32)
    h, _ = np.histogram(a, bins=bins, range=(0, 255))
    h = np.convolve(h, np.ones(3) / 3, mode="same")
    return h / h.max()


def n6_output(idx, total):
    neg, dev = load_ektar()
    sl = Slide()
    sl.frame(idx, total, "Method 04 / Output", CREDIT_EKTAR)
    y = sl.title(TOP + 10, "Adjust, then", "keep the file.", TITLE)
    top = y + GAP
    fw = W - 2 * M
    fh = BOTTOM - top - (52 + sl.caption_h("Fig. 6", "Luminance histogram of frame 22 before and after development.")
                         + 40 + 3 * 86) - 8
    sl.d.rectangle(p(M, top, W - M, top + fh), fill=(232, 232, 229))
    for k, (img, col, lab) in ((1, (dev, BLUE, "developed")), (0, (neg, INK, "negative"))):  # negative on top
        hst = histogram(img)
        pts = [(M + i / (len(hst) - 1) * fw, top + fh - 16 - v * (fh - 70)) for i, v in enumerate(hst)]
        if k == 1:
            sl.d.polygon([p(M, top + fh)] + [p(*q) for q in pts] + [p(W - M, top + fh)], fill=(206, 216, 255))
        sl.d.line([p(*q) for q in pts], fill=col, width=int(3 * S), joint="curve")
        sl.d.rectangle(p(M + 24 + k * 220, top + 28, M + 50 + k * 220, top + 32), fill=col)
        sl.mono(M + 60 + k * 220, top + 38, lab, 22, INK)
    sl.mono(M, top + fh + 32, "0", 20)
    sl.mono(W - M, top + fh + 32, "255", 20, anchor="rs")
    yc = sl.caption(top + fh + 52, "Fig. 6", "Luminance histogram of frame 22 before and after development.")
    y = yc + 40
    rows = [("Exposure, contrast, colour", "adjustable"), ("JPEG", "8-bit, to share"),
            ("TIFF", "16-bit, to keep editing")]
    for a, b in rows:
        sl.rule(y)
        sl.text(M, y + 58, a, F("bodyb", 32), INK)
        sl.mono(W - M, y + 56, b, 24, MUTED_L, anchor="rs")
        y += 86
    sl.rule(y)
    return sl


def n7_close(idx, total):
    sl = Slide(dark=True)
    sl.frame(idx, total, "Notes", None)
    y = sl.title(TOP + 10, "Open source.", "Runs in your browser.", TITLE)
    y += GAP
    rows = [("Tool", SITE), ("Code", CODE), ("Cost", "free"), ("Account", "none"),
            ("Your photos", "stay on your device")]
    for a, b in rows:
        sl.rule(y)
        sl.mono(M, y + 52, a, 24)
        sl.mono(M + 210, y + 52, b, 24, WHITE)
        y += 82
    sl.rule(y)
    end = "Link in bio. Save this for when your next roll comes back from the lab."
    sl.para(M, BOTTOM - sl.para_h(end, 34, W - 2 * M), end, 34, W - 2 * M, fill=WHITE)
    return sl




# ==================================================================== interlude: plate grids
PLATE_ITEMS = ["2057235", "2057262", "2057242", "2057245", "2057260", "2057251"]


def grid_slide(idx, total, kind, section, fig, note):
    """Six whole glass plates, 2 x 3, edges and tape included."""
    sl = Slide(dark=True)
    sl.frame(idx, total, section, CREDIT_MV)
    g = 12
    x0, x1 = M, W - M
    top, bot = TOP + 15, BOTTOM - sl.caption_h(fig, note) - CAP_GAP  # aligned with title cap height
    cw = (x1 - x0 - g) / 2
    ch = (bot - top - 2 * g) / 3
    for i, item in enumerate(PLATE_ITEMS):
        neg, dev = load_plate(item)
        img = neg if kind == "negative" else dev
        c, r = i % 2, i // 2
        bx, by = x0 + c * (cw + g), top + r * (ch + g)
        iw, ih = fit(img, cw, ch)
        ox, oy = bx + (cw - iw) / 2, by + (ch - ih) / 2
        sl.place(img, (ox, oy, ox + iw, oy + ih))
        sl.tag(ox + 10, oy + 10, f"{i + 1:02d}")
    sl.caption(bot + CAP_GAP, fig, note)
    return sl


# ==================================================================== interlude: details
DETAILS = [
    [("2057235", (0.45, 0.74), 0.22), ("2057242", (0.40, 0.33), 0.22),
     ("2057251", (0.40, 0.30), 0.26), ("2057262", (0.68, 0.42), 0.24)],
    [("2057260", (0.74, 0.22), 0.24), ("2057235", (0.84, 0.44), 0.22),
     ("2057245", (0.40, 0.30), 0.22), ("2057262", (0.03, 0.62), 0.16)],
]


def detail_slide(idx, total, spots, fig, first=1):
    """Four details, negative left and developed right, same crop."""
    sl = Slide(dark=True)
    sl.frame(idx, total, "Details", CREDIT_MV)
    note = f"Details {first:02d} to {first + 3:02d}. Left: negative. Right: developed, same crop."
    g = 12
    x0, x1 = M, W - M
    top, bot = TOP + 15, BOTTOM - sl.caption_h(fig, note) - CAP_GAP  # aligned with title cap height
    cw = (x1 - x0 - g) / 2
    rh = (bot - top - 3 * g) / 4
    for r, (item, (cx, cy), span) in enumerate(spots):
        neg, dev = load_plate(item)
        pw = span * neg.width
        ph = pw * rh / cw
        bx = max(0, min(neg.width - pw, cx * neg.width - pw / 2))
        by = max(0, min(neg.height - ph, cy * neg.height - ph / 2))
        crop = (int(bx), int(by), int(bx + pw), int(by + ph))
        y = top + r * (rh + g)
        for c, img in enumerate((neg, dev)):
            sl.place(img.crop(crop), (x0 + c * (cw + g), y, x0 + c * (cw + g) + cw, y + rh))
        sl.tag(x0 + 10, y + 10, f"{first + r:02d}  MV {item}")
    sl.caption(bot + CAP_GAP, fig, note)
    return sl


# ==================================================================== studies
STUDIES = [
    ("superia-frame-negative.png", "superia-frame-developed.jpg", CREDIT_SUPERIA, "Study 01,", "Fuji Superia 200.",
     [("Film", "Fuji Superia 200, 35 mm, frame 24"), ("Profile", "generic colour negative")],
     "Left of the line: negative, under the orange mask of colour film. Right: developed, no manual edits."),
    ("kodak-street-negative.jpg", "kodak-street-developed.jpg", CREDIT_MV, "Study 02,", "glass plate.",
     [("Plate", "MV 2057235, Southampton Crescent"), ("Place", "Abbotsford, Melbourne, c. 1930s"),
      ("Profile", "generic black and white")],
     "Left of the line: glass negative. Right: developed, no manual edits."),
]


def study_page(idx, total, fig, neg_file, dev_file, credit, t1, t2, meta, cap):
    """One frame: title, metadata, split figure and caption."""
    neg = Image.open(ASSETS / neg_file).convert("RGB")
    dev = Image.open(ASSETS / dev_file).convert("RGB").resize(neg.size, Image.LANCZOS)
    sl = Slide(dark=True)
    sl.frame(idx, total, "Study", credit)
    y = sl.title(TOP + 10, t1, t2, TITLE)
    y += GAP - 26
    for a, b in meta:
        sl.mono(M, y + 26, a, 22)
        sl.mono(M + 150, y + 26, b, 22, WHITE)
        y += 36
    ch = sl.caption_h(fig, cap)
    top = y + 30
    bw, bh = fit(neg, W - 2 * M, BOTTOM - ch - CAP_GAP - top)
    top = BOTTOM - ch - CAP_GAP - bh          # figure sits on the common bottom line
    box = ((W - bw) / 2, top, (W + bw) / 2, top + bh)
    sl.split(neg, dev, box, labels=None)
    sl.marks(box)
    sl.caption(box[3] + CAP_GAP, fig, cap)
    return sl


# ==================================================================== the carousel
def carousel():
    """One post, 13 slides: notes alternate with full pages of photographs."""
    sec = "Plates / Kodak factory, c. 1930s"
    pages = [
        lambda i, t: n1_cover(i, t),
        lambda i, t: n2_abstract(i, t),
        lambda i, t: grid_slide(i, t, "negative", sec, "Fig. 2", "Six glass negatives, as scanned."),
        lambda i, t: n3_capture(i, t),
        lambda i, t: n4_profile(i, t),
        lambda i, t: n5_inversion(i, t),
        lambda i, t: grid_slide(i, t, "developed", sec, "Fig. 5", "The same six, base development, no manual edits."),
        lambda i, t: n6_output(i, t),
        lambda i, t: study_page(i, t, "Fig. 7", *STUDIES[0]),
        lambda i, t: detail_slide(i, t, DETAILS[0], "Fig. 8", first=1),
        lambda i, t: study_page(i, t, "Fig. 9", *STUDIES[1]),
        lambda i, t: detail_slide(i, t, DETAILS[1], "Fig. 10", first=5),
        lambda i, t: n7_close(i, t),
    ]
    out = OUT / "field-notes"
    for i, fn in enumerate(pages, 1):
        fn(i, len(pages)).save(out / f"{i:02d}.jpg")
    # video slides replace their still when the raea render exists (drafts/*/README in captions.md)
    for i, video in VIDEO_SLIDES.items():
        if video.exists():
            shutil.copyfile(video, out / f"{i:02d}.mp4")
            (out / f"{i:02d}.jpg").unlink()
            print("video", (out / f"{i:02d}.mp4").relative_to(ROOT))


# slide number -> rendered video (raea compositions in drafts/; render with `raea render <file>.tsx -o <file>.mp4`)
VIDEO_SLIDES = {
    4: HERE / "drafts" / "capture-video" / "capture.mp4",
    6: HERE / "drafts" / "colour-cloud" / "cloud.mp4",
}


if __name__ == "__main__":
    # clear generated output so removed slides do not linger
    if OUT.exists():
        shutil.rmtree(OUT)
    carousel()
