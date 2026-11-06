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


def test_jpeg_exif_orientation_is_applied(tmp_path):
    from PIL import Image
    f = tmp_path / "verticale.jpg"
    im = Image.fromarray(np.full((20, 40, 3), 120, np.uint8))
    exif = im.getexif()
    exif[0x0112] = 6  # ruota di 90°
    im.save(f, exif=exif)
    assert load_image(f).rgb.shape == (40, 20, 3)


def test_corrupt_dng_raises_clear_error(tmp_path):
    f = tmp_path / "rotto.dng"
    f.write_bytes(b"non un dng" * 100)
    with pytest.raises(ValueError, match="DNG non leggibile"):
        load_image(f)


def test_dng_uses_camera_white_balance(tmp_path, monkeypatch):
    import sys
    import types
    seen = {}

    class FakeRaw:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def postprocess(self, **kw):
            seen.update(kw)
            return np.zeros((4, 4, 3), np.uint16)

    fake = types.SimpleNamespace(imread=lambda p: FakeRaw(),
                                 ColorSpace=types.SimpleNamespace(sRGB="srgb", raw="raw"),
                                 LibRawError=Exception)
    monkeypatch.setitem(sys.modules, "rawpy", fake)
    f = tmp_path / "x.dng"
    f.write_bytes(b"x")
    load_image(f)
    # bilanciamento della camera prima della matrice: senza, il blu sotto la maschera viene tagliato a 0
    assert seen["use_camera_wb"] is True and seen.get("user_wb") is None


def test_outputs_embed_srgb_profile(tmp_path):
    import tifffile
    from PIL import Image, ImageCms
    grad = np.linspace(0, 1, 32 * 32 * 3, dtype=np.float32).reshape(32, 32, 3)
    tif, jpg = save_outputs(grad, tmp_path / "out")
    with tifffile.TiffFile(tif) as t:
        icc = t.pages[0].tags.get(34675)
        assert icc is not None and len(icc.value) > 100
    with Image.open(jpg) as im:
        prof = ImageCms.ImageCmsProfile(__import__("io").BytesIO(im.info["icc_profile"]))
        assert "srgb" in ImageCms.getProfileDescription(prof).lower()
    assert np.max(np.abs(load_image(tif).rgb - grad)) < 1e-3   # i valori non cambiano


def _photo_like(h=96, w=128):
    rng = np.random.default_rng(0)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.stack([x / w, y / h, 0.5 + 0.5 * np.sin(x / 7)], -1) * 0.8
    return np.clip(img + rng.normal(0, 0.01, img.shape), 0, 1).astype(np.float32)


def test_jpeg_keeps_full_colour_resolution_and_names_the_software(tmp_path):
    from PIL import Image, JpegImagePlugin
    _, jpg = save_outputs(_photo_like(), tmp_path / "out")
    with Image.open(jpg) as im:
        assert JpegImagePlugin.get_sampling(im) == 0      # 4:4:4, niente colore dimezzato
        assert "Ai-Film-Developing" in str(im.getexif().get(0x0131, ""))  # tag Software


def test_tiff_is_losslessly_compressed(tmp_path):
    import tifffile
    img = _photo_like(256, 384)
    tif, _ = save_outputs(img, tmp_path / "out")
    with tifffile.TiffFile(tif) as t:
        assert t.pages[0].compression != 1  # 1 = nessuna compressione
        assert t.pages[0].dtype == np.uint16
    assert np.max(np.abs(load_image(tif).rgb - img)) < 1e-3
