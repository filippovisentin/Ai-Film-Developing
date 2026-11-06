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
