"""Multi-scatto: più foto dello stesso fotogramma, allineate e mediate.

Il rumore del sensore del telefono è diverso in ogni scatto, l'immagine no: la media di N scatti
allineati riduce il rumore di circa radice di N, senza inventare nulla (niente AI).
Uno scatto che non si riesce ad allineare (mosso, fotogramma sbagliato) viene scartato.
"""
from __future__ import annotations

import cv2
import numpy as np

ALIGN_LONG_SIDE = 800       # risoluzione per stimare l'allineamento
MIN_CORRELATION = 0.50      # stesso fotogramma con rumore: ~0,8; fotogramma diverso: ~0,1


def _gray(img: np.ndarray, scale: float) -> np.ndarray:
    g = np.log10(np.clip(img.mean(axis=-1), 1e-4, None)).astype(np.float32)
    if scale != 1.0:
        g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(g, (0, 0), 1.0)
    return (g - g.mean()) / max(float(g.std()), 1e-6)


def _align(ref_g: np.ndarray, img_g: np.ndarray) -> tuple[np.ndarray, float] | None:
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        cc, warp = cv2.findTransformECC(ref_g, img_g, warp, cv2.MOTION_EUCLIDEAN,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5),
                                        None, 5)
    except cv2.error:
        return None
    return warp, float(cc)


def stack_captures(images: list[np.ndarray], return_report: bool = False):
    if not images:
        raise ValueError("Nessuno scatto da unire")
    ref = images[0]
    if any(im.shape != ref.shape for im in images):
        raise ValueError("Gli scatti da unire devono avere le stesse dimensioni")
    if len(images) == 1:
        return (ref, {"usati": 1, "scartati": 0}) if return_report else ref

    h, w = ref.shape[:2]
    scale = min(1.0, ALIGN_LONG_SIDE / max(h, w))
    ref_g = _gray(ref, scale)
    total = ref.astype(np.float64).copy()
    count = np.ones((h, w, 1), np.float64)
    used, dropped = 1, 0
    for im in images[1:]:
        res = _align(ref_g, _gray(im, scale))
        if res is None or res[1] < MIN_CORRELATION:
            dropped += 1
            continue
        warp = res[0].copy()
        warp[:, 2] /= scale  # la traslazione stimata a bassa risoluzione, riportata a piena
        flags = cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP
        moved = cv2.warpAffine(im, warp, (w, h), flags=flags, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        valid = cv2.warpAffine(np.ones((h, w), np.float32), warp, (w, h), flags=flags,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0)[..., None]
        valid = (valid > 0.999).astype(np.float64)
        total += moved * valid
        count += valid
        used += 1
    out = (total / count).astype(np.float32)
    report = {"usati": used, "scartati": dropped}
    return (out, report) if return_report else out
