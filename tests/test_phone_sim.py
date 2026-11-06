import numpy as np

from tests.synthetic import make_negative, make_scene
from tools.phone_sim import PhoneSetup, simulate

MASK = (0.8, 0.5, 0.32)


def _neg():
    return make_negative(make_scene(seed=1), MASK, (0.6, 0.6, 0.6), border_px=0)


def test_ideal_setup_contains_frame_at_reported_corners():
    neg = _neg()
    cap = simulate(neg, PhoneSetup(), seed=0)
    assert cap.image.shape == cap.light.shape and cap.image.dtype == np.float32
    tl, tr, br, bl = cap.corners
    # al centro del fotogramma si ritrova il negativo (a meno della scala)
    c = cap.image[int((tl[1] + br[1]) / 2), int((tl[0] + br[0]) / 2)]
    assert np.all(c > 0) and np.all(c < 1)
    assert np.linalg.norm(tr - tl) > 0.5 * cap.image.shape[1]


def test_rebate_has_base_color():
    cap = simulate(_neg(), PhoneSetup(), seed=0)
    r = cap.base_patch.reshape(-1, 3).mean(0)
    assert np.allclose(r / r.max(), cap.true_base / cap.true_base.max(), atol=0.03)


def test_vignette_is_also_in_light_frame():
    cap = simulate(_neg(), PhoneSetup(vignette=0.4), seed=0)
    h, w = cap.light.shape[:2]
    assert cap.light[h // 2, w // 2].mean() > 1.3 * cap.light[5, 5].mean()


def test_same_seed_same_capture():
    a = simulate(_neg(), PhoneSetup(noise=0.01, jpeg_quality=80, tilt_deg=4), seed=3)
    b = simulate(_neg(), PhoneSetup(noise=0.01, jpeg_quality=80, tilt_deg=4), seed=3)
    assert np.array_equal(a.image, b.image)


def test_jpeg_quantizes_to_8bit_levels():
    cap = simulate(_neg(), PhoneSetup(jpeg_quality=85), seed=0)
    from filmengine.imageio_ import linear_to_srgb
    v = np.round(linear_to_srgb(cap.image) * 255)
    assert np.allclose(linear_to_srgb(cap.image) * 255, v, atol=0.05)


def test_reflection_veil_lifts_dense_areas():
    neg = _neg()
    a = simulate(neg, PhoneSetup(), seed=0)
    b = simulate(neg, PhoneSetup(veil=0.03), seed=0)
    assert b.image.min() > a.image.min() + 0.02


def test_light_photo_is_auto_exposed_unless_forced():
    a = simulate(_neg(), PhoneSetup(vignette=0.4, wb=(0.85, 1.0, 1.25)), seed=0)
    assert a.light.max() < 0.95  # come l'esposizione automatica del telefono
    b = simulate(_neg(), PhoneSetup(vignette=0.4, light_overexposed=True), seed=0)
    assert b.light.max() >= 0.99
