"""Data for the colour-cloud video: pixels of Ektar frame 22 in four states, and the frame in each state.

Run from the repository root:
    .venv/Scripts/python social/instagram/drafts/colour-cloud/prepare.py
States: 1 negative as photographed, 2 base removed (divided by the film base), 3 inverted, 4 the engine's
development. 2 and 3 are a simplified version of the engine's steps; 4 is its real output.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parents[1] / "assets"
MEDIA = HERE / "media"
N = 1400

neg = np.asarray(Image.open(ASSETS / "ektar-frame-negative.png").convert("RGB"), float) / 255
dev_img = Image.open(ASSETS / "ektar-frame-developed.jpg").convert("RGB").resize((neg.shape[1], neg.shape[0]), Image.LANCZOS)
dev = np.asarray(dev_img, float) / 255

# the film base: the brightest, most orange part of the negative (simplified: a high percentile per channel)
base = np.percentile(neg.reshape(-1, 3), 99.5, axis=0)
no_base = np.clip(neg / base, 0, 1)
inverted = 1 - no_base
states = [neg, no_base, inverted, dev]

MEDIA.mkdir(exist_ok=True)
for i, s in enumerate(states):
    Image.fromarray((s * 255).round().astype(np.uint8)).save(MEDIA / f"state{i + 1}.png")

rng = np.random.default_rng(22)
h, w = neg.shape[:2]
ys, xs = rng.integers(0, h, N), rng.integers(0, w, N)
pts = [[round(float(v), 4) for st in states for v in st[y, x]] for y, x in zip(ys, xs)]
# order: each point is 12 numbers, r g b for each of the four states
(HERE / "data.json").write_text(json.dumps({"base": [round(float(b), 4) for b in base], "points": pts}))
print("base", base.round(3), "points", len(pts))
for i, s in enumerate(states):
    m = s.reshape(-1, 3).mean(0)
    print(f"state {i + 1} mean rgb", m.round(3), "spread from grey", float(np.abs(s - s.mean(2, keepdims=True)).mean()).__round__(3))
