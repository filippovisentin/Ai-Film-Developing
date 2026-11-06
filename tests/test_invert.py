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


def test_black_point_is_neutral_per_channel():
    scene = make_scene()
    scene[150:190, 20:120] = scene.reshape(-1, 3).min(0)  # l'ombra più scura, con la dominante della scena
    p = dataclasses.replace(COLOR, paper_range=2.0)
    out = _develop(scene, p)
    darkest = out.reshape(-1, 3)[np.argsort(out.reshape(-1, 3).sum(1))[:200]].mean(0)
    assert darkest.max() - darkest.min() < 0.005


def test_paper_range_sets_print_black():
    p = dataclasses.replace(COLOR, paper_range=2.0)
    out = _develop(make_scene(), p)
    lo = np.percentile(out, 0.1)
    assert 0.007 < lo < 0.015 and out.max() > 0.97


def test_s_curve_keeps_endpoints_and_order():
    from filmengine.invert import tone_curve
    n = np.linspace(0, 1, 101, dtype=np.float32)
    for k in (0.0, 2.0, 6.0):
        g = tone_curve(n, k)
        assert abs(g[0]) < 1e-6 and abs(g[-1] - 1) < 1e-6 and np.all(np.diff(g) > 0)
    assert np.allclose(tone_curve(n, 0.0), n)
    assert tone_curve(n, 6.0)[25] < 0.25 < 0.75 < tone_curve(n, 6.0)[75]  # S: più contrasto al centro


def test_profile_defaults_keep_scene_linear_output():
    assert COLOR.paper_range is None and COLOR.s_curve == 0.0


def test_dust_does_not_shift_highlights():
    base = np.array(MASK, np.float32)
    neg = make_negative(make_scene(seed=5), MASK, GAMMA, border_px=0)
    dusty = neg.copy()
    rng = np.random.default_rng(1)
    specks = rng.random(neg.shape[:2]) < 0.004  # 0,4% di pixel opachi (polvere)
    dusty[specks] = 1e-4
    dc, dd = to_density(neg, base), to_density(dusty, base)
    clean = render_positive(dc, COLOR, compute_roll_levels([dc], COLOR))
    dirty = render_positive(dd, COLOR, compute_roll_levels([dd], COLOR))
    assert float(np.abs(clean - dirty)[~specks].mean()) < 0.01


def _cast_roll():
    base = np.array(MASK, np.float32)
    frames = [to_density(make_negative(make_scene(seed=s), MASK, GAMMA, border_px=0), base)
              for s in range(3)]
    cast = frames[0] + np.array([0.0, 0.08, 0.2], np.float32)  # luce diversa su un fotogramma
    return frames, cast


def test_frame_balance_absorbs_single_frame_cast():
    frames, cast = _cast_roll()
    p = dataclasses.replace(COLOR, frame_balance=1.0)
    lv = compute_roll_levels(frames[1:] + [cast], p)
    lv_ref = compute_roll_levels(frames, p)
    a = render_positive(cast, p, lv)
    b = render_positive(frames[0], p, lv_ref)
    assert float(np.abs(a - b).mean()) < 0.01


def test_without_frame_balance_cast_remains():
    frames, cast = _cast_roll()
    lv = compute_roll_levels(frames[1:] + [cast], COLOR)
    a = render_positive(cast, COLOR, lv)
    b = render_positive(frames[0], COLOR, compute_roll_levels(frames, COLOR))
    assert float(np.abs(a - b).mean()) > 0.03


def test_thin_edge_line_does_not_change_levels():
    # riga sottile al bordo, densissima solo nel blu (transizione dello scanner): non deve decidere il bianco
    base = np.array(MASK, np.float32)
    neg = make_negative(make_scene(seed=4), MASK, GAMMA, border_px=0)
    lined = neg.copy()
    lined[:3, :, 2] = 1e-4
    lined[-3:, :, 2] = 1e-4
    dc, dl = to_density(neg, base), to_density(lined, base)
    p = dataclasses.replace(COLOR, frame_balance=0.75)
    a = render_positive(dc, p, compute_roll_levels([dc], p))
    b = render_positive(dl, p, compute_roll_levels([dl], p))
    assert float(np.abs(a - b)[10:-10].mean()) < 0.005
