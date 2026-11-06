"""Rilevamento del fotogramma, raddrizzamento prospettico e ritaglio."""
from __future__ import annotations

import cv2
import numpy as np

MIN_AREA_FRACTION = 0.20
MIN_RECT_FILL = 0.90
# un quadrilatero interno conta come fotogramma se ha almeno questa frazione dell'area esterna
INNER_MIN_FRACTION = 0.5
INNER_MAX_FRACTION = 0.85


RECT_SIDE_TOL = 0.10    # lati opposti: differenza massima (prospettiva leggera)
RECT_ANGLE_TOL = 8.0    # angoli: scarto massimo da 90° (gradi)


def _is_rectangular(q: np.ndarray) -> bool:
    """Un fotogramma è un rettangolo, al più un po' deformato dalla prospettiva."""
    sides = [np.linalg.norm(q[(i + 1) % 4] - q[i]) for i in range(4)]
    for a, b in ((sides[0], sides[2]), (sides[1], sides[3])):
        if abs(a - b) > RECT_SIDE_TOL * max(a, b):
            return False
    for i in range(4):
        u, v = q[i - 1] - q[i], q[(i + 1) % 4] - q[i]
        cos = float(np.dot(u, v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-6))
        if abs(np.degrees(np.arccos(np.clip(cos, -1, 1))) - 90) > RECT_ANGLE_TOL:
            return False
    return True


def _inside(inner: np.ndarray, outer: np.ndarray, tol: float = 3.0) -> bool:
    poly = outer.reshape(-1, 1, 2).astype(np.float32)
    return all(cv2.pointPolygonTest(poly, (float(x), float(y)), True) >= -tol for x, y in inner)


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


def _quad(c: np.ndarray) -> tuple[np.ndarray, bool] | None:
    """Quadrilatero del contorno e se è netto (True) o approssimato da un rettangolo (False)."""
    approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
    if len(approx) == 4 and cv2.isContourConvex(approx):
        return _order(approx.reshape(4, 2).astype(np.float32)), True
    rect = cv2.minAreaRect(c)
    if cv2.contourArea(c) / max(rect[1][0] * rect[1][1], 1.0) >= MIN_RECT_FILL:
        return _order(cv2.boxPoints(rect).astype(np.float32)), False
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
    candidates: list[tuple[float, np.ndarray, bool]] = []
    kernel = np.ones((5, 5), np.uint8)
    for t in sorted(thresholds):
        mask = cv2.morphologyEx((lum8 <= t).astype(np.uint8) * 255, cv2.MORPH_CLOSE, kernel)
        # CCOMP: al primo livello ci sono i bordi esterni di TUTTE le zone scure, anche quelle
        # dentro un buco di un'altra (il fotogramma dentro la finestra del porta-negativi)
        contours, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        outer = [c for c, hh in zip(contours, hier[0]) if hh[3] == -1] if contours else []
        # la finestra del porta-negativi (buco di una zona scura che tocca il bordo) è un
        # candidato anche quando il contorno del fotogramma è irregolare
        windows = []
        for c, hh in zip(contours, hier[0]) if contours else []:
            if hh[3] == -1 and _touches_border(c, img.shape):
                child = hh[2]
                while child != -1:
                    windows.append(contours[child])
                    child = hier[0][child][0]
        for c in outer + windows:
            area = cv2.contourArea(c)
            if area < min_area or _touches_border(c, img.shape):
                continue
            q = _quad(c)
            if q is not None:
                candidates.append((area, *q))
    if not candidates:
        return None
    # si parte dal più grande e si scende verso quello interno: sulla luce nuda il più grande
    # è la striscia di pellicola (fotogramma + bordo chiaro), il fotogramma sta dentro
    candidates.sort(key=lambda a: -a[0])
    best_area, best, _ = candidates[0]
    for area, q, clean in candidates[1:]:
        # lo stesso fotogramma a soglie diverse cambia area di pochi %: serve un oggetto distinto,
        # con un contorno netto (un fotogramma "mangiato" da zone chiare darebbe un ritaglio sbagliato:
        # meglio tenere la finestra e rifilare poi il bordo della pellicola)
        if (clean and _is_rectangular(q) and INNER_MIN_FRACTION * best_area <= area <= INNER_MAX_FRACTION * best_area
                and _inside(q, best)):
            best_area, best = area, q
    return best


