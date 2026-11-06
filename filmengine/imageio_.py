"""Lettura delle foto in valori lineari e scrittura delle versioni finali."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import imageio.v3 as iio
import numpy as np
import tifffile

RAW_EXT = {".dng"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
SUPPORTED = sorted(RAW_EXT | IMG_EXT)


@dataclass
class LoadedImage:
    rgb: np.ndarray
    is_raw: bool
    warnings: list[str] = field(default_factory=list)


def srgb_to_linear(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.float32)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0).astype(np.float32)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055).astype(np.float32)


def _to_rgb3(a: np.ndarray) -> np.ndarray:
    if a.ndim == 2:
        a = np.stack([a] * 3, axis=-1)
    return a[..., :3]


def _load_raw(path: Path) -> np.ndarray:
    import rawpy

    with rawpy.imread(str(path)) as raw:
        out = raw.postprocess(
            gamma=(1, 1),
            no_auto_bright=True,
            output_bps=16,
            use_camera_wb=False,
            use_auto_wb=False,
            user_wb=[1.0, 1.0, 1.0, 1.0],
            output_color=rawpy.ColorSpace.sRGB,
        )
    return out.astype(np.float32) / 65535.0


def load_image(path: str | Path) -> LoadedImage:
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in RAW_EXT | IMG_EXT:
        raise ValueError(
            f"Formato non supportato: {ext or '(nessuna estensione)'}. "
            f"Formati ammessi: {' '.join(SUPPORTED)}"
        )
    if not path.exists():
        raise FileNotFoundError(f"File non trovato: {path}")
    if ext in RAW_EXT:
        return LoadedImage(_load_raw(path), is_raw=True)

    a = _to_rgb3(iio.imread(path))
    if a.dtype == np.uint8:
        v = a.astype(np.float32) / 255.0
    elif a.dtype == np.uint16:
        v = a.astype(np.float32) / 65535.0
    else:
        v = np.clip(a.astype(np.float32), 0.0, 1.0)
    warn = [
        f"{path.name}: immagine non RAW, linearizzata con la curva sRGB "
        "(qualità inferiore a uno scatto DNG)"
    ]
    return LoadedImage(srgb_to_linear(v), is_raw=False, warnings=warn)


def save_outputs(rgb_linear: np.ndarray, out_stem: Path) -> tuple[Path, Path]:
    out_stem = Path(out_stem)
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    enc = linear_to_srgb(rgb_linear)
    tif = out_stem.with_suffix(".tif")
    jpg = out_stem.with_suffix(".jpg")
    tifffile.imwrite(tif, np.round(enc * 65535).astype(np.uint16), photometric="rgb")
    iio.imwrite(jpg, np.round(enc * 255).astype(np.uint8), quality=95)
    return tif, jpg
