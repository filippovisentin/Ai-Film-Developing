import base64
import io
import json
import threading
import urllib.error
import urllib.request

import numpy as np
import pytest
from PIL import Image

from filmengine.imageio_ import linear_to_srgb
from tests.synthetic import make_light, make_negative, make_scene
from tools import server

MASK = (0.8, 0.5, 0.32)


def _data_url(rgb_linear, fmt="PNG"):
    buf = io.BytesIO()
    Image.fromarray((linear_to_srgb(rgb_linear) * 255).round().astype(np.uint8)).save(buf, fmt)
    mime = "image/png" if fmt == "PNG" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def _payload(**kw):
    neg = make_negative(make_scene(seed=1), MASK, (0.6, 0.6, 0.6), border_px=30, vignette=0.2)
    p = {"negativo": _data_url(neg), "luce": _data_url(make_light(*neg.shape[:2], vignette=0.2)),
         "base": _data_url(np.ones((40, 40, 3), np.float32) * np.array(MASK, np.float32)),
         "profilo": "generic_color"}
    p.update(kw)
    return p


def _decode(url):
    assert url.startswith("data:image/jpeg;base64,")
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))))


def test_process_returns_original_only_by_default():
    out = server.process(_payload())
    assert set(out["immagini"]) == {"originale"}
    assert _decode(out["immagini"]["originale"]).ndim == 3


def test_process_with_enhance_returns_both_versions():
    out = server.process(_payload(migliora=True))
    assert set(out["immagini"]) == {"originale", "migliorata"}


def test_process_rejects_profile_paths():
    with pytest.raises(ValueError, match="profilo"):
        server.process(_payload(profilo="../../etc/passwd"))


def test_process_rejects_non_image_data():
    with pytest.raises(ValueError, match="immagine"):
        server.process(_payload(negativo="data:text/html;base64,PGgxPg=="))


def test_process_rejects_bad_super_resolution_factor():
    with pytest.raises(ValueError, match="super"):
        server.process(_payload(super_ris=8))


def test_process_without_light_and_base_still_develops_with_warning():
    out = server.process(_payload(luce=None, base=None))
    assert "originale" in out["immagini"]
    assert any("base stimata" in a for a in out["avvisi"])


def test_http_server_end_to_end_on_localhost(tmp_path):
    (tmp_path / "strumento.html").write_text("<h1>ok</h1>", encoding="utf-8")
    httpd = server.make_server(0, tmp_path)
    assert httpd.server_address[0] == "127.0.0.1"
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{port}"
        assert b"ok" in urllib.request.urlopen(base + "/strumento.html").read()
        profili = json.loads(urllib.request.urlopen(base + "/api/profili").read())
        assert any(p["id"] == "portra_400" for p in profili)
        req = urllib.request.Request(base + "/api/sviluppa", data=json.dumps(_payload()).encode(),
                                     headers={"Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(req).read())
        assert "originale" in res["immagini"]
        bad = urllib.request.Request(base + "/api/sviluppa", data=b"{non json",
                                     headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(bad)
        assert e.value.code == 400
    finally:
        httpd.shutdown()
        httpd.server_close()
