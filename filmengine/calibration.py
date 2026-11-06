"""Calibrazione del rullino: correzione della luce non uniforme e misura della base."""
from __future__ import annotations

import cv2
import numpy as np

EPS = 1e-4
# dopo la correzione della luce, la luce nuda vale ~1.0: la base è sempre più scura
BARE_LIGHT = 0.97


def correct_light(img: np.ndarray, light: np.ndarray | None) -> np.ndarray:
    if light is None:
        return img
    if light.shape != img.shape:
        raise ValueError(
            f"La foto della luce ha dimensioni {light.shape[1]}x{light.shape[0]}, "
            f"il fotogramma {img.shape[1]}x{img.shape[0]}: scattale con lo stesso "
            "orientamento e la stessa risoluzione"
        )
    sigma = max(1.0, 0.02 * min(light.shape[:2]))
    blurred = cv2.GaussianBlur(light.astype(np.float32), (0, 0), sigma)
    norm = np.percentile(blurred, 99, axis=(0, 1))
    field = np.maximum(blurred / np.maximum(norm, EPS), EPS)
    return (img / field).astype(np.float32)


def measure_base(base_img: np.ndarray) -> np.ndarray:
    h, w = base_img.shape[:2]
    center = base_img[h // 4: h - h // 4, w // 4: w - w // 4].reshape(-1, 3)
    return np.maximum(np.median(center, axis=0), EPS).astype(np.float32)


def estimate_base_from_border(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    b = max(1, int(round(0.05 * min(h, w))))
    band = np.concatenate([
        img[:b].reshape(-1, 3), img[-b:].reshape(-1, 3),
        img[:, :b].reshape(-1, 3), img[:, -b:].reshape(-1, 3),
    ])
    film = band[~np.all(band >= BARE_LIGHT, axis=1)]
    if len(film) == 0:
        film = band
    return np.maximum(np.percentile(film, 99.5, axis=0), EPS).astype(np.float32)


LIGHT_CLIP_LEVEL = 0.99
LIGHT_CLIP_FRACTION = 0.005


def light_is_clipped(light: np.ndarray) -> bool:
    """Una foto della luce con zone bruciate non descrive più la luce: va rifatta più scura."""
    return float(np.mean(np.any(light >= LIGHT_CLIP_LEVEL, axis=-1))) > LIGHT_CLIP_FRACTION
