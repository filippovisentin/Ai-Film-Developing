import cv2
import numpy as np
import pytest

from filmengine import enhance


def _scene(h=240, w=320):
    """Scena lineare con bordi netti e sfumature, valori realistici (0.02-0.8)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.empty((h, w, 3), np.float32)
    img[...] = 0.05 + 0.25 * (x / w)[..., None]
    img[60:180, 100:220] = [0.6, 0.4, 0.2]
    img[20:50, 20:300] = [0.1, 0.3, 0.7]
    return img


def _noisy(img, sigma=0.03, seed=0):
    rng = np.random.default_rng(seed)
    lum_noise = rng.normal(0, sigma, img.shape[:2])[..., None]
    chroma_noise = rng.normal(0, sigma, img.shape)
    return np.clip(img + 0.5 * lum_noise + chroma_noise, 0, 1).astype(np.float32)


def _edge_strength(img):
    lum = img.mean(-1)
    return float(np.abs(np.diff(lum[100:140, 90:110], axis=1)).max())


def test_estimate_noise_tracks_true_sigma():
    clean = _scene()
    lo = enhance.estimate_noise(_noisy(clean, 0.01))
    hi = enhance.estimate_noise(_noisy(clean, 0.04))
    assert hi > 2.5 * lo
    assert enhance.estimate_noise(clean) < lo


def test_denoise_reduces_noise_and_keeps_edges():
    clean = _scene()
    noisy = _noisy(clean)
    out = enhance.denoise(noisy)
    inner = (slice(10, -10), slice(10, -10))
    assert np.abs(out - clean)[inner].mean() < 0.6 * np.abs(noisy - clean)[inner].mean()
    assert _edge_strength(out) > 0.8 * _edge_strength(clean)


def test_denoise_leaves_clean_image_almost_untouched():
    clean = _scene()
    assert np.abs(enhance.denoise(clean) - clean).mean() < 0.004


def test_remove_dust_erases_small_bright_specks_only():
    img = _scene()
    dirty = img.copy()
    specks = [(30, 70), (200, 40), (120, 280), (215, 250)]
    for yy, xx in specks:
        cv2.circle(dirty, (xx, yy), 2, (1.0, 1.0, 1.0), -1)
    dirty[100:150, 110:200] = 0.95  # area chiara grande: soggetto, non polvere
    out, n = enhance.remove_dust(dirty, return_count=True)
    assert n == len(specks)
    for yy, xx in specks:
        assert np.abs(out[yy, xx] - img[yy, xx]).max() < 0.08
    assert np.allclose(out[110:140, 120:190], 0.95)


def test_sharpen_increases_acutance_without_shifting_flat_areas():
    img = cv2.GaussianBlur(_scene(), (0, 0), 1.5)
    out = enhance.sharpen(img)
    assert _edge_strength(out) > 1.15 * _edge_strength(img)
    assert abs(out[90:150, 130:190].mean() - img[90:150, 130:190].mean()) < 0.003


def test_sharpen_does_not_amplify_fine_noise():
    flat = np.full((100, 100, 3), 0.3, np.float32)
    noisy = _noisy(flat, 0.004)
    assert enhance.sharpen(noisy).std() < 1.3 * noisy.std()


def test_enhance_returns_valid_image_same_shape():
    out = enhance.enhance(_noisy(_scene()))
    assert out.shape == (240, 320, 3) and out.dtype == np.float32
    assert out.min() >= 0 and out.max() <= 1


def test_super_resolve_missing_model_explains_how_to_get_it(tmp_path):
    with pytest.raises(FileNotFoundError, match="get_model"):
        enhance.super_resolve(_scene(), model_path=tmp_path / "nessuno.onnx")


_has_model = enhance.DEFAULT_MODEL.exists()
needs_model = pytest.mark.skipif(not _has_model, reason="modello AI non scaricato")


@needs_model
def test_super_resolve_quadruples_size_and_keeps_colours():
    pytest.importorskip("onnxruntime")
    img = _scene(150, 210)
    out = enhance.super_resolve(img)
    assert out.shape == (600, 840, 3) and out.dtype == np.float32
    small = cv2.resize(out, (210, 150), interpolation=cv2.INTER_AREA)
    assert np.abs(small - img)[10:-10, 10:-10].mean() < 0.02


@needs_model
def test_super_resolve_has_no_tile_seams():
    pytest.importorskip("onnxruntime")
    img = np.full((300, 300, 3), [0.3, 0.2, 0.1], np.float32)
    out = enhance.super_resolve(img)
    assert out[20:-20, 20:-20].std(axis=(0, 1)).max() < 0.004


@needs_model
def test_super_resolve_scale_two():
    pytest.importorskip("onnxruntime")
    assert enhance.super_resolve(_scene(100, 140), scale=2).shape == (200, 280, 3)


def test_remove_dust_keeps_small_lights_in_dark_sky():
    sky = np.full((120, 160, 3), 0.01, np.float32)
    for yy, xx in [(30, 40), (60, 100), (90, 130)]:
        cv2.circle(sky, (xx, yy), 1, (0.9, 0.9, 0.85), -1)
    out, n = enhance.remove_dust(sky, return_count=True)
    assert n == 0 and np.array_equal(out, sky)


def test_restore_missing_model_explains_how_to_get_it(tmp_path):
    with pytest.raises(FileNotFoundError, match="train_restore"):
        enhance.restore(_scene(), model_path=tmp_path / "nessuno.onnx")


needs_restore = pytest.mark.skipif(not enhance.RESTORE_MODEL.exists(), reason="rete di restauro non addestrata")


@needs_restore
def test_restore_keeps_size_and_leaves_clean_image_nearly_untouched():
    pytest.importorskip("onnxruntime")
    clean = _scene(300, 420)
    out = enhance.restore(clean)
    assert out.shape == clean.shape and out.dtype == np.float32
    # misurato 0.014 con restore_v1: lieve ritocco di tono, coerente con ΔE 3.25 -> 3.43 sui negativi veri
    assert np.abs(out - clean)[10:-10, 10:-10].mean() < 0.02


@needs_restore
def test_restore_tiles_have_no_seams():
    pytest.importorskip("onnxruntime")
    flat = np.full((700, 900, 3), [0.3, 0.2, 0.1], np.float32)
    out = enhance.restore(flat)
    assert out[20:-20, 20:-20].std(axis=(0, 1)).max() < 0.003
