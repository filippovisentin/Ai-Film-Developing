"""Scarica il modello di super-risoluzione Real-ESRGAN General x4v3 (ONNX, ~5 MB).

Fonte: Qualcomm AI Hub (huggingface.co/qualcomm/Real-ESRGAN-General-x4v3), licenza BSD-3-Clause,
release v0.66.0. Il file viene accettato solo se l'impronta SHA-256 coincide con quella fissata qui.
Uso: python -m tools.get_model
"""
from __future__ import annotations

import hashlib
import io
import sys
import urllib.request
import zipfile

from filmengine.enhance import MODELS_DIR

URL = ("https://qaihub-public-assets.s3.us-west-2.amazonaws.com/qai-hub-models/models/"
       "real_esrgan_general_x4v3/releases/v0.66.0/real_esrgan_general_x4v3-onnx-float.zip")
SHA256 = "fc094329b24a00c936ebc1cc4c51bc59633e7dc36f4a553344342171cbd3c7cf"
WANTED = ("real_esrgan_general_x4v3.onnx", "real_esrgan_general_x4v3.data")


def main() -> int:
    print("Scarico", URL)
    with urllib.request.urlopen(URL, timeout=120) as r:
        data = r.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        print(f"Impronta errata ({digest}): file rifiutato.", file=sys.stderr)
        return 1
    MODELS_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            name = info.filename.rsplit("/", 1)[-1]
            if name in WANTED:
                (MODELS_DIR / name).write_bytes(z.read(info))
                print("ok", MODELS_DIR / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
