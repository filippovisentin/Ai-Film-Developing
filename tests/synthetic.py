"""Generatore deterministico di scene e negativi sintetici per i test."""
from __future__ import annotations

import numpy as np

SCENE_MIN = 0.01
# patch grigia neutra: righe/colonne nella scena (prima di aggiungere il bordo)
GRAY = (slice(20, 50), slice(20, 60))
GRAY_VALUE = 0.18
# patch bianca neutra: è il punto più chiaro della scena su ogni canale
WHITE = (slice(20, 50), slice(70, 110))
WHITE_VALUE = 0.9


def make_scene(h: int = 200, w: int = 300, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.stack([
        0.05 + 0.6 * x / w,
        0.05 + 0.6 * y / h,
        0.05 + 0.6 * (1 - x / w) * (y / h),
    ], axis=-1)
    for _ in range(6):
        cy, cx = rng.integers(60, h - 30), rng.integers(80, w - 30)
        base[cy - 20:cy + 20, cx - 25:cx + 25] = rng.uniform(0.02, 0.85, 3)
    base[GRAY] = GRAY_VALUE
    base[WHITE] = WHITE_VALUE
    return np.clip(base, SCENE_MIN, 1.0).astype(np.float32)


def make_light(h: int, w: int, vignette: float = 0.0) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = ((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2
    f = 1.0 - vignette * r2 / 2.0
    return np.repeat(f[..., None], 3, axis=2).astype(np.float32)


def make_negative(scene, mask_rgb, gamma_rgb, border_px: int = 20, vignette: float = 0.0):
    mask = np.asarray(mask_rgb, np.float32)
    gamma = np.asarray(gamma_rgb, np.float32)
    t = mask * (scene / SCENE_MIN) ** (-gamma)
    h, w = scene.shape[:2]
    neg = np.empty((h + 2 * border_px, w + 2 * border_px, 3), np.float32)
    neg[:] = mask
    neg[border_px:border_px + h, border_px:border_px + w] = t
    return (neg * make_light(*neg.shape[:2], vignette)).astype(np.float32)
