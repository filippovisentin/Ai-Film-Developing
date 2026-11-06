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


# i bordi del fotogramma sono inaffidabili (transizioni dello scanner o del ritaglio, luce che
# filtra, velo): i livelli si misurano senza una cornice esterna
EDGE_IGNORE_FRAC = 0.02


def _frame_percentiles(lexp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h, w = lexp.shape[:2]
    my, mx = int(EDGE_IGNORE_FRAC * h), int(EDGE_IGNORE_FRAC * w)
    if h - 2 * my > 10 and w - 2 * mx > 10:
        lexp = lexp[my:h - my, mx:w - mx]
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


LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def gamut_map(rgb: np.ndarray) -> np.ndarray:
    """Porta i colori dentro [0, 1] mantenendo tinta e luminanza.

    Un taglio canale per canale cambia la tinta (un arancio troppo saturo diventa giallo).
    Qui un colore fuori gamma viene invece desaturato verso il grigio della sua stessa
    luminanza, quanto basta per rientrare; i colori già nel gamut non cambiano.
    """
    rgb = np.asarray(rgb, np.float32)
    lum = rgb @ LUMA
    d = rgb - lum[..., None]
    mx, mn = rgb.max(axis=-1), rgb.min(axis=-1)
    t = np.ones_like(lum)
    over = mx > 1.0
    t[over] = np.minimum(t[over], (1.0 - lum[over]) / np.maximum(mx[over] - lum[over], 1e-6))
    under = mn < 0.0
    t[under] = np.minimum(t[under], lum[under] / np.maximum(lum[under] - mn[under], 1e-6))
    t = np.clip(t, 0.0, 1.0)
    out = np.clip(lum, 0.0, 1.0)[..., None] + t[..., None] * d
    inside = (mx <= 1.0) & (mn >= 0.0)
    out[inside] = rgb[inside]
    return np.clip(out, 0.0, 1.0).astype(np.float32)


AE_POWER_RANGE = (0.5, 2.0)


def _auto_expose(n: np.ndarray, strength: float, target: float) -> np.ndarray:
    """Curva di potenza che sposta la mediana dei mezzitoni verso `target`; 0 e 1 restano fissi.

    È ciò che fa una stampatrice di laboratorio quando "integra" la densità del fotogramma:
    una foto sottoesposta viene stampata più chiara, una sovraesposta più scura.
    """
    h, w = n.shape[:2]
    my, mx = int(EDGE_IGNORE_FRAC * h), int(EDGE_IGNORE_FRAC * w)
    core = n[my:h - my or None, mx:w - mx or None].mean(-1).ravel()
    m = float(np.clip(np.median(core[:: max(1, core.size // MAX_SAMPLES)]), 0.05, 0.95))
    goal = np.exp((1 - strength) * np.log(m) + strength * np.log(target))
    p = float(np.clip(np.log(goal) / np.log(m), *AE_POWER_RANGE))
    return np.power(n, p).astype(np.float32)


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
    if profile.auto_exposure > 0:
        n = _auto_expose(n, profile.auto_exposure, profile.exposure_target)
    g = tone_curve(n, profile.s_curve)
    # carta da stampa: distende la gamma della scena sulla gamma di densità della carta
    # senza carta: gamma per canale, cioè la scena lineare ricostruita fedelmente
    rng = profile.paper_range if profile.paper_range is not None else span
    scene = np.power(10.0, (g - 1.0) * rng)
    printed = scene ** profile.print_contrast
    out = printed @ np.asarray(profile.color_matrix, np.float32).T
    return gamut_map(out)
