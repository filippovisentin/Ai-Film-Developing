import imageio.v3 as iio
import numpy as np
import pytest

from filmengine.imageio_ import load_image, save_outputs


def test_srgb_8bit_is_linearized(tmp_path):
    f = tmp_path / "grigio.png"
    iio.imwrite(f, np.full((20, 30, 3), 128, np.uint8))
    img = load_image(f)
    assert img.rgb.dtype == np.float32 and img.rgb.shape == (20, 30, 3)
    assert abs(float(img.rgb.mean()) - 0.2158) < 0.01
    assert img.is_raw is False
    assert any("non RAW" in w for w in img.warnings)


def test_jpeg_is_accepted(tmp_path):
    f = tmp_path / "foto.jpg"
    iio.imwrite(f, np.full((16, 16, 3), 200, np.uint8))
    assert load_image(f).rgb.shape == (16, 16, 3)


def test_unsupported_format_raises(tmp_path):
    f = tmp_path / "foto.heic"
    f.write_bytes(b"\x00" * 10)
    with pytest.raises(ValueError, match="Formato non supportato") as e:
        load_image(f)
    for ext in (".dng", ".jpg", ".png", ".tif"):
        assert ext in str(e.value)


def test_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_image(tmp_path / "manca.jpg")


def test_grayscale_and_alpha_become_rgb(tmp_path):
    g = tmp_path / "g.png"
    iio.imwrite(g, np.full((8, 8), 100, np.uint8))
    a = tmp_path / "a.png"
    iio.imwrite(a, np.full((8, 8, 4), 100, np.uint8))
    assert load_image(g).rgb.shape == (8, 8, 3)
    assert load_image(a).rgb.shape == (8, 8, 3)


def test_save_outputs_roundtrip(tmp_path):
    grad = np.linspace(0, 1, 64 * 48 * 3, dtype=np.float32).reshape(48, 64, 3)
    tif, jpg = save_outputs(grad, tmp_path / "out")
    assert tif.suffix == ".tif" and jpg.suffix == ".jpg"
    raw = iio.imread(tif)
    assert raw.dtype == np.uint16 and raw.shape == (48, 64, 3)
    back = load_image(tif).rgb
    assert np.max(np.abs(back - grad)) < 1e-3


def test_16bit_tiff_input_keeps_precision(tmp_path):
    vals = np.linspace(0.2, 0.2005, 100, dtype=np.float32)
    img = np.repeat(vals[None, :, None], 3, axis=2).repeat(4, axis=0)
    tif, _ = save_outputs(img, tmp_path / "fine")
    back = load_image(tif).rgb
    assert len(np.unique(back[0, :, 0])) > 20  # ~39 livelli a 16 bit; 8 bit ne darebbe 1-2
