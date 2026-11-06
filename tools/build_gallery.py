"""Genera le immagini e i dati della pagina web di confronto (web/).

Uso: python -m tools.build_gallery testdata/rolls web
Per ogni fotogramma: negativo, scatto simulato col telefono, risultato del motore, stampa di
laboratorio, più i passaggi intermedi del motore. Dataset BlueNeg, Copyrighted by Tien-Tsin Wong.
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

from filmengine.calibration import correct_light, light_is_clipped, measure_base
from filmengine.geometry import find_frame_corners, trim_dark_edges, trim_rebate_edges, warp_frame
from filmengine.imageio_ import linear_to_srgb, load_image, save_outputs
from filmengine.invert import compute_roll_levels, render_positive, to_density
from filmengine.pipeline import Calibration, develop_roll
from filmengine.profile import load_profile
from tools.evaluate import _align, compare
from tools.phone_sim import PhoneSetup, simulate

FILMS = {"19941217A": "Fuji 100", "19941218C": "Kodak Gold 100",
         "19941222E": "Konica Super XG 100", "199807A": "Fuji 400"}
PROFILES = {"19941218C": "kodak_gold_100"}
PHONE = PhoneSetup(tilt_deg=3, perspective=0.03, vignette=0.3, wb=(0.85, 1.0, 1.25), veil=0.01,
                   noise=0.008, jpeg_quality=85, blur=0.8)
WIDTH = 960


def _jpg(img_linear: np.ndarray, path: Path, width: int = WIDTH) -> str:
    h, w = img_linear.shape[:2]
    small = cv2.resize(img_linear, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)
    enc = (linear_to_srgb(np.nan_to_num(small)) * 255).round().astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), enc[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 88])
    return path.name


def _develop(path: Path, profile_id: str, calib: Calibration, out: Path):
    with contextlib.redirect_stderr(io.StringIO()):
        r = develop_roll([path], load_profile(profile_id), calib, out)[0]
    return load_image(r.outputs[0]).rgb, r.warnings


def _stages(cap, profile_id: str, img_dir: Path, stem: str) -> list[dict]:
    """Passaggi intermedi del motore su uno scatto da telefono."""
    prof = load_profile(profile_id)
    light = None if light_is_clipped(cap.light) else cap.light
    flat = correct_light(cap.image, light)
    corners = find_frame_corners(flat)
    crop = trim_dark_edges(trim_rebate_edges(warp_frame(flat, corners)) if corners is not None else flat)
    base = np.maximum(measure_base(correct_light(cap.base_patch, light)),
                      np.percentile(crop.reshape(-1, 3), 99.9, axis=0))
    dens = to_density(crop, base)
    plain = load_profile(profile_id)
    import dataclasses
    plain = dataclasses.replace(plain, paper_range=None, s_curve=0.0, frame_balance=0.0)
    scene = render_positive(dens, plain, compute_roll_levels([dens], plain))
    final = render_positive(dens, prof, compute_roll_levels([dens], prof))
    inverted_naive = np.clip(1.0 - crop / max(float(crop.max()), 1e-6), 0, 1)
    return [
        {"titolo": "1. Scatto col telefono", "testo": "Pellicola sulla luce: inclinata, luce non uniforme, riflessi, rumore e JPEG.", "img": _jpg(cap.image, img_dir / f"{stem}_s1.jpg")},
        {"titolo": "2. Luce corretta e ritaglio", "testo": "La foto della sola luce corregge l'illuminazione; il fotogramma viene trovato, raddrizzato e rifilato.", "img": _jpg(crop, img_dir / f"{stem}_s2.jpg")},
        {"titolo": "3. Inversione ingenua", "testo": "Quello che fa un semplice 'inverti colori': la maschera arancione diventa una dominante blu.", "img": _jpg(inverted_naive ** 2.2, img_dir / f"{stem}_s3.jpg")},
        {"titolo": "4. Inversione in densità", "testo": "Si divide per la base della pellicola e si inverte in densità: colori corretti, ma immagine piatta.", "img": _jpg(scene, img_dir / f"{stem}_s4.jpg")},
        {"titolo": "5. Carta da stampa", "testo": "Neri e bianchi neutri, gamma della carta e curva a S: il risultato finale.", "img": _jpg(final, img_dir / f"{stem}_s5.jpg")},
    ]


def build(root: Path, out: Path) -> dict:
    img_dir = out / "img"
    frames = []
    featured = None
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for i, neg_path in enumerate(sorted(root.glob("*/negativi/*.tif"))):
            roll = neg_path.parent.parent.name
            stem = neg_path.stem
            prof = PROFILES.get(roll, "generic_color")
            neg = load_image(neg_path).rgb
            ref_print = load_image(root / roll / "stampe" / f"{stem}.tif").rgb
            scan_res, _ = _develop(neg_path, prof, Calibration(), tmp / "scan")
            cap = simulate(trim_dark_edges(neg), PHONE, seed=i)
            cap_path, _ = save_outputs(cap.image, tmp / "cap" / stem)
            light = None if light_is_clipped(cap.light) else cap.light
            calib = Calibration(base_rgb=measure_base(correct_light(cap.base_patch, light)), light=cap.light)
            phone_res, warns = _develop(cap_path, prof, calib, tmp / "phone")
            aligned = _align(phone_res, ref_print)
            frames.append({
                "id": stem, "rullino": roll, "pellicola": FILMS.get(roll, roll), "profilo": prof,
                "negativo": _jpg(trim_dark_edges(neg), img_dir / f"{stem}_neg.jpg"),
                "telefono": _jpg(cap.image, img_dir / f"{stem}_tel.jpg"),
                "risultato": _jpg(aligned if aligned is not None else phone_res, img_dir / f"{stem}_ris.jpg"),
                "scansione": _jpg(scan_res, img_dir / f"{stem}_scan.jpg"),
                "stampa": _jpg(ref_print, img_dir / f"{stem}_stampa.jpg"),
                "dE_stampa": compare(phone_res, ref_print).get("dE_medio"),
                "dE_scansione": compare(phone_res, scan_res).get("dE_medio"),
                "avvisi": [w for w in warns if "non RAW" not in w],
            })
            if stem == "19941217A-10-tokyo":
                featured = {"id": stem, "passi": _stages(cap, prof, img_dir, stem)}
            print("ok", stem, file=sys.stderr)
    data = {"fotogrammi": frames, "passi": featured,
            "credito": "Negativi e stampe: dataset BlueNeg, Copyrighted by Tien-Tsin Wong"}
    (out / "data.js").write_text("window.GALLERIA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n",
                                 encoding="utf-8")
    return data


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
