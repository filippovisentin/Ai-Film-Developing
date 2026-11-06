"""Pipeline completa: dai file del rullino alla versione Originale di ogni fotogramma."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .calibration import correct_light, estimate_base_from_border
from .geometry import find_frame_corners, warp_frame
from .imageio_ import load_image, save_outputs
from .invert import compute_roll_levels, render_positive, to_density
from .profile import FilmProfile


@dataclass
class Calibration:
    base_rgb: np.ndarray | None = None
    light: np.ndarray | None = None


@dataclass
class FrameResult:
    source: Path
    outputs: tuple[Path, Path]
    warnings: list[str] = field(default_factory=list)


def _warn(msg: str) -> None:
    print(f"Attenzione: {msg}", file=sys.stderr)


BRIGHTER_TOLERANCE = 1.02
FRAME_BASE_PCT = 99.9


def _frame_base(f: Path, img: np.ndarray, base: np.ndarray, w: list[str]) -> np.ndarray:
    """Le zone più chiare di un negativo sono la base stessa: se il fotogramma ne ha di più
    chiare della base misurata (esposizione diversa, porta-negativi scuro ai bordi), la base
    di quel fotogramma viene alzata, altrimenti le ombre verrebbero appiattite."""
    brightest = np.percentile(img.reshape(-1, 3), FRAME_BASE_PCT, axis=0).astype(np.float32)
    if np.any(brightest > base * BRIGHTER_TOLERANCE):
        w.append(f"{f.name}: fotogramma più chiaro della base misurata "
                 "(esposizione diversa?), base corretta per questo fotogramma")
        return np.maximum(base, brightest)
    return base


def develop_roll(frames: list[Path], profile: FilmProfile, calib: Calibration,
                 out_dir: Path, crop: bool = True) -> list[FrameResult]:
    frames = sorted((Path(f) for f in frames), key=lambda p: (p.name, str(p)))
    if not frames:
        raise ValueError("Nessun fotogramma da sviluppare")
    out_dir = Path(out_dir)

    prepared: list[np.ndarray] = []
    warnings: list[list[str]] = []
    base_candidates: list[np.ndarray] = []
    for f in frames:
        loaded = load_image(f)
        w = list(loaded.warnings)
        img = correct_light(loaded.rgb, calib.light)
        if calib.base_rgb is None and profile.type != "slide":
            base_candidates.append(estimate_base_from_border(img))
        if crop:
            corners = find_frame_corners(img)
            if corners is None:
                w.append(f"{f.name}: fotogramma non trovato, uso l'immagine intera")
            else:
                img = warp_frame(img, corners)
        prepared.append(img)
        warnings.append(w)

    if profile.type == "slide":
        data = prepared
    else:
        if calib.base_rgb is not None:
            base = np.asarray(calib.base_rgb, np.float32)
        else:
            base = np.median(np.stack(base_candidates), axis=0).astype(np.float32)
            msg = "base stimata dai bordi dei fotogrammi (calibrazione assente, meno precisa)"
            _warn(msg)
            for w in warnings:
                w.append(msg)
        data = []
        for f, img, w in zip(frames, prepared, warnings):
            data.append(to_density(img, _frame_base(f, img, base, w)))

    levels = compute_roll_levels(data, profile)
    results = []
    for f, d, w in zip(frames, data, warnings):
        for msg in w:
            if "base stimata" not in msg:
                _warn(msg)
        outputs = save_outputs(render_positive(d, profile, levels), out_dir / f"{f.stem}_originale")
        results.append(FrameResult(source=f, outputs=outputs, warnings=w))
    return results
