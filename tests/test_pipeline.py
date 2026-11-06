import numpy as np
import pytest

from filmengine.__main__ import main
from filmengine.imageio_ import load_image, save_outputs
from filmengine.pipeline import Calibration, develop_roll
from filmengine.profile import load_profile
from tests.synthetic import make_light, make_negative, make_scene

MASK = (0.8, 0.5, 0.32)
GAMMA = (0.6, 0.6, 0.6)  # come il profilo generic_color


def _roll(tmp_path, names=("frame_b", "frame_a", "frame_c"), vignette=0.2):
    paths = []
    for i, n in enumerate(names):
        neg = make_negative(make_scene(seed=i), MASK, GAMMA, border_px=30, vignette=vignette)
        tif, _ = save_outputs(neg, tmp_path / "in" / n)
        paths.append(tif)
    light = make_light(*neg.shape[:2], vignette=vignette)
    lt, _ = save_outputs(light, tmp_path / "in" / "luce")
    return paths, lt


def test_develop_roll_end_to_end(tmp_path):
    frames, light_path = _roll(tmp_path)
    calib = Calibration(base_rgb=np.array(MASK, np.float32), light=load_image(light_path).rgb)
    res = develop_roll(frames, load_profile("generic_color"), calib, tmp_path / "out")
    assert len(res) == 3
    for r in res:
        assert all(p.exists() for p in r.outputs)
    first = load_image(res[0].outputs[0]).rgb
    assert abs(first.shape[1] / first.shape[0] - 1.5) < 0.02
    g = first[28:42, 28:52].mean(axis=(0, 1))
    assert g.max() - g.min() < 0.02


def test_frame_not_found_falls_back_with_warning(tmp_path):
    f, _ = save_outputs(np.full((60, 90, 3), 0.3, np.float32), tmp_path / "piatto")
    res = develop_roll([f], load_profile("generic_color"),
                       Calibration(base_rgb=np.array(MASK, np.float32)), tmp_path / "out")
    assert res[0].outputs[0].exists()
    assert any("fotogramma non trovato" in w for w in res[0].warnings)


def test_no_base_uses_border_estimate_with_warning(tmp_path):
    frames, _ = _roll(tmp_path, names=("a",), vignette=0.0)
    res = develop_roll(frames, load_profile("generic_color"), Calibration(), tmp_path / "out")
    assert any("base stimata" in w for w in res[0].warnings)


def test_frames_processed_in_sorted_order(tmp_path):
    frames, _ = _roll(tmp_path, vignette=0.0)
    res = develop_roll(frames, load_profile("generic_color"), Calibration(), tmp_path / "out")
    assert [r.source.name for r in res] == sorted(p.name for p in frames)


def test_cli_profiles_lists_builtin(capsys):
    assert main(["profiles"]) == 0
    out = capsys.readouterr().out
    assert "portra_400" in out and "hp5_400" in out


def test_cli_develop(tmp_path):
    frames, light = _roll(tmp_path, names=("x",))
    base_patch, _ = save_outputs(np.ones((40, 40, 3), np.float32) * np.array(MASK, np.float32),
                                 tmp_path / "in" / "base")
    rc = main(["develop", str(frames[0]), "--profile", "generic_color", "--base", str(base_patch),
               "--out", str(tmp_path / "out")])
    assert rc == 0
    assert (tmp_path / "out" / "x_originale.tif").exists()


def test_cli_unknown_profile_returns_error(tmp_path, capsys):
    frames, _ = _roll(tmp_path, names=("x",))
    assert main(["develop", str(frames[0]), "--profile", "nope", "--out", str(tmp_path)]) == 2
    assert "Profilo sconosciuto" in capsys.readouterr().err


def test_frames_brighter_than_base_photo_keep_shadows(tmp_path):
    # la foto della base è stata esposta meno dei fotogrammi (esposizione automatica del telefono)
    scene = make_scene(seed=4)
    scene[150:190, 20:280] = np.linspace(0.01, 0.04, 260, dtype=np.float32)[None, :, None]
    neg = make_negative(scene, MASK, GAMMA, border_px=30) * 1.5
    f, _ = save_outputs(np.clip(neg, 0, 1), tmp_path / "in" / "f")
    res = develop_roll([f], load_profile("generic_color"),
                       Calibration(base_rgb=np.array(MASK, np.float32)), tmp_path / "out")
    out = load_image(res[0].outputs[0]).rgb
    ramp = out[160:180, 30:270, 1].mean(axis=0)
    assert len(np.unique(np.round(ramp, 4))) > 100  # la rampa delle ombre non è appiattita
    assert any("più chiar" in w for w in res[0].warnings)


def test_black_holder_does_not_blank_the_frame(tmp_path):
    neg = make_negative(make_scene(), MASK, GAMMA, border_px=30)
    framed = np.full((neg.shape[0] + 80, neg.shape[1] + 80, 3), 0.005, np.float32)
    framed[40:-40, 40:-40] = neg
    f, _ = save_outputs(framed, tmp_path / "in" / "holder")
    res = develop_roll([f], load_profile("generic_color"), Calibration(), tmp_path / "out")
    out = load_image(res[0].outputs[0]).rgb
    assert out.std() > 0.1  # non un'immagine uniforme
    assert abs(out.shape[1] / out.shape[0] - 1.5) < 0.02  # ritagliato sul fotogramma
