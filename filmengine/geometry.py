"""Rilevamento del fotogramma, raddrizzamento prospettico e ritaglio."""
from __future__ import annotations

import cv2
import numpy as np

MIN_AREA_FRACTION = 0.20
MIN_RECT_FILL = 0.90


def _order(pts: np.ndarray) -> np.ndarray:
    """Ordina gli angoli: alto-sinistra, alto-destra, basso-destra, basso-sinistra."""
    s = pts.sum(axis=1)
    d = pts[:, 1] - pts[:, 0]
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
                    np.float32)


def _otsu(values: np.ndarray) -> float:
    v = values.astype(np.uint8).reshape(1, -1)
    t, _ = cv2.threshold(v, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return float(t)


def _touches_border(c: np.ndarray, shape: tuple[int, ...], margin: int = 2) -> bool:
    x, y, w, h = cv2.boundingRect(c)
    return x <= margin or y <= margin or x + w >= shape[1] - margin or y + h >= shape[0] - margin


def _quad(c: np.ndarray) -> np.ndarray | None:
    approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
    if len(approx) == 4 and cv2.isContourConvex(approx):
        return _order(approx.reshape(4, 2).astype(np.float32))
    rect = cv2.minAreaRect(c)
    if cv2.contourArea(c) / max(rect[1][0] * rect[1][1], 1.0) >= MIN_RECT_FILL:
        return _order(cv2.boxPoints(rect).astype(np.float32))
    return None


def find_frame_corners(img: np.ndarray, aspect: float = 1.5) -> np.ndarray | None:
    """Cerca il fotogramma: la zona scura più grande che non tocca i bordi della foto.

    La foto contiene fino a quattro livelli di luminosità (porta-negativi nero, fotogramma,
    base della pellicola, luce nuda): si provano più soglie, così il fotogramma emerge
    qualunque sia lo sfondo.
    """
    lum = np.log10(np.clip(img.mean(axis=-1), 1e-4, None))
    if float(lum.max() - lum.min()) < 1e-3:
        return None
    lum8 = cv2.normalize(lum, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    lum8 = cv2.GaussianBlur(lum8, (0, 0), max(1.0, 0.003 * min(img.shape[:2])))
    t1 = _otsu(lum8)
    thresholds = {t1}
    for part in (lum8[lum8 <= t1], lum8[lum8 > t1]):
        if part.size and part.min() != part.max():
            thresholds.add(_otsu(part))
    min_area = MIN_AREA_FRACTION * img.shape[0] * img.shape[1]
    best, best_area = None, 0.0
    kernel = np.ones((5, 5), np.uint8)
    for t in sorted(thresholds):
        mask = cv2.morphologyEx((lum8 <= t).astype(np.uint8) * 255, cv2.MORPH_CLOSE, kernel)
        # CCOMP: al primo livello ci sono i bordi esterni di TUTTE le zone scure, anche quelle
        # dentro un buco di un'altra (il fotogramma dentro la finestra del porta-negativi)
        contours, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        outer = [c for c, hh in zip(contours, hier[0]) if hh[3] == -1] if contours else []
        for c in outer:
            area = cv2.contourArea(c)
            if area < min_area or area <= best_area or _touches_border(c, img.shape):
                continue
            q = _quad(c)
            if q is not None:
                best, best_area = q, area
    return best


def warp_frame(img: np.ndarray, corners: np.ndarray, aspect: float = 1.5) -> np.ndarray:
    tl, tr, br, bl = corners
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    if width >= height:
        out_w = int(round(width))
        out_h = int(round(width / aspect))
    else:
        out_h = int(round(height))
        out_w = int(round(height / aspect))
    dst = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], np.float32)
    m = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    # bilineare: la cubica oscilla sotto zero ai bordi netti e falsa le densità
    return cv2.warpPerspective(img, m, (out_w, out_h), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)


DARK_EDGE_RATIO = 0.25
DARK_EDGE_MAX_FRAC = 0.05


def trim_dark_edges(img: np.ndarray, ratio: float = DARK_EDGE_RATIO,
                    max_frac: float = DARK_EDGE_MAX_FRAC) -> np.ndarray:
    """Rifila le strisce quasi nere sui bordi (porta-negativi, bordo dello scanner).

    Sul negativo il nero è la densità massima: se restassero, verrebbero prese per le luci
    più forti della foto. Una zona scura più larga di `max_frac` è contenuto e non si tocca.
    """
    lum = img.mean(axis=-1)
    limit = ratio * float(np.median(lum))

    def count(lines: np.ndarray) -> int:
        n = int(max_frac * lines.shape[0])
        dark = np.median(lines[:n + 1], axis=1) < limit
        k = int(np.argmin(dark)) if not dark.all() else n + 1
        return 0 if k > n else k

    top, bottom = count(lum), count(lum[::-1])
    left, right = count(lum.T), count(lum.T[::-1])
    h, w = lum.shape
    return img[top:h - bottom, left:w - right]
