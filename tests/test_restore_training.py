import numpy as np
import pytest

from tools.restore_data import random_setup, synth_negative


def test_synthetic_negative_is_inverted_and_masked():
    scene = np.zeros((10, 20, 3), np.float32)
    scene[:, :10] = 0.05   # zona scura della scena
    scene[:, 10:] = 0.6    # zona chiara
    neg = synth_negative(scene, np.random.default_rng(0))
    assert (neg[:, :10] > neg[:, 10:]).all()          # scuro nella scena = chiaro sul negativo
    assert neg[..., 0].mean() > neg[..., 2].mean()    # maschera arancione: più rosso che blu


def test_mild_setup_is_nearly_perfect():
    s = random_setup(np.random.default_rng(1), mild=True)
    assert s.noise <= 0.003 and s.blur <= 0.4 and s.jpeg_quality >= 92
    assert s.tilt_deg == 0 and s.vignette == 0


def test_validation_rolls_never_in_training():
    torch = pytest.importorskip("torch")  # noqa: F841
    from tools.train_restore import split
    names = [f"{r}-{i:02d}-x.preview.png" for r in ("19880215B", "19921210", "19941220D", "19960101",
                                                     "19960809B", "199910", "19990806", "19941228F")
             for i in range(3)]
    tr, va, rolls = split(names)
    assert va and tr
    assert not {names[i].split("-")[0] for i in tr} & {names[i].split("-")[0] for i in va}


def test_restore_net_keeps_image_size():
    torch = pytest.importorskip("torch")
    from tools.train_restore import RestoreNet
    out = RestoreNet()(torch.rand(1, 3, 50, 70))
    assert out.shape == (1, 3, 50, 70) and float(out.min()) >= 0 and float(out.max()) <= 1
