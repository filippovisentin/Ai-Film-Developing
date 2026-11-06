import cv2
import numpy as np
import pytest

from filmengine.stack import stack_captures


def _scene(h=300, w=450, seed=0):
    rng = np.random.default_rng(seed)
    tex = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 3)
    img = np.stack([0.2 + 0.6 * tex, 0.15 + 0.5 * tex[::-1], 0.1 + 0.4 * tex[:, ::-1]], -1)
    return img.astype(np.float32)


def _noisy_shifted(img, dx, dy, seed, noise=0.03):
    m = np.float32([[1, 0, dx], [0, 1, dy]])
    moved = cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_REFLECT)
    rng = np.random.default_rng(seed)
    return np.clip(moved + rng.normal(0, noise, img.shape).astype(np.float32), 0, 1)


def test_stack_reduces_noise_after_alignment():
    clean = _scene()
    shots = [_noisy_shifted(clean, dx, dy, s) for s, (dx, dy) in
             enumerate([(0, 0), (2.5, -1.5), (-3, 2), (1, 3)])]
    c = (slice(20, -20), slice(20, -20))
    err_single = np.abs(shots[0] - clean)[c].mean()
    err_stack = np.abs(stack_captures(shots) - clean)[c].mean()
    assert err_stack < err_single / 1.7


def test_stack_of_one_is_identity():
    x = _scene()
    assert np.array_equal(stack_captures([x]), x)


def test_stack_rejects_different_sizes():
    with pytest.raises(ValueError, match="dimensioni"):
        stack_captures([_scene(), _scene(200, 300)])


def test_stack_rejects_empty():
    with pytest.raises(ValueError):
        stack_captures([])


def test_stack_drops_shot_that_cannot_be_aligned():
    clean = _scene()
    shots = [_noisy_shifted(clean, 0, 0, 1), _noisy_shifted(clean, 1, 1, 2),
             _scene(seed=9)]  # foto sbagliata: un'altra scena
    out, report = stack_captures(shots, return_report=True)
    assert report["usati"] == 2 and report["scartati"] == 1
    assert np.abs(out - clean)[20:-20, 20:-20].mean() < 0.03
