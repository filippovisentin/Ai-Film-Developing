"""Valuta il motore su negativi reali confrontandoli con le stampe di laboratorio.

Uso:
  python tools/evaluate.py prepare SRC_DIR OUT_DIR   # DNG + stampe -> versioni ridotte
  python tools/evaluate.py run OUT_DIR [--profile ID] # sviluppa e confronta

Immagini di prova: dataset BlueNeg, "Copyrighted by Tien-Tsin Wong"
(https://huggingface.co/datasets/ttgroup/blueneg-release).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from filmengine.imageio_ import load_image, save_outputs
from filmengine.pipeline import Calibration, develop_roll
from filmengine.profile import load_profile

LONG_SIDE = 1500


def _resize(img: np.ndarray, long_side: int = LONG_SIDE) -> np.ndarray:
    h, w = img.shape[:2]
    s = long_side / max(h, w)
    return cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)


def prepare(src: Path, out: Path) -> None:
    (out / "negativi").mkdir(parents=True, exist_ok=True)
    (out / "stampe").mkdir(parents=True, exist_ok=True)
    for dng in sorted(src.glob("*.dng")):
        neg = load_image(dng).rgb
        save_outputs(_resize(neg), out / "negativi" / dng.stem)
        (out / "negativi" / f"{dng.stem}.jpg").unlink()
        pr = src / f"{dng.stem}.print.tif"
        if pr.exists():
            save_outputs(_resize(load_image(pr).rgb), out / "stampe" / dng.stem)
            (out / "stampe" / f"{dng.stem}.jpg").unlink()
        print("preparato", dng.stem, neg.shape)


# --- confronto -------------------------------------------------------------

def _lab(rgb_linear: np.ndarray) -> np.ndarray:
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = np.clip(rgb_linear, 0, 1) @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)


def _align(moving: np.ndarray, ref: np.ndarray) -> np.ndarray | None:
    """Allinea `moving` su `ref` (omografia da punti ORB sulla luminanza)."""
    def gray(x):
        g = np.clip(x.mean(-1), 0, 1) ** (1 / 2.2)
        return cv2.equalizeHist((g * 255).astype(np.uint8))
    orb = cv2.ORB_create(5000)
    k1, d1 = orb.detectAndCompute(gray(moving), None)
    k2, d2 = orb.detectAndCompute(gray(ref), None)
    if d1 is None or d2 is None:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2)
    if len(matches) < 20:
        return None
    src = np.float32([k1[m.queryIdx].pt for m in matches])
    dst = np.float32([k2[m.trainIdx].pt for m in matches])
    h, inl = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
    if h is None or inl.sum() < 20:
        return None
    return cv2.warpPerspective(moving, h, (ref.shape[1], ref.shape[0]), flags=cv2.INTER_LINEAR,
                               borderValue=(np.nan, np.nan, np.nan))


def compare(out: np.ndarray, ref: np.ndarray) -> dict:
    al = _align(out, ref)
    if al is None:
        return {"errore": "allineamento fallito"}
    valid = np.all(np.isfinite(al), -1)
    m = 0.05  # scarta i bordi
    h, w = valid.shape
    valid[: int(h * m)] = valid[-int(h * m):] = False
    valid[:, : int(w * m)] = valid[:, -int(w * m):] = False
    a, r = al[valid], ref[valid]
    de = np.linalg.norm(_lab(a) - _lab(r), axis=-1)
    gain = np.median(r, 0) / np.maximum(np.median(a, 0), 1e-4)  # dominante + esposizione
    de_g = np.linalg.norm(_lab(a * gain) - _lab(r), axis=-1)
    la, lr = np.log(a.mean(-1) + 1e-3), np.log(r.mean(-1) + 1e-3)
    return {
        "dE_medio": round(float(de.mean()), 2),
        "dE_dopo_dominante": round(float(de_g.mean()), 2),
        "guadagno_RGB_per_stampa": [round(float(g), 3) for g in gain],
        "correlazione_tono": round(float(np.corrcoef(la, lr)[0, 1]), 3),
        "contrasto_rel": round(float(lr.std() / max(la.std(), 1e-6)), 3),
    }


def run(data: Path, profile_id: str, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or data / "sviluppati"
    frames = sorted((data / "negativi").glob("*.tif"))
    res = develop_roll(frames, load_profile(profile_id), Calibration(), out_dir)
    report = {}
    for r in res:
        stem = r.source.stem
        ref = data / "stampe" / f"{stem}.tif"
        report[stem] = compare(load_image(r.outputs[0]).rgb, load_image(ref).rgb) if ref.exists() else {}
    vals = [v["dE_medio"] for v in report.values() if "dE_medio" in v]
    vals_g = [v["dE_dopo_dominante"] for v in report.values() if "dE_dopo_dominante" in v]
    if vals:
        report["MEDIA"] = {"dE_medio": round(float(np.mean(vals)), 2),
                           "dE_dopo_dominante": round(float(np.mean(vals_g)), 2)}
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prepare"); a.add_argument("src", type=Path); a.add_argument("out", type=Path)
    b = sub.add_parser("run"); b.add_argument("data", type=Path); b.add_argument("--profile", default="generic_color")
    args = p.parse_args(argv)
    if args.cmd == "prepare":
        prepare(args.src, args.out)
    else:
        print(json.dumps(run(args.data, args.profile), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
