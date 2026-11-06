"""Miglioramento della qualità dopo lo sviluppo (versione "Migliorata").

Due livelli, tenuti separati di proposito:
- `enhance`: pulisce ciò che c'è già (polvere, rumore, nitidezza). Non aggiunge dettagli.
- `super_resolve`: rete neurale Real-ESRGAN General x4v3 (Qualcomm AI Hub, BSD-3) che
  INVENTA pixel plausibili per ingrandire l'immagine. Il dettaglio aggiunto non esisteva
  sulla pellicola: va sempre presentato come tale.

Tutte le funzioni lavorano su RGB lineare float32 in [0, 1].
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .imageio_ import linear_to_srgb, srgb_to_linear

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
DEFAULT_MODEL = MODELS_DIR / "real_esrgan_general_x4v3.onnx"
RESTORE_MODEL = MODELS_DIR / "restore_v1.onnx"
RESTORE_TILE, RESTORE_PAD = 512, 24
SR_TILE, SR_SCALE, SR_OVERLAP = 128, 4, 16
DUST_CONTRAST, DUST_RING_STD, DUST_CHROMA, DUST_MIN_BG = 0.25, 0.03, 0.25, 0.25

_LAPLACE = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)


def estimate_noise(rgb: np.ndarray) -> float:
    """Deviazione standard del rumore (metodo di Immerkaer con mediana: robusto ai bordi)."""
    sig = []
    for c in range(rgb.shape[-1]):
        r = np.abs(cv2.filter2D(rgb[..., c].astype(np.float32), -1, _LAPLACE)[1:-1, 1:-1])
        sig.append(np.median(r) / 0.6745 / 6.0)
    return float(np.mean(sig))


def _guided(guide: np.ndarray, src: np.ndarray, r: int, eps: float) -> np.ndarray:
    """Filtro guidato (He et al.): leviga src seguendo i bordi di guide."""
    k = (2 * r + 1, 2 * r + 1)
    box = lambda a: cv2.boxFilter(a, -1, k, borderType=cv2.BORDER_REFLECT)  # noqa: E731
    mg, ms = box(guide), box(src)
    cov = box(guide * src) - mg * ms
    var = box(guide * guide) - mg * mg
    a = cov / (var + eps)
    b = ms - a * mg
    return box(a) * guide + box(b)


def denoise(rgb: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Riduce il rumore: forte sul colore (macchie colorate), delicato sulla luminanza."""
    rgb = rgb.astype(np.float32)
    # in scala percettiva il rumore è circa uniforme tra luci e ombre (come nel JPEG del telefono)
    enc = linear_to_srgb(np.clip(rgb, 0, 1))
    sigma = estimate_noise(enc) * strength
    if sigma < 1e-3:
        return rgb.copy()
    lum = enc.mean(-1)
    chroma = enc - lum[..., None]
    lum_d = lum
    for _ in range(2):
        lum_d = cv2.bilateralFilter(lum_d, 0, 2.5 * sigma, 2.0)
    out = np.empty_like(enc)
    for c in range(3):
        out[..., c] = lum_d + _guided(lum_d, chroma[..., c], 4, (3 * sigma) ** 2)
    return srgb_to_linear(np.clip(out, 0, 1)).astype(np.float32)


