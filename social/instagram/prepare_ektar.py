"""Crop the town-square frame from the Ektar strip and develop it with filmengine.

Run from the repository root after placing the full-resolution original at
social/instagram/assets/ektar-strip-negative.jpg:
    .venv/Scripts/python social/instagram/prepare_ektar.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent / "assets"
# frame interior measured on the 960x578 preview, kept relative so any size works
BOX = (301 / 960, 191 / 578, 589 / 960, 377 / 578)

strip = Image.open(ASSETS / "ektar-strip-negative.jpg").convert("RGB")
w, h = strip.size
crop = strip.crop((int(BOX[0] * w), int(BOX[1] * h), int(BOX[2] * w), int(BOX[3] * h)))
crop.save(ASSETS / "ektar-frame-negative.png")
print("frame", crop.size)

with tempfile.TemporaryDirectory() as tmp:
    subprocess.run([sys.executable, "-m", "filmengine", "develop", str(ASSETS / "ektar-frame-negative.png"),
                    "--profile", "generic_color", "--no-crop", "--out", tmp], check=True)
    shutil.copy(Path(tmp) / "ektar-frame-negative_originale.jpg", ASSETS / "ektar-frame-developed.jpg")
print("developed ->", ASSETS / "ektar-frame-developed.jpg")
