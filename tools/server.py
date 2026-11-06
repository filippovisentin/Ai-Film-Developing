"""Server locale per la pagina strumento (web/strumento.html).

Uso: python -m tools.server [porta]   →  http://127.0.0.1:8765/strumento.html
Ascolta solo su 127.0.0.1: le foto non lasciano il computer.
API:
  GET  /api/profili   → [{"id", "nome", "tipo"}]
  POST /api/sviluppa  → JSON {negativo, luce?, base?, profilo, migliora?, super_ris?: 0|2|4}
                        (immagini come data URL) ⇒ {immagini: {originale, migliorata?, ai?}, avvisi}
"""
from __future__ import annotations

import base64
import binascii
import contextlib
import io
import json
import sys
import tempfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from filmengine.calibration import correct_light, light_is_clipped, measure_base
from filmengine.imageio_ import linear_to_srgb, load_image
from filmengine.pipeline import Calibration, develop_roll
from filmengine.profile import list_profiles, load_profile

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_BODY = 80 * 1024 * 1024


def _decode_image(url: str, dest: Path) -> Path:
    """Data URL → file su disco; il formato viene dai byte, non da quello che dichiara il client."""
    if not isinstance(url, str) or not url.startswith("data:") or ";base64," not in url:
        raise ValueError("immagine non valida: serve una foto JPEG, PNG, TIFF o DNG")
    head, b64 = url.split(",", 1)
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("immagine non valida: dati corrotti") from None
    if data.startswith(b"\x89PNG"):
        ext = ".png"
    elif data.startswith(b"\xff\xd8"):
        ext = ".jpg"
    elif data[:4] in (b"II*\x00", b"MM\x00*"):
        ext = ".dng" if "dng" in head.lower() or "octet" in head.lower() else ".tif"
    else:
        raise ValueError("immagine non valida: serve una foto JPEG, PNG, TIFF o DNG")
    path = dest.with_suffix(ext)
    path.write_bytes(data)
    return path


def _to_jpeg_url(path: Path) -> str:
    from PIL import Image

    enc = linear_to_srgb(load_image(path).rgb)
    buf = io.BytesIO()
    Image.fromarray((enc * 255).round().astype(np.uint8)).save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def profiles() -> list[dict]:
    out = []
    for pid in list_profiles():
        p = load_profile(pid)
        out.append({"id": pid, "nome": p.name, "tipo": p.type})
    return out


def process(payload: dict) -> dict:
    pid = payload.get("profilo")
    if pid not in list_profiles():  # solo id noti: mai percorsi scelti dal client
        raise ValueError("profilo pellicola sconosciuto")
    sr = payload.get("super_ris") or 0
    if sr not in (0, 2, 4):
        raise ValueError("super-risoluzione ammessa: 0, 2 o 4")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        neg = _decode_image(payload.get("negativo"), tmp / "negativo")
        light = load_image(_decode_image(payload["luce"], tmp / "luce")).rgb if payload.get("luce") else None
        base = None
        if payload.get("base"):
            usable = None if light is None or light_is_clipped(light) else light
            base = measure_base(correct_light(load_image(_decode_image(payload["base"], tmp / "base")).rgb, usable))
        with contextlib.redirect_stderr(io.StringIO()):
            r = develop_roll([neg], load_profile(pid), Calibration(base, light), tmp / "out",
                             enhance=bool(payload.get("migliora")), super_res=sr)[0]
        images = {"originale": _to_jpeg_url(r.outputs[0])}
        if r.enhanced:
            images["migliorata"] = _to_jpeg_url(r.enhanced[0])
        if r.ai:
            images["ai"] = _to_jpeg_url(r.ai[0])
        avvisi = [w for w in r.warnings if "non RAW" not in w]
        return {"immagini": images, "avvisi": avvisi}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):  # meno rumore in console
        pass

    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/profili":
            return self._json(200, profiles())
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/sviluppa":
            return self._json(404, {"errore": "indirizzo sconosciuto"})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            return self._json(413, {"errore": "foto troppo grande (massimo 80 MB in tutto)"})
        try:
            payload = json.loads(self.rfile.read(n))
            if not isinstance(payload, dict):
                raise ValueError("richiesta non valida")
            return self._json(200, process(payload))
        except (ValueError, json.JSONDecodeError) as e:
            return self._json(400, {"errore": str(e)})
        except FileNotFoundError as e:
            return self._json(400, {"errore": str(e)})
        except Exception as e:  # noqa: BLE001 — l'utente vede un messaggio, non la traccia
            print("errore interno:", repr(e), file=sys.stderr)
            return self._json(500, {"errore": "elaborazione non riuscita: prova con un'altra foto"})


def make_server(port: int = 8765, web_dir: Path = WEB_DIR) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(web_dir)))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv else 8765
    httpd = make_server(port)
    print(f"Strumento pronto: http://127.0.0.1:{port}/strumento.html  (Ctrl+C per uscire)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
