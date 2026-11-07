"""Prepara i dati per verificare che il motore JavaScript dia gli stessi risultati di filmengine.

Uso (dalla radice del repository): .venv/Scripts/python site/scripts/export_fixtures.py
Per alcuni negativi BlueNeg (Copyrighted by Tien-Tsin Wong) simula lo scatto col telefono, lo salva
come sRGB 8 bit (come lo leggerebbe il browser) e scrive i risultati di Python in float32 grezzo.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from filmengine.calibration import correct_light, light_is_clipped, measure_base  # noqa: E402
from filmengine.enhance import DEFAULT_MODEL, enhance, super_resolve  # noqa: E402
from filmengine.geometry import trim_dark_edges  # noqa: E402
from filmengine.imageio_ import linear_to_srgb, load_image  # noqa: E402
from filmengine.pipeline import Calibration, develop_roll  # noqa: E402
from filmengine.profile import load_profile  # noqa: E402
from tools.phone_sim import PhoneSetup, simulate  # noqa: E402

OUT = ROOT / "site" / "tests" / "fixtures"
CASES = [("19941217A/negativi/19941217A-10-tokyo.tif", "generic_color", True),
         ("19941218C/negativi/19941218C-03-tokyo.tif", "kodak_gold_100", True),
         ("199807A/negativi", "portra_400", False)]
PHONE = PhoneSetup(tilt_deg=3, perspective=0.03, vignette=0.3, wb=(0.85, 1.0, 1.25), veil=0.01,
                   noise=0.008, jpeg_quality=85, blur=0.8)
LONG = 1600


def u8(lin: np.ndarray) -> np.ndarray:
    return np.round(linear_to_srgb(lin) * 255).astype(np.uint8)


def write(name: str, arr: np.ndarray) -> None:
    arr = np.ascontiguousarray(arr)
    (OUT / name).write_bytes(arr.tobytes())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rolls = ROOT / "testdata" / "rolls"
    meta = []
    for i, (rel, prof_id, with_calib) in enumerate(CASES):
        p = rolls / rel
        if p.is_dir():
            p = sorted(p.glob("*.tif"))[0]
        neg = trim_dark_edges(load_image(p).rgb)
        h, w = neg.shape[:2]
        s = LONG / max(h, w)
        neg = cv2.resize(neg, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
        cap = simulate(neg, PHONE, seed=i)
        stem = f"case{i}"
        imgs = {"neg": u8(cap.image), "light": u8(cap.light), "base": u8(cap.base_patch)}
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            paths = {}
            for k, a in imgs.items():
                write(f"{stem}_{k}.u8", a)
                paths[k] = tmp / f"{k}.png"
                cv2.imwrite(str(paths[k]), a[..., ::-1])
            light = load_image(paths["light"]).rgb if with_calib else None
            base = None
            if with_calib:
                usable = None if light_is_clipped(light) else light
                base = measure_base(correct_light(load_image(paths["base"]).rgb, usable))
            with contextlib.redirect_stderr(io.StringIO()):
                r = develop_roll([paths["neg"]], load_profile(prof_id), Calibration(base, light), tmp / "o")[0]
            pos = load_image(r.outputs[0]).rgb  # TIFF 16 bit sRGB -> lineare
        better = enhance(pos)
        write(f"{stem}_pos.f32", pos.astype(np.float32))
        write(f"{stem}_enh.f32", better.astype(np.float32))
        entry = {"stem": stem, "profile": prof_id, "calib": with_calib,
                 "neg": list(imgs["neg"].shape), "light": list(imgs["light"].shape),
                 "base": list(imgs["base"].shape), "pos": list(pos.shape),
                 "warnings": [x for x in r.warnings if "non RAW" not in x]}
        if i == 0 and DEFAULT_MODEL.exists():
            patch = pos[100:196, 200:328].copy()
            write(f"{stem}_srin.f32", patch.astype(np.float32))
            write(f"{stem}_sr.f32", super_resolve(patch, 4).astype(np.float32))
            entry["sr"] = list(patch.shape)
        meta.append(entry)
        print("ok", stem, pos.shape, file=sys.stderr)
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
