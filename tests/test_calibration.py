import numpy as np

from filmengine.calibration import correct_light, estimate_base_from_border, measure_base
from tests.synthetic import make_light, make_negative, make_scene

MASK = (0.8, 0.5, 0.32)
GAMMA = (0.6, 0.55, 0.5)


def test_correct_light_removes_vignette():
    neg = make_negative(make_scene(), MASK, GAMMA, border_px=20, vignette=0.3)
    light = make_light(*neg.shape[:2], vignette=0.3)
    out = correct_light(neg, light)
    border = np.concatenate([out[:15].reshape(-1, 3), out[-15:].reshape(-1, 3)])
    rel_std = border.std(axis=0) / border.mean(axis=0)
    assert np.all(rel_std < 0.01)


def test_correct_light_none_is_identity():
    img = np.random.default_rng(1).random((10, 10, 3)).astype(np.float32)
    assert np.array_equal(correct_light(img, None), img)


def test_correct_light_dark_light_gives_no_nan():
    img = np.full((40, 40, 3), 0.5, np.float32)
    light = np.zeros_like(img)
    light[10:30, 10:30] = 1.0
    out = correct_light(img, light)
    assert np.all(np.isfinite(out))


def test_measure_base_uses_median_of_center():
    patch = np.empty((100, 100, 3), np.float32)
    patch[:] = (0.8, 0.5, 0.3)
    rng = np.random.default_rng(2)
    dust = rng.random((100, 100)) < 0.05
    patch[dust] = 0.0
    base = measure_base(patch)
    assert base.shape == (3,)
    assert np.allclose(base, (0.8, 0.5, 0.3), atol=0.01)


def test_base_never_zero():
    assert np.all(measure_base(np.zeros((20, 20, 3), np.float32)) >= 1e-4)


def test_estimate_base_from_border():
    neg = make_negative(make_scene(), MASK, GAMMA, border_px=20)
    est = estimate_base_from_border(neg)
    assert np.allclose(est, MASK, rtol=0.03)


def test_estimate_base_ignores_bare_light_around_film():
    neg = make_negative(make_scene(), MASK, GAMMA, border_px=20)
    framed = np.ones((neg.shape[0] + 20, neg.shape[1] + 20, 3), np.float32)
    framed[10:-10, 10:-10] = neg  # anello di luce nuda (1.0) intorno alla pellicola
    est = estimate_base_from_border(framed)
    assert np.allclose(est, MASK, rtol=0.03)
