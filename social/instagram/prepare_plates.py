"""Develop the six Kodak factory glass plates (whole plate, tape and edges included) for the grid posts.

Run from the repository root:
    .venv/Scripts/python social/instagram/prepare_plates.py
Writes assets/plates/<museum item>-negative.jpg and -developed.jpg (base development, no manual edits).
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent / "assets"
MV = ASSETS / "incoming" / "museums-victoria"
OUT = ASSETS / "plates"

# raw negative scans only (the museum's own positives are not used)
PLATES = {
    "2057235": "b3a2d1bf.jpg",
    "2057242": "32c08866.jpg",
    "2057245": "0efc9c65.jpg",
    "2057251": "f453cfab.jpg",
    "2057260": "b95210d0.jpg",
    "2057262": "2a884623.jpg",
}

OUT.mkdir(exist_ok=True)
for item, fn in PLATES.items():
    src = MV / fn
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-m", "filmengine", "develop", str(src), "--profile", "generic_bw",
                        "--no-crop", "--out", tmp], check=True, stdout=subprocess.DEVNULL)
        dev = Image.open(Path(tmp) / f"{src.stem}_originale.jpg").convert("RGB")
    neg = Image.open(src).convert("RGB")
    dev = dev.resize(neg.size, Image.LANCZOS)
    neg.save(OUT / f"{item}-negative.jpg", quality=95)
    dev.save(OUT / f"{item}-developed.jpg", quality=95)
    print(item, neg.size)