ASPECT_SNAP = 0.035  # entro il 3,5% dal formato nominale si aggancia (prospettiva); una striscia con bordo (~1,42) no


def warp_frame(img: np.ndarray, corners: np.ndarray, aspect: float = 1.5) -> np.ndarray:
    """Raddrizza il quadrilatero. Il formato nominale (3:2) si impone solo se quello misurato
    è vicino: una striscia di pellicola con il bordo non va deformata."""
    tl, tr, br, bl = corners
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    measured = max(width, height) / max(min(width, height), 1.0)
    ratio = aspect if abs(measured / aspect - 1) <= ASPECT_SNAP else measured
    if width >= height:
        out_w = int(round(width))
        out_h = int(round(width / ratio))
    else:
        out_h = int(round(height))
        out_w = int(round(height / ratio))
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


REBATE_MAX_FRAC = 0.15
REBATE_UNIFORMITY = 0.02
REBATE_BRIGHTNESS = 0.9


REBATE_LEVEL_TOL = 0.03   # variazione massima di luminosità lungo la fascia di bordo
REBATE_OUTER_FRAC = 0.02   # righe esterne miste (bordo + luce nuda) tollerate prima del bordo
REBATE_SAFETY_FRAC = 0.005  # margine per la transizione sfocata tra bordo e immagine
REBATE_SAFETY_MIN_PX = 4


def trim_rebate_edges(img: np.ndarray, max_frac: float = REBATE_MAX_FRAC) -> np.ndarray:
    """Rifila il bordo non esposto della pellicola rimasto nel ritaglio.

    Il bordo è la zona più chiara del negativo ed è uniforme: righe o colonne ai lati chiare
    quanto la base e senza dettagli vengono tolte. Le primissime righe possono essere miste con
    la luce nuda (non uniformi): si saltano, ma solo se dopo c'è davvero un bordo uniforme.
    Un cielo chiaro ha dettagli e resta.
    """
    lum = cv2.GaussianBlur(img.mean(axis=-1).astype(np.float32), (0, 0), 1.5)
    h, w = lum.shape
    o_h, o_w = max(2, int(REBATE_OUTER_FRAC * h)), max(2, int(REBATE_OUTER_FRAC * w))
    # riferimento di luminosità senza le righe esterne miste con la luce nuda (più chiare del bordo)
    bright = REBATE_BRIGHTNESS * float(np.percentile(lum[o_h:h - o_h, o_w:w - o_w], 99.5))

    def count(lines: np.ndarray) -> int:
        n = int(max_frac * lines.shape[0])
        outer = max(2, int(REBATE_OUTER_FRAC * lines.shape[0]))
        part = lines[:n + 1]
        med = np.median(part, axis=1)
        uniform = (med >= bright) & (part.std(axis=1) <= REBATE_UNIFORMITY * np.maximum(med, 1e-6))
        k, seen = 0, False
        for i in range(len(med)):
            if uniform[i]:
                seen = True
            elif not (med[i] >= bright and i < outer and not seen):
                break
            k = i + 1
        if not seen or k > n:
            return 0
        # la base della pellicola ha una sola luminosità: la si misura vicino al lato, dopo la
        # transizione sfocata, e la fascia finisce dove la luminosità cambia (ombre uniformi
        # dell'immagine possono essere chiare quasi come la base)
        if k > outer + 2:
            ref = float(np.median(med[outer:outer + max(3, (k - outer) // 3)]))
            for i in range(outer, k):
                if abs(med[i] / ref - 1) > REBATE_LEVEL_TOL:
                    k = i
                    break
        return min(k + max(REBATE_SAFETY_MIN_PX, round(REBATE_SAFETY_FRAC * lines.shape[0])), n)

    top, bottom = count(lum), count(lum[::-1])
    left, right = count(lum.T), count(lum.T[::-1])
    return img[top:h - bottom, left:w - right]


def snap_aspect(img: np.ndarray, aspect: float = 1.5) -> np.ndarray:
    """Riporta al formato nominale un fotogramma che ne differisce di poco (prospettiva residua)."""
    h, w = img.shape[:2]
    long_, short = max(h, w), min(h, w)
    if abs((long_ / short) / aspect - 1) > ASPECT_SNAP:
        return img
    new_short = int(round(long_ / aspect))
    size = (long_, new_short) if w >= h else (new_short, long_)
    return cv2.resize(img, size, interpolation=cv2.INTER_AREA)