def _fill(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Riempie i pixel mascherati con la media pesata dei vicini buoni (convoluzione normalizzata)."""
    good = (~mask).astype(np.float32)
    fill = rgb.copy()
    for sigma in (2.0, 4.0, 8.0):
        den = cv2.GaussianBlur(good, (0, 0), sigma)
        num = cv2.GaussianBlur(rgb * good[..., None], (0, 0), sigma)
        ok = mask & (den > 1e-3)
        fill[ok] = num[ok] / den[ok, None]
        if ok.sum() == mask.sum():
            break
    out = rgb.copy()
    out[mask] = fill[mask]
    return out


def remove_dust(rgb: np.ndarray, max_area: int = 80, return_count: bool = False):
    """Toglie i puntini chiari di polvere (sul negativo sono scuri, nel positivo bianchi)."""
    rgb = rgb.astype(np.float32)
    lum = np.sqrt(np.clip(rgb.mean(-1), 0, 1))  # scala percettiva
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    tophat = lum - cv2.morphologyEx(lum, cv2.MORPH_OPEN, kern)
    thr = max(0.12, 8 * estimate_noise(lum[..., None]))
    n, lab, stats, _ = cv2.connectedComponentsWithStats((tophat > thr).astype(np.uint8), 8)
    mask = np.zeros(lum.shape, np.uint8)
    ring_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    count = 0
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area > max_area:
            continue
        y0, y1, x0, x1 = max(y - 6, 0), y + h + 6, max(x - 6, 0), x + w + 6
        comp = (lab[y0:y1, x0:x1] == i).astype(np.uint8)
        ring = cv2.dilate(comp, ring_k).astype(bool) & ~comp.astype(bool)
        if not ring.any():
            continue
        win = lum[y0:y1, x0:x1]
        inside = comp.astype(bool)
        # polvere = puntino neutro (blocca tutti i colori), molto più chiaro di un intorno
        # uniforme. Le texture vere (foglie, finestre, luci) hanno intorno vario o colore.
        if win[inside].max() - np.percentile(win[ring], 90) < max(thr, DUST_CONTRAST):
            continue
        if np.median(win[ring]) < DUST_MIN_BG:  # nelle ombre un puntino può essere una luce vera
            continue
        if win[ring].std() > DUST_RING_STD:
            continue
        px = rgb[y0:y1, x0:x1][inside]
        if (px.max(-1) - px.min(-1)).mean() > DUST_CHROMA * px.mean():
            continue
        mask[y0:y1, x0:x1] |= comp
        count += 1
    out = rgb
    if count:
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        out = _fill(rgb, mask.astype(bool))
    return (out, count) if return_count else out


def sharpen(rgb: np.ndarray, amount: float = 1.0, radius: float = 1.5,
            noise: float | None = None) -> np.ndarray:
    """Maschera di contrasto sulla luminanza percettiva, con soglia che ignora il rumore fine."""
    rgb = rgb.astype(np.float32)
    enc = linear_to_srgb(np.clip(rgb, 0, 1))
    lum = enc.mean(-1)
    detail = lum - cv2.GaussianBlur(lum, (0, 0), radius)
    # soglia dal rumore dello scatto originale: dopo `denoise` la stima sarebbe troppo bassa
    t = max(0.006, 3 * (estimate_noise(enc) if noise is None else noise))
    gain = amount * np.clip((np.abs(detail) - t) / t, 0, 1)
    out = enc + (gain * detail)[..., None]
    return srgb_to_linear(np.clip(out, 0, 1)).astype(np.float32)


def enhance(rgb: np.ndarray, dust: bool = True, noise: bool = True, sharp: bool = True) -> np.ndarray:
    """Versione migliorata senza pixel inventati: polvere → rumore → nitidezza."""
    out = rgb.astype(np.float32)
    sigma = estimate_noise(linear_to_srgb(np.clip(out, 0, 1)))
    if dust:
        out = remove_dust(out)
    if noise:
        out = denoise(out)
    if sharp:
        # dose moderata: misurato sul simulatore, a dose piena la nitidezza si allontana
        # dalla scansione di riferimento (errore di dettaglio 0.0322 contro 0.0298)
        out = sharpen(out, amount=0.5, noise=sigma)
    return np.clip(out, 0, 1).astype(np.float32)


_SESSIONS: dict[str, object] = {}


def restore(rgb: np.ndarray, model_path: Path | None = None) -> np.ndarray:
    """Rete addestrata a togliere rumore, blocchi JPEG e morbidezza dello scatto da telefono.

    Non ingrandisce: ricostruisce ciò che lo scatto ha degradato (addestrata su coppie
    scatto simulato → sviluppo pulito, vedi tools/train_restore.py).
    """
    model_path = Path(model_path or RESTORE_MODEL)
    if not model_path.exists():
        raise FileNotFoundError(f"Rete di restauro assente ({model_path}): addestrala con "
                                "'python -m tools.restore_data' e 'python -m tools.train_restore'")
    sess = _session(model_path)
    name = sess.get_inputs()[0].name
    enc = linear_to_srgb(np.clip(rgb.astype(np.float32), 0, 1))
    h, w = enc.shape[:2]
    P, T = RESTORE_PAD, RESTORE_TILE
    pad = cv2.copyMakeBorder(enc, P, P, P, P, cv2.BORDER_REFLECT)
    out = np.empty_like(enc)
    for y in range(0, h, T):
        for x in range(0, w, T):
            th, tw = min(T, h - y), min(T, w - x)
            tile = pad[y:y + th + 2 * P, x:x + tw + 2 * P].transpose(2, 0, 1)[None]
            res = sess.run(None, {name: np.ascontiguousarray(tile, np.float32)})[0][0].transpose(1, 2, 0)
            out[y:y + th, x:x + tw] = res[P:P + th, P:P + tw]
    return srgb_to_linear(np.clip(out, 0, 1)).astype(np.float32)


def _session(model_path: Path):
    key = str(model_path)
    if key not in _SESSIONS:
        import onnxruntime as ort

        _SESSIONS[key] = ort.InferenceSession(key, providers=["CPUExecutionProvider"])
    return _SESSIONS[key]


def super_resolve(rgb: np.ndarray, scale: int = 4, model_path: Path | None = None) -> np.ndarray:
    """Ingrandisce ×4 (o ×2) con Real-ESRGAN: aggiunge dettagli inventati dalla rete."""
    model_path = Path(model_path or DEFAULT_MODEL)
    if not model_path.exists():
        raise FileNotFoundError(f"Modello AI assente ({model_path}): scaricalo con "
                                "'python -m tools.get_model'")
    if scale not in (2, 4):
        raise ValueError("scala ammessa: 2 o 4")
    sess = _session(model_path)
    name = sess.get_inputs()[0].name
    enc = linear_to_srgb(np.clip(rgb.astype(np.float32), 0, 1))
    h, w = enc.shape[:2]
    step = SR_TILE - 2 * SR_OVERLAP
    ny, nx = max(1, -(-(h - 2 * SR_OVERLAP) // step)), max(1, -(-(w - 2 * SR_OVERLAP) // step))
    ph, pw = ny * step + 2 * SR_OVERLAP, nx * step + 2 * SR_OVERLAP
    pad = cv2.copyMakeBorder(enc, 0, max(ph - h, 0), 0, max(pw - w, 0), cv2.BORDER_REFLECT)
    S, O = SR_SCALE, SR_OVERLAP * SR_SCALE
    acc = np.zeros((ph * S, pw * S, 3), np.float32)
    wsum = np.zeros((ph * S, pw * S, 1), np.float32)
    ramp = np.ones(SR_TILE * S, np.float32)
    ramp[:O] = ramp[-O:][::-1] = (np.arange(O, dtype=np.float32) + 0.5) / O
    weight = np.outer(ramp, ramp)[..., None]
    for ty in range(ny):
        for tx in range(nx):
            y, x = ty * step, tx * step
            tile = pad[y:y + SR_TILE, x:x + SR_TILE].transpose(2, 0, 1)[None]
            up = sess.run(None, {name: np.ascontiguousarray(tile, np.float32)})[0][0].transpose(1, 2, 0)
            acc[y * S:(y + SR_TILE) * S, x * S:(x + SR_TILE) * S] += up * weight
            wsum[y * S:(y + SR_TILE) * S, x * S:(x + SR_TILE) * S] += weight
    out = (acc / np.maximum(wsum, 1e-6))[:h * S, :w * S]
    if scale == 2:
        out = cv2.resize(out, (w * 2, h * 2), interpolation=cv2.INTER_AREA)
    return srgb_to_linear(np.clip(out, 0, 1)).astype(np.float32)
