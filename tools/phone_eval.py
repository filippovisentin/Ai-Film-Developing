"""Misura il degrado dovuto allo scatto col telefono, difetto per difetto.

Uso: python -m tools.phone_eval testdata/rolls [--frames N] [--out risultati.json]
Riferimento: lo sviluppo della scansione pulita dello stesso negativo.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

from filmengine.calibration import correct_light, light_is_clipped, measure_base
from filmengine.geometry import trim_dark_edges
from filmengine.imageio_ import load_image, save_outputs
from filmengine.pipeline import Calibration, develop_roll
from filmengine.profile import load_profile
from tools.evaluate import compare
from tools.phone_sim import PhoneSetup, simulate

WB = (0.85, 1.0, 1.25)  # il bilanciamento automatico del telefono "corregge" la maschera
SCENARI = {
    "ideale": (PhoneSetup(), True),
    "inclinato+prospettiva": (PhoneSetup(tilt_deg=5, perspective=0.04), True),
    "vignettatura+calibrazione": (PhoneSetup(vignette=0.4), True),
    "vignettatura senza calibrazione": (PhoneSetup(vignette=0.4), False),
    "foto della luce bruciata": (PhoneSetup(vignette=0.4, wb=WB, light_overexposed=True), True),
    "esposizione+bil.automatico": (PhoneSetup(exposure=1.3, wb=WB), True),
    "riflessi 2%": (PhoneSetup(veil=0.02), True),
    "rumore+jpeg+sfocatura": (PhoneSetup(noise=0.01, jpeg_quality=85, blur=1.0), True),
    "porta-negativi nero": (PhoneSetup(holder=True), True),
    "realistico+calibrazione": (PhoneSetup(tilt_deg=3, perspective=0.03, vignette=0.3, wb=WB, veil=0.01,
                                           noise=0.008, jpeg_quality=85, blur=0.8), True),
    "realistico senza calibrazione": (PhoneSetup(tilt_deg=3, perspective=0.03, vignette=0.3, wb=WB,
                                                 veil=0.01, noise=0.008, jpeg_quality=85, blur=0.8), False),
}


def _develop(path: Path, calib: Calibration, out: Path) -> tuple[np.ndarray, list[str]]:
    with contextlib.redirect_stderr(io.StringIO()):
        r = develop_roll([path], load_profile("generic_color"), calib, out)[0]
    return load_image(r.outputs[0]).rgb, r.warnings


def evaluate(root: Path, frames: int | None = None, scenari=SCENARI) -> dict:
    negs = sorted(root.glob("*/negativi/*.tif"))[:frames]
    res: dict[str, list] = {k: [] for k in scenari}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for i, f in enumerate(negs):
            ref, _ = _develop(f, Calibration(), tmp / "ref")
            # i bordi neri sono un artefatto dello scanner, non fanno parte della pellicola fisica
            neg = trim_dark_edges(load_image(f).rgb)
            for name, (setup, calibrate) in scenari.items():
                cap = simulate(neg, setup, seed=i)
                src, _ = save_outputs(cap.image, tmp / "cap" / f"{f.stem}")
                calib = Calibration()
                if calibrate:
                    usable = None if light_is_clipped(cap.light) else cap.light
                    calib = Calibration(base_rgb=measure_base(correct_light(cap.base_patch, usable)),
                                        light=cap.light)
                out, warns = _develop(src, calib, tmp / "out")
                c = compare(out, ref)
                res[name].append({"dE": c.get("dE_medio"), "trovato": not any("non trovato" in w for w in warns)})
    summary = {}
    for name, rows in res.items():
        ok = [r["dE"] for r in rows if r["dE"] is not None]
        summary[name] = {"dE_vs_scansione": round(float(np.mean(ok)), 2) if ok else None,
                         "dE_peggiore": round(float(np.max(ok)), 2) if ok else None,
                         "fotogramma_trovato": f"{sum(r['trovato'] for r in rows)}/{len(rows)}",
                         "allineamento_fallito": len(rows) - len(ok)}
    return summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("--frames", type=int)
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    s = evaluate(a.root, a.frames)
    txt = json.dumps(s, indent=1, ensure_ascii=False)
    print(txt)
    if a.out:
        a.out.write_text(txt, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
