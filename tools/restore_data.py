"""Coppie di addestramento per la rete di restauro (scatto da telefono → sviluppo pulito).

Le anteprime BlueNeg sono positive: da ciascuna si ricostruisce un negativo artificiale
(maschera arancione + densità, come in tests/synthetic.py), lo si "fotografa" col simulatore
di telefono con difetti casuali e lo si sviluppa due volte:
  ingresso = sviluppo dello scatto rovinato, obiettivo = sviluppo del negativo pulito.
La rete impara così a togliere i difetti dello scatto, non a cambiare il "look".

Uso: python -m tools.restore_data testdata/train_prev testdata/restore_pairs.npz [varianti]
Dataset BlueNeg, Copyrighted by Tien-Tsin Wong: i dati generati restano in testdata/ (non pubblicati).
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from filmengine.calibration import correct_light, light_is_clipped, measure_base
from filmengine.imageio_ import linear_to_srgb, load_image, save_outputs
from filmengine.pipeline import Calibration, develop_roll
from filmengine.profile import load_profile
from tools.evaluate import _align
from tools.phone_sim import PhoneSetup, simulate

SCENE_MIN = 0.01
SCENE_SCALE = 0.5
MASKS = [(0.8, 0.5, 0.32), (0.85, 0.55, 0.36), (0.75, 0.47, 0.3), (0.82, 0.52, 0.28)]


def random_setup(rng: np.random.Generator, mild: bool = False) -> PhoneSetup:
    if mild:  # scatto quasi perfetto: la rete deve imparare a non toccarlo
        return PhoneSetup(blur=float(rng.uniform(0, 0.4)), noise=float(rng.uniform(0, 0.003)),
                          jpeg_quality=int(rng.integers(92, 99)))
    return PhoneSetup(
        tilt_deg=float(rng.uniform(-4, 4)), perspective=float(rng.uniform(0, 0.04)),
        vignette=float(rng.uniform(0, 0.4)), exposure=float(rng.uniform(0.85, 1.2)),
        wb=tuple(float(x) for x in rng.uniform([0.8, 1.0, 0.95], [1.0, 1.0, 1.35])),
        veil=float(rng.uniform(0, 0.02)), blur=float(rng.uniform(0.3, 1.3)),
        noise=float(rng.uniform(0.004, 0.02)), jpeg_quality=int(rng.integers(70, 96)))


def synth_negative(scene: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    mask = np.asarray(MASKS[rng.integers(len(MASKS))], np.float32)
    gamma = np.full(3, rng.uniform(0.55, 0.7), np.float32)
    scene = np.clip(scene, SCENE_MIN, 1.0)
    return (mask * (scene / SCENE_MIN) ** (-gamma)).astype(np.float32)


def make_pair(path: Path, seed: int, mild: bool = False,
              scale: float = SCENE_SCALE) -> tuple[np.ndarray, np.ndarray] | None:
    rng = np.random.default_rng(seed)
    scene = load_image(path).rgb
    if scale != 1.0:  # le anteprime a 8 bit hanno già grana e compressione: rimpicciolite sono pulite
        scene = cv2.resize(scene, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    neg = synth_negative(scene, rng)
    prof = load_profile("generic_color")
    with tempfile.TemporaryDirectory() as td, contextlib.redirect_stderr(io.StringIO()):
        t = Path(td)
        clean_tif, _ = save_outputs(neg / neg.max() * 0.9, t / "pulito")
        target = load_image(develop_roll([clean_tif], prof, Calibration(), t / "o1", crop=False)[0].outputs[0]).rgb
        cap = simulate(neg, random_setup(rng, mild), seed=seed)
        _, cap_jpg = save_outputs(cap.image, t / "scatto")
        light = None if light_is_clipped(cap.light) else cap.light
        calib = Calibration(measure_base(correct_light(cap.base_patch, light)), cap.light)
        phone = load_image(develop_roll([cap_jpg], prof, calib, t / "o2")[0].outputs[0]).rgb
    al = _align(phone, target)
    if al is None:
        return None
    valid = np.all(np.isfinite(al), -1)
    if valid.mean() < 0.8:
        return None
    enc = lambda x: np.round(linear_to_srgb(np.clip(np.nan_to_num(x), 0, 1)) * 65535).astype(np.uint16)  # noqa: E731
    a, b = enc(al), enc(target)
    a[~valid] = b[~valid]  # bordi senza dati: nessun errore da imparare
    return a, b


def _job(args):
    path, seed, mild = args
    try:
        return path.name, make_pair(path, seed, mild)
    except Exception as e:  # noqa: BLE001
        return path.name, repr(e)


def build(src: Path, out: Path, variants: int = 2, workers: int = 6) -> int:
    jobs = [(p, 1000 * v + i, v == 0) for i, p in enumerate(sorted(src.glob("*.png")))
            for v in range(variants)]
    inputs, targets, names = [], [], []
    with ProcessPoolExecutor(workers) as ex:
        for name, res in ex.map(_job, jobs):
            if isinstance(res, tuple):
                inputs.append(res[0]); targets.append(res[1]); names.append(name)
                print("ok", name, file=sys.stderr)
            else:
                print("scartato", name, res, file=sys.stderr)
    np.savez(out, inputs=np.array(inputs, dtype=object), targets=np.array(targets, dtype=object),
             names=np.array(names))
    return len(names)


if __name__ == "__main__":
    a = sys.argv[1:]
    print("coppie:", build(Path(a[0]), Path(a[1]), int(a[2]) if len(a) > 2 else 3))
