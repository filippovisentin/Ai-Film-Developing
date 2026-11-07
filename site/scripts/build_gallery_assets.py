"""Prepara le immagini della galleria del sito (site/src/img/g/ e site/src/data/gallery.json).

Uso (dalla radice): .venv/Scripts/python -m tools.build_gallery testdata/rolls web   (se web/img manca)
                    .venv/Scripts/python site/scripts/build_gallery_assets.py
Parte da web/data.js e web/img (galleria di prova) e aggiunge il confronto tra le modalità su un
fotogramma. Negativi e stampe: dataset BlueNeg, Copyrighted by Tien-Tsin Wong.
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
from filmengine.enhance import DEFAULT_MODEL, RESTORE_MODEL  # noqa: E402
from filmengine.geometry import trim_dark_edges  # noqa: E402
from filmengine.imageio_ import linear_to_srgb, load_image, save_outputs  # noqa: E402
from filmengine.pipeline import Calibration, develop_roll  # noqa: E402
from filmengine.profile import load_profile  # noqa: E402
from tools.phone_sim import PhoneSetup, simulate  # noqa: E402

SRC = ROOT / "web"
OUT = ROOT / "site" / "src"
IMG = OUT / "img" / "g"
CREDIT = "Copyrighted by Tien-Tsin Wong"
PHONE = PhoneSetup(tilt_deg=3, perspective=0.03, vignette=0.3, wb=(0.85, 1.0, 1.25), veil=0.01,
                   noise=0.008, jpeg_quality=85, blur=0.8)


def recompress(name: str, width: int = 960, q: int = 80) -> str:
    im = cv2.imread(str(SRC / "img" / name))
    h, w = im.shape[:2]
    if w > width:
        im = cv2.resize(im, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(IMG / name), im, [cv2.IMWRITE_JPEG_QUALITY, q, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
    return name


def save_u8(lin: np.ndarray, name: str, q: int = 84) -> str:
    enc = np.round(linear_to_srgb(np.nan_to_num(lin)) * 255).astype(np.uint8)
    cv2.imwrite(str(IMG / name), enc[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, q, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
    return name


def modes(stem: str = "19941217A-10-tokyo") -> dict:
    """Le quattro modalità sullo stesso scatto da telefono, con un dettaglio ingrandito."""
    neg = trim_dark_edges(load_image(ROOT / "testdata" / "rolls" / stem[:9] / "negativi" / f"{stem}.tif").rgb)
    cap = simulate(neg, PHONE, seed=1)
    # lo stesso scatto è l'esempio dell'applicativo: negativo, foto della luce e del bordo
    ex = OUT / "img" / "esempio"
    ex.mkdir(parents=True, exist_ok=True)
    for name, lin in (("negativo", cap.image), ("luce", cap.light), ("bordo", cap.base_patch)):
        enc = np.round(linear_to_srgb(lin) * 255).astype(np.uint8)
        cv2.imwrite(str(ex / f"{name}.jpg"), enc[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 92])
    light = None if light_is_clipped(cap.light) else cap.light
    calib = Calibration(measure_base(correct_light(cap.base_patch, light)), cap.light)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cap_path = save_outputs(cap.image, tmp / "cap")[0]
        with contextlib.redirect_stderr(io.StringIO()):
            r = develop_roll([cap_path], load_profile("generic_color"), calib, tmp / "o", enhance=True,
                             super_res=2 if DEFAULT_MODEL.exists() else 0, restore=RESTORE_MODEL.exists())[0]
        out = {"originale": r.outputs[0], "migliorata": r.enhanced[0] if r.enhanced else None,
               "restaurata": r.restored[0] if r.restored else None, "ai": r.ai[0] if r.ai else None}
        imgs = {k: load_image(p).rgb for k, p in out.items() if p is not None}
    base = imgs["originale"]
    h, w = base.shape[:2]
    cw, ch = w // 4, h // 4
    x0, y0 = int(w * 0.40), int(h * 0.30)
    res = {"stem": stem, "full": {}, "detail": {}}
    for k, im in imgs.items():
        s = im.shape[1] / w
        res["full"][k] = save_u8(cv2.resize(im, (1200, round(1200 * h / w)), interpolation=cv2.INTER_AREA),
                                 f"modo_{k}.jpg")
        part = im[round(y0 * s):round((y0 + ch) * s), round(x0 * s):round((x0 + cw) * s)]
        part = cv2.resize(part, (cw * 2, ch * 2), interpolation=cv2.INTER_CUBIC if s < 2 else cv2.INTER_AREA)
        res["detail"][k] = save_u8(np.clip(part, 0, 1), f"modo_{k}_det.jpg", q=90)
    return res


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    s = (SRC / "data.js").read_text(encoding="utf-8")
    data = json.loads(s[s.index("{"):s.rindex("}") + 1])
    for f in data["fotogrammi"]:
        for k in ("negativo", "telefono", "risultato", "scansione", "stampa"):
            recompress(f[k])
    for p in data["passi"]["passi"]:
        recompress(p["img"])
    data["modalita"] = modes()
    data["credito"] = CREDIT
    (OUT / "data").mkdir(exist_ok=True)
    (OUT / "data" / "gallery.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(p.stat().st_size for p in IMG.glob("*.jpg"))
    print(f"ok: {len(list(IMG.glob('*.jpg')))} immagini, {total / 1e6:.1f} MB", file=sys.stderr)


if __name__ == "__main__":
    main()
