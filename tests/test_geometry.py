import cv2
import numpy as np

from filmengine.geometry import find_frame_corners, warp_frame


def _canvas_with_frame(corners, h=600, w=800):
    img = np.full((h, w, 3), 0.8, np.float32)
    rng = np.random.default_rng(0)
    frame = np.zeros((h, w), np.uint8)
    cv2.fillPoly(frame, [np.round(corners).astype(np.int32)], 1)
    tex = 0.05 + 0.3 * rng.random((h, w)).astype(np.float32)
    tex = cv2.GaussianBlur(tex, (0, 0), 3)
    img[frame == 1] = tex[frame == 1, None]
    return img


def _rect(cx, cy, w, h, deg):
    pts = np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]], np.float32)
    a = np.deg2rad(deg)
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]], np.float32)
    return pts @ rot.T + (cx, cy)


def test_finds_rotated_frame():
    true = _rect(400, 300, 450, 300, 7)
    true[2] += (6, 4)  # leggera prospettiva
    found = find_frame_corners(_canvas_with_frame(true))
    assert found is not None and found.shape == (4, 2)
    assert np.max(np.linalg.norm(found - true, axis=1)) < 3.0


def test_returns_none_on_uniform_image():
    assert find_frame_corners(np.full((300, 400, 3), 0.5, np.float32)) is None


def test_returns_none_when_frame_too_small():
    assert find_frame_corners(_canvas_with_frame(_rect(400, 300, 120, 80, 0))) is None


def test_warp_output_aspect():
    true = _rect(400, 300, 450, 300, 7)
    img = _canvas_with_frame(true)
    out = warp_frame(img, find_frame_corners(img))
    h, w = out.shape[:2]
    assert abs(w / h - 1.5) < 0.015
    assert abs(w - 450) <= 3


def test_portrait_frame_keeps_orientation():
    true = _rect(400, 300, 260, 390, 3)
    img = _canvas_with_frame(true)
    out = warp_frame(img, find_frame_corners(img))
    h, w = out.shape[:2]
    assert h > w and abs(h / w - 1.5) < 0.015


def test_warp_has_no_overshoot_at_sharp_edges():
    img = np.full((400, 600, 3), 0.9, np.float32)
    img[:, 300:] = 0.5  # bordo netto tra due zone chiare
    img[0, 0] = 0.001   # un pixel scuro lontano: il minimo globale non deve mascherare il difetto
    out = warp_frame(img, _rect(300, 200, 450, 300, 5))
    assert out.min() >= 0.5 - 1e-6 and out.max() <= 0.9 + 1e-6


def _texture(h, w):
    rng = np.random.default_rng(0)
    tex = 0.05 + 0.3 * rng.random((h, w)).astype(np.float32)
    return cv2.GaussianBlur(tex, (0, 0), 3)


def test_frame_in_black_holder_is_found():
    h, w = 600, 800
    img = np.full((h, w, 3), 0.01, np.float32)        # porta-negativi nero
    img[100:500, 100:700] = 0.8                       # finestra: base della pellicola
    true = _rect(400, 300, 450, 300, 0)
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.round(true).astype(np.int32)], 1)
    tex = _texture(h, w)
    img[m == 1] = tex[m == 1, None]
    found = find_frame_corners(img)
    assert found is not None
    assert np.max(np.linalg.norm(found - true, axis=1)) < 3.0


def test_strip_with_bare_light_and_neighbours_is_found():
    h, w = 600, 800
    img = np.ones((h, w, 3), np.float32)              # luce nuda sopra e sotto
    img[120:480] = 0.8                                # striscia di pellicola
    tex = _texture(h, w)
    for c0, c1 in ((0, 150), (175, 625), (650, 800)):  # vicino, fotogramma, vicino
        img[150:450, c0:c1] = tex[150:450, c0:c1, None]
    true = np.array([[175, 150], [624, 150], [624, 449], [175, 449]], np.float32)
    found = find_frame_corners(img)
    assert found is not None
    assert np.max(np.linalg.norm(found - true, axis=1)) < 3.0


def test_quad_touching_image_border_is_rejected():
    img = np.full((300, 400, 3), 0.8, np.float32)
    img[:, :200] = 0.1  # zona scura che tocca il bordo: non è un fotogramma
    assert find_frame_corners(img) is None


def test_trim_dark_edges_removes_scanner_borders():
    from filmengine.geometry import trim_dark_edges
    img = _texture(300, 400)[..., None].repeat(3, 2) + 0.3
    img[:, :8] = 0.01       # striscia nera a sinistra
    img[-5:, :] = 0.02      # e in basso
    out = trim_dark_edges(img)
    assert out.shape == (295, 392, 3)
    assert np.allclose(out, img[:295, 8:])


def test_trim_dark_edges_leaves_clean_image_alone():
    from filmengine.geometry import trim_dark_edges
    img = _texture(200, 300)[..., None].repeat(3, 2) + 0.3
    assert trim_dark_edges(img).shape == img.shape


def test_trim_dark_edges_never_cuts_more_than_limit():
    from filmengine.geometry import trim_dark_edges
    img = np.full((200, 300, 3), 0.5, np.float32)
    img[:, :150] = 0.01  # metà immagine scura: è contenuto, non un bordo
    out = trim_dark_edges(img)
    assert out.shape[1] >= int(300 * 0.95)


def test_frame_inside_film_rebate_on_bare_light():
    h, w = 700, 900
    img = np.ones((h, w, 3), np.float32)                  # luce nuda
    img[90:610, 60:840] = (0.64, 0.4, 0.26)               # pellicola: bordo non esposto (base)
    tex = _texture(h, w)
    true = np.array([[150, 160], [749, 160], [749, 559], [150, 559]], np.float32)
    img[160:560, 150:750] = (tex[160:560, 150:750, None] * np.array([0.9, 0.6, 0.4], np.float32))
    found = find_frame_corners(img)
    assert found is not None
    assert np.max(np.linalg.norm(found - true, axis=1)) < 3.0


