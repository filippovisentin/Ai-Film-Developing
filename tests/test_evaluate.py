import cv2
import numpy as np

from tests.synthetic import make_scene
from tools.evaluate import compare


def _textured(seed=0):
    rng = np.random.default_rng(seed)
    noise = cv2.GaussianBlur(rng.random((400, 600)).astype(np.float32), (0, 0), 2)
    img = make_scene(400, 600, seed=seed) * (0.6 + 0.8 * noise[..., None])
    return np.clip(img, 0, 1).astype(np.float32)


def test_identical_images_have_zero_error():
    x = _textured()
    r = compare(x, x)
    assert r["dE_medio"] < 0.5 and r["correlazione_tono"] > 0.99


def test_shifted_image_is_aligned():
    x = _textured()
    m = np.float32([[1, 0, 12], [0, 1, -8]])
    shifted = cv2.warpAffine(x, m, (600, 400), borderMode=cv2.BORDER_REFLECT)
    assert compare(shifted, x)["dE_medio"] < 1.5


def test_color_cast_is_separated_from_tone():
    x = _textured()
    cast = np.clip(x * np.array([1.0, 0.8, 0.6], np.float32), 0, 1)
    r = compare(cast, x)
    assert r["dE_medio"] > 5 and r["dE_dopo_dominante"] < 1.5
