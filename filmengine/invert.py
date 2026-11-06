"""Inversione negativo -> positivo in densità, curve della pellicola e livelli del rullino."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .profile import FilmProfile

RATIO_MIN = 1e-5
MIN_SPAN = 1e-3
MAX_SAMPLES = 200_000
# 0,5/99,5: la polvere (opaca sul negativo) e i riflessi non decidono nero e bianco
LOW_PCT, HIGH_PCT = 0.5, 99.5


def to_density(img: np.ndarray, base: np.ndarray) -> np.ndarray:
    ratio = np.clip(img / np.asarray(base, np.float32), RATIO_MIN, 1.0)
    return (-np.log10(ratio)).astype(np.float32)


@dataclass(frozen=True)
class RollLevels:
    low: np.ndarray
    high: np.ndarray


def _log_exposure(x: np.ndarray, profile: FilmProfile) -> np.ndarray:
    """log10 dell'esposizione relativa della scena, per canale."""
    if profile.type == "slide":
        return np.log10(np.clip(x, RATIO_MIN, 1.0)).astype(np.float32)
    lexp = x / np.asarray(profile.gamma_rgb, np.float32)
    if profile.type == "bw_negative":
        lexp = np.repeat(lexp.mean(axis=-1, keepdims=True), 3, axis=-1)
    return lexp.astype(np.float32)


def _frame_percentiles(lexp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    flat = lexp.reshape(-1, 3)
    step = max(1, len(flat) // MAX_SAMPLES)
    sample = flat[::step]
    return (np.percentile(sample, LOW_PCT, axis=0), np.percentile(sample, HIGH_PCT, axis=0))


def compute_roll_levels(densities: list[np.ndarray], profile: FilmProfile) -> RollLevels:
    if not densities:
        raise ValueError("Il rullino non contiene fotogrammi")
    pct = [_frame_percentiles(_log_exposure(d, profile)) for d in densities]
    low = np.median(np.stack([p[0] for p in pct]), axis=0).astype(np.float32)
    high = np.median(np.stack([p[1] for p in pct]), axis=0).astype(np.float32)
    return RollLevels(low=low, high=high)


def tone_curve(n: np.ndarray, k: float) -> np.ndarray:
    """Curva a S della carta su [0,1]: estremi fissi, monotona; k=0 è l'identità."""
    if k <= 0:
        return n
    lo, hi = 1 / (1 + np.exp(k / 2)), 1 / (1 + np.exp(-k / 2))
    return ((1 / (1 + np.exp(-k * (n - 0.5))) - lo) / (hi - lo)).astype(np.float32)


def render_positive(density_or_slide: np.ndarray, profile: FilmProfile, levels: RollLevels) -> np.ndarray:
    lexp = _log_exposure(density_or_slide, profile)
    low, high = levels.low, levels.high
    if profile.frame_balance > 0:
        # come le stampatrici di laboratorio: ogni fotogramma ha anche il suo bilanciamento
        f_low, f_high = _frame_percentiles(lexp)
        w = profile.frame_balance
        low, high = (1 - w) * low + w * f_low, (1 - w) * high + w * f_high
    span = np.maximum(high - low, MIN_SPAN)
    # nero e bianco del rullino portati allo stesso valore su ogni canale: niente dominanti
    n = np.clip((lexp - low) / span, 0.0, 1.0)
    g = tone_curve(n, profile.s_curve)
    # carta da stampa: distende la gamma della scena sulla gamma di densità della carta
    # senza carta: gamma per canale, cioè la scena lineare ricostruita fedelmente
    rng = profile.paper_range if profile.paper_range is not None else span
    scene = np.power(10.0, (g - 1.0) * rng)
    printed = scene ** profile.print_contrast
    out = printed @ np.asarray(profile.color_matrix, np.float32).T
    return np.clip(out, 0.0, 1.0).astype(np.float32)