def _holder_strip(h=700, w=900):
    img = np.full((h, w, 3), 0.005, np.float32)          # porta-negativi nero
    img[90:610, 60:840] = (0.64, 0.4, 0.26)              # finestra: pellicola con bordo chiaro
    tex = _texture(h, w)
    fr = tex[160:560, 150:750, None] * np.array([0.9, 0.6, 0.4], np.float32)
    fr[:40, :200] = (0.64, 0.4, 0.26)                    # zona sottile che tocca il bordo del fotogramma
    img[160:560, 150:750] = fr
    return img


def test_holder_window_is_used_when_frame_outline_is_irregular():
    found = find_frame_corners(_holder_strip())
    assert found is not None
    area = cv2.contourArea(found.reshape(-1, 1, 2))
    assert 600 * 400 * 0.95 <= area <= 780 * 520 * 1.02


def test_trim_rebate_edges_removes_uniform_bright_bands():
    from filmengine.geometry import trim_rebate_edges
    img = _texture(300, 450)[..., None].repeat(3, 2) * np.array([0.9, 0.6, 0.4], np.float32)
    img[:20] = (0.64, 0.4, 0.26)
    img[:, -25:] = (0.64, 0.4, 0.26)
    out = trim_rebate_edges(img)
    assert 274 <= out.shape[0] <= 280 and 419 <= out.shape[1] <= 425   # bordo + margine


def test_trim_rebate_edges_keeps_bright_sky():
    from filmengine.geometry import trim_rebate_edges
    img = _texture(300, 450)[..., None].repeat(3, 2) * 0.5
    sky = 0.6 + 0.2 * _texture(300, 450)[:60, :, None]   # cielo chiaro ma non uniforme
    img[:60] = sky
    assert trim_rebate_edges(img).shape[0] >= 295


def test_trim_rebate_skips_mixed_outer_lines():
    from filmengine.geometry import trim_rebate_edges
    rng = np.random.default_rng(0)
    img = _texture(300, 450)[..., None].repeat(3, 2) * np.array([0.9, 0.6, 0.4], np.float32)
    img[:33] = (0.64, 0.4, 0.26)                                   # bordo della pellicola
    img[:3] = (0.64, 0.4, 0.26) + 0.3 * rng.random((3, 450, 1))   # righe esterne miste con la luce
    out = trim_rebate_edges(img)
    assert 300 - 33 - 6 <= out.shape[0] <= 300 - 33                # 33 righe + un piccolo margine


def test_warp_keeps_measured_aspect_when_not_a_frame():
    corners = np.float32([[100, 100], [620, 100], [620, 500], [100, 500]])  # 520x400 = 1,3
    out = warp_frame(np.zeros((600, 800, 3), np.float32), corners)
    assert abs(out.shape[1] / out.shape[0] - 1.3) < 0.02


def test_warp_snaps_near_3_2_to_3_2():
    corners = np.float32([[100, 100], [580, 100], [580, 427], [100, 427]])  # 480x327 = 1,468
    out = warp_frame(np.zeros((600, 800, 3), np.float32), corners)
    assert abs(out.shape[1] / out.shape[0] - 1.5) < 0.01


def test_snap_aspect_after_trim():
    from filmengine.geometry import snap_aspect
    assert snap_aspect(np.zeros((819, 1194, 3), np.float32)).shape[:2] == (796, 1194)
    assert snap_aspect(np.zeros((1194, 819, 3), np.float32)).shape[:2] == (1194, 796)
    assert snap_aspect(np.zeros((600, 780, 3), np.float32)).shape[:2] == (600, 780)  # 1,3: non è un 3:2


def test_film_strip_with_rebate_is_not_squeezed_to_3_2():
    corners = np.float32([[0, 0], [1680, 0], [1680, 1180], [0, 1180]])  # striscia 1,42: non è un 3:2
    out = warp_frame(np.zeros((1200, 1700, 3), np.float32), corners)
    assert abs(out.shape[1] / out.shape[0] - 1680 / 1180) < 0.01


def test_trim_rebate_stops_at_uniform_shadow_content():
    from filmengine.geometry import trim_rebate_edges
    img = _texture(300, 450)[..., None].repeat(3, 2) * np.array([0.9, 0.6, 0.4], np.float32)
    img[-40:] = (0.59, 0.37, 0.24)     # ombra profonda: uniforme, quasi chiara come la base
    img[-30:] = (0.64, 0.4, 0.26)      # bordo della pellicola
    out = trim_rebate_edges(img)
    assert out.shape[0] >= 300 - 30 - 6   # toglie il bordo, non l'ombra


def test_trim_dark_edges_skips_soft_transition_lines():
    # come nella scansione reale: 2 colonne esterne appena sopra la soglia di "scuro", poi il bordo nero
    from filmengine.geometry import trim_dark_edges
    img = _texture(300, 400)[..., None].repeat(3, 2) + 0.3
    img[:, -8:] = 0.03                      # bordo nero dello scanner
    img[:, -1] = 0.16                       # colonne esterne sfumate (luce che filtra)
    img[:, -2] = 0.14
    out = trim_dark_edges(img)
    assert out.shape[1] <= 400 - 8


def test_trim_dark_edges_soft_lines_alone_are_kept():
    from filmengine.geometry import trim_dark_edges
    img = _texture(300, 400)[..., None].repeat(3, 2) + 0.3
    img[:, -2:] = 0.16                      # solo colonne un po' scure, nessun bordo nero dopo
    assert trim_dark_edges(img).shape[1] == 400
