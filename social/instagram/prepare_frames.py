"""Crop and develop the before/after frames (Fuji Superia strip, Kodak glass negatives).

Run from the repository root:
    .venv/Scripts/python social/instagram/prepare_frames.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent / "assets"
MV = ASSETS / "incoming" / "museums-victoria"


def develop(src, profile, dst):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-m", "filmengine", "develop", str(src), "--profile", profile,
                        "--no-crop", "--out", tmp], check=True, stdout=subprocess.DEVNULL)
        out = Image.open(Path(tmp) / f"{Path(src).stem}_originale.jpg").convert("RGB")
    out.resize(Image.open(src).size, Image.LANCZOS).save(dst, quality=95)


# Fuji Superia 200 strip: frame 24, rotated upright
strip = Image.open(ASSETS / "farbnegativ-strip.jpg").convert("RGB")
w, h = strip.size
box = (1032 / 2000, 155 / 934, 1950 / 2000, 782 / 934)
strip.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))).rotate(90, expand=True) \
    .save(ASSETS / "superia-frame-negative.png")
develop(ASSETS / "superia-frame-negative.png", "generic_color", ASSETS / "superia-frame-developed.jpg")

# Kodak factory glass negatives: develop the whole plate, then crop inside the tape
plates = {
    "kodak-street": ("b3a2d1bf.jpg", (0.17, 0.14, 0.795, 0.79)),
    "kodak-garden": ("b95210d0.jpg", (0.14, 0.075, 0.87, 0.955)),
}
for name, (fn, (x0, y0, x1, y1)) in plates.items():
    with tempfile.TemporaryDirectory() as tmp:
        dev_full = Path(tmp) / "dev.jpg"
        develop(MV / fn, "generic_bw", dev_full)
        neg = Image.open(MV / fn).convert("RGB")
        dev = Image.open(dev_full).convert("RGB")
        W, H = neg.size
        c = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
        neg.crop(c).save(ASSETS / f"{name}-negative.jpg", quality=95)
        dev.crop(c).save(ASSETS / f"{name}-developed.jpg", quality=95)
    print(name, c)
print("done")
