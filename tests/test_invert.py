import dataclasses

import numpy as np

from filmengine.invert import RollLevels, compute_roll_levels, render_positive, to_density
from filmengine.profile import FilmProfile
from tests.synthetic import GRAY, WHITE_VALUE, make_negative, make_scene

MASK = (0.8, 0.5, 0.32)
GAMMA = (0.6, 0.55, 0.5)
IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
COLOR = FilmProfile("t", "Test", "color_negative", MASK, GAMMA, 1.0, IDENTITY)
BW = dataclasses.replace(COLOR, type="bw_negative")
SLIDE = dataclasses.replace(COLOR, type="slide")


def _develop(scene, profile=COLOR, levels=None):
    d = to_density(make_negative(scene, MASK, GAMMA, border_px=0), np.array(MASK, np.float32))
    levels = levels or compute_roll_levels([d], profile)
    return render_positive(d, profile, levels)


def test_roundtrip_color_negative():
    scene = make_scene()
    out = _develop(scene)
    assert out.dtype == np.float32 and out.shape == scene.shape
    assert float(np.mean(np.abs(out - scene / WHITE_VALUE))) < 0.02
    g = out[GRAY].mean(axis=(0, 1))
    assert g.max() - g.min() < 0.01


def test_bw_output_is_neutral():
    out = _develop(make_scene(), BW)
    assert np.array_equal(out[..., 0], out[..., 1]) and np.array_equal(out[..., 1], out[..., 2])


def test_slide_skips_inversion():
    ramp = np.linspace(0.02, 0.9, 50, dtype=np.float32)
    img = np.repeat(np.repeat(ramp[None, :, None], 3, axis=2), 4, axis=0)
    out = render_positive(img, SLIDE, compute_roll_levels([img], SLIDE))
    assert np.all(np.diff(out[0, :, 1]) >= 0) and out[0, -1, 1] > out[0, 0, 1]


def test_no_nan_with_zero_pixels():
    img = np.zeros((30, 30, 3), np.float32)
    img[:10] = 2.0  # oltre la base
    img[10:20] = 0.3
    d = to_density(img, np.array(MASK, np.float32))
    out = render_positive(d, COLOR, compute_roll_levels([d], COLOR))
    assert np.all(np.isfinite(out)) and out.min() >= 0 and out.max() <= 1


def test_uniform_frame_gives_finite_output():
    d = np.full((10, 10, 3), 0.5, np.float32)
    out = render_positive(d, COLOR, compute_roll_levels([d], COLOR))
    assert np.all(np.isfinite(out))


def test_roll_levels_robust_to_outlier_frame():
    base = np.array(MASK, np.float32)
    scenes = [make_scene(seed=s) for s in range(5)]
    dens = [to_density(make_negative(s, MASK, GAMMA, border_px=0), base) for s in scenes]
    dark = np.clip(make_scene(seed=9) * 0.02, 0.01, 1.0)
    outlier = to_density(make_negative(dark, MASK, GAMMA, border_px=0), base)
    lv_a = compute_roll_levels(dens, COLOR)
    lv_b = compute_roll_levels(dens + [outlier], COLOR)
    assert isinstance(lv_a, RollLevels)
    for d in dens:
        diff = np.abs(render_positive(d, COLOR, lv_a) - render_positive(d, COLOR, lv_b))
        assert float(diff.mean()) < 0.03


def test_deterministic():
    scene = make_scene(seed=3)
    assert np.array_equal(_develop(scene), _develop(scene))


def test_print_contrast_and_matrix_are_applied():
    scene = make_scene()
    plain = _develop(scene)
    swap = ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    p = dataclasses.replace(COLOR, print_contrast=1.5, color_matrix=swap)
    out = _develop(scene, p)
    assert np.allclose(out[..., 0], np.clip(plain[..., 1] ** 1.5, 0, 1), atol=1e-4)
