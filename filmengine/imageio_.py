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
    try:
        import rawpy
    except ImportError as e:  # pragma: no cover - dipende dall'installazione
        raise ValueError("DNG non leggibile: il modulo rawpy non è installato") from e
    try:
        with rawpy.imread(str(path)) as raw:
            # bilanciamento della camera PRIMA della matrice colore: senza, sotto la maschera
            # arancione il blu diventa negativo e LibRaw lo taglia a 0 (dettaglio perso).
            # I guadagni per canale si annullano poi dividendo per la base.
            out = raw.postprocess(
                gamma=(1, 1),
                no_auto_bright=True,
                output_bps=16,
                use_camera_wb=True,
                use_auto_wb=False,
                output_color=rawpy.ColorSpace.sRGB,
            )
    except (rawpy.LibRawError, OSError) as e:
        raise ValueError(f"DNG non leggibile: {path.name} ({e})") from e
    return out.astype(np.float32) / 65535.0


def _read_oriented(path: Path) -> np.ndarray:
    """Legge un'immagine applicando la rotazione EXIF, come fa la galleria del telefono."""
    from PIL import Image, ImageOps

    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("I;16", "I;16B", "I;16L", "I"):
            return np.asarray(im).astype(np.uint16)
        if im.mode not in ("RGB", "RGBA", "L"):
            im = im.convert("RGB")
        return np.asarray(im)


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

    if ext in {".jpg", ".jpeg"}:
        a = _to_rgb3(_read_oriented(path))
    else:
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


def _srgb_icc() -> bytes:
    """Profilo colore sRGB da incorporare: senza, altre app possono interpretare male i colori."""
    from PIL import ImageCms

    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def save_outputs(rgb_linear: np.ndarray, out_stem: Path) -> tuple[Path, Path]:
    from PIL import Image

    out_stem = Path(out_stem)
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    enc = linear_to_srgb(rgb_linear)
    tif = out_stem.with_suffix(".tif")
    jpg = out_stem.with_suffix(".jpg")
    icc = _srgb_icc()
    tifffile.imwrite(tif, np.round(enc * 65535).astype(np.uint16), photometric="rgb",
                     extratags=[(34675, "B", len(icc), icc, True)])
    Image.fromarray(np.round(enc * 255).astype(np.uint8)).save(jpg, quality=95, icc_profile=icc)
    return tif, jpg
