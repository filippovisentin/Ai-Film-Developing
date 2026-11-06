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


def find_frame_corners(img: np.ndarray, aspect: float = 1.5) -> np.ndarray | None:
    lum = np.log10(np.clip(img.mean(axis=-1), 1e-4, None))
    if float(lum.max() - lum.min()) < 1e-3:
        return None
    lum8 = cv2.normalize(lum, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    lum8 = cv2.GaussianBlur(lum8, (0, 0), max(1.0, 0.003 * min(img.shape[:2])))
    # il fotogramma è più denso (più scuro) della base: diventa il primo piano
    _, mask = cv2.threshold(lum8, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if area < MIN_AREA_FRACTION * img.shape[0] * img.shape[1]:
        return None
    approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
    if len(approx) == 4 and cv2.isContourConvex(approx):
        return _order(approx.reshape(4, 2).astype(np.float32))
    rect = cv2.minAreaRect(c)
    if area / max(rect[1][0] * rect[1][1], 1.0) >= MIN_RECT_FILL:
        return _order(cv2.boxPoints(rect).astype(np.float32))
    return None


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
    # bilineare: la cubica oscilla sotto zero ai bordi netti e falsa le densit�
    return cv2.warpPerspective(img, m, (out_w, out_h), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)
