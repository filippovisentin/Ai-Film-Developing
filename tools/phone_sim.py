"""Simula lo scatto di un negativo con lo smartphone su una fonte di luce.

Parte da una scansione reale del negativo e aggiunge, uno per uno, i difetti tipici
dello scatto col telefono: bordo della pellicola, luce nuda o porta-negativi intorno,
inclinazione e prospettiva, luce non uniforme, esposizione e bilanciamento automatici,
riflessi della stanza, sfocatura, rumore del sensore e compressione JPEG.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from filmengine.imageio_ import linear_to_srgb, srgb_to_linear

BASE_TRANSMISSION = 0.8   # la base trasmette ~80% della luce del pannello
REBATE = 0.06             # bordo di pellicola intorno al fotogramma (frazione del lato)
MARGIN = 0.10             # spazio intorno alla pellicola nello scatto
OUT_LONG = 1600


@dataclass(frozen=True)
class PhoneSetup:
    tilt_deg: float = 0.0
    perspective: float = 0.0          # 0.05 = un lato più lungo del 5%
    vignette: float = 0.0             # calo di luce ai bordi (0.4 = -40% agli angoli)
    exposure: float = 1.0
    wb: tuple[float, float, float] = (1.0, 1.0, 1.0)  # bilanciamento automatico del telefono
    veil: float = 0.0                 # riflessi/luce della stanza sommati all'immagine
    blur: float = 0.0                 # sigma in pixel
    noise: float = 0.0                # rumore relativo del sensore
    jpeg_quality: int | None = None
    holder: bool = False              # porta-negativi nero invece della luce nuda intorno
    light_overexposed: bool = False   # foto della luce scattata con la stessa esposizione (bruciata)
    shake_px: float = 0.0             # mano che trema tra gli scatti di una raffica (pixel)


@dataclass
class Capture:
    image: np.ndarray
    light: np.ndarray        # stesso scatto senza pellicola
    base_patch: np.ndarray   # scatto di sola pellicola non esposta
    corners: np.ndarray      # angoli del fotogramma nello scatto (TL, TR, BR, BL)
    true_base: np.ndarray


def _light_field(h: int, w: int, vignette: float) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = (((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2) / 2.0
    return np.repeat((1.0 - vignette * r2)[..., None], 3, axis=2)


def _finish(img: np.ndarray, s: PhoneSetup, rng: np.random.Generator, veil: bool) -> np.ndarray:
    img = img * s.exposure * np.asarray(s.wb, np.float32)
    if veil and s.veil:
        img = img + s.veil
    if s.blur:
        img = cv2.GaussianBlur(img, (0, 0), s.blur)
    if s.noise:
        img = img + rng.normal(0.0, 1.0, img.shape).astype(np.float32) * s.noise * np.sqrt(np.clip(img, 0, None))
    img = np.clip(img, 0.0, 1.0).astype(np.float32)
    if s.jpeg_quality:
        enc = (linear_to_srgb(img) * 255).round().astype(np.uint8)
        ok, buf = cv2.imencode(".jpg", enc[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, int(s.jpeg_quality)])
        img = srgb_to_linear(cv2.imdecode(buf, cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32) / 255.0)
    return img


def simulate(neg: np.ndarray, s: PhoneSetup, seed: int = 0,
             shift: tuple[float, float] = (0.0, 0.0)) -> Capture:
    rng = np.random.default_rng(seed)
    base = np.percentile(neg.reshape(-1, 3), 99.9, axis=0).astype(np.float32)
    k = BASE_TRANSMISSION / float(base.max())
    neg, base = (neg * k).astype(np.float32), base * k

    # striscia di pellicola: fotogramma + bordo non esposto
    h, w = neg.shape[:2]
    rb = int(REBATE * max(h, w))
    strip = np.empty((h + 2 * rb, w + 2 * rb, 3), np.float32)
    strip[:] = base
    strip[rb:rb + h, rb:rb + w] = neg

    # scatto: pellicola al centro, con margine, inclinata e in prospettiva
    sh, sw = strip.shape[:2]
    m = int(MARGIN * max(sh, sw))
    ch, cw = sh + 2 * m, sw + 2 * m
    surround = 0.005 if s.holder else 1.0
    sc0 = OUT_LONG / max(ch, cw)
    c = np.array([cw / 2 + shift[0] / sc0, ch / 2 + shift[1] / sc0], np.float32)
    src = np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]])
    dst = src - [sw / 2, sh / 2]
    dst[1, 1] -= s.perspective * sh / 2
    dst[2, 1] += s.perspective * sh / 2
    a = np.deg2rad(s.tilt_deg)
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]], np.float32)
    dst = (dst @ rot.T + c).astype(np.float32)
    hmat = cv2.getPerspectiveTransform(src, dst)
    scene = cv2.warpPerspective(strip, hmat, (cw, ch), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=(surround,) * 3)
    frame = np.float32([[rb, rb], [rb + w, rb], [rb + w, rb + h], [rb, rb + h]])
    corners = cv2.perspectiveTransform(frame[None], hmat)[0]

    # risoluzione del telefono
    sc = OUT_LONG / max(ch, cw)
    size = (round(cw * sc), round(ch * sc))
    scene = cv2.resize(scene, size, interpolation=cv2.INTER_AREA)
    corners = corners * sc
    light = _light_field(size[1], size[0], s.vignette)
    image = _finish(scene * light, s, rng, veil=True)
    # la foto della luce nuda: l'esposizione automatica la porta all'85%, salvo errore dell'utente
    gain = 1.0 if s.light_overexposed else 0.85 / float(np.max(light * s.exposure * np.asarray(s.wb)))
    light_img = _finish(light * gain, s, np.random.default_rng(seed + 1), veil=False)
    base_img = _finish(np.ones_like(light) * base * light, s, np.random.default_rng(seed + 2), veil=True)
    return Capture(image, light_img, base_img, corners.astype(np.float32), base)


def simulate_burst(neg: np.ndarray, s: PhoneSetup, n: int, seed: int = 0) -> list[Capture]:
    """Raffica di n scatti dello stesso fotogramma: rumore diverso, mano che trema di pochi pixel.
    La foto della luce e quella della base sono una sola per tutta la raffica."""
    rng = np.random.default_rng(seed)
    shots = []
    for i in range(n):
        shift = (0.0, 0.0) if i == 0 else tuple(rng.uniform(-s.shake_px, s.shake_px, 2))
        shots.append(simulate(neg, s, seed=seed * 1000 + i, shift=shift))
    for sh in shots[1:]:
        sh.light, sh.base_patch = shots[0].light, shots[0].base_patch
    return shots
