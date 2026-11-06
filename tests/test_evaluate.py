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


def _fake_roll(root, name, seeds):
    from filmengine.imageio_ import save_outputs
    from tests.synthetic import make_negative
    for s in seeds:
        scene = _textured(s)
        save_outputs(make_negative(scene, (0.8, 0.5, 0.32), (0.6, 0.6, 0.6), border_px=0),
                     root / name / "negativi" / f"f{s}")
        save_outputs(scene, root / name / "stampe" / f"f{s}")


def test_run_all_reports_each_roll_and_overall(tmp_path):
    from tools.evaluate import run_all
    _fake_roll(tmp_path, "rollA", (0, 1))
    _fake_roll(tmp_path, "rollB", (2, 3))
    rep = run_all(tmp_path, "generic_color", tmp_path / "out")
    assert set(rep) == {"rollA", "rollB", "MEDIA"}
    assert all(set(rep[r]) >= {"dE_medio", "dE_dopo_dominante", "fotogrammi"} for r in ("rollA", "rollB"))
    assert rep["rollA"]["fotogrammi"] == 2
    assert abs(rep["MEDIA"]["dE_medio"] - (rep["rollA"]["dE_medio"] + rep["rollB"]["dE_medio"]) / 2) < 0.01
