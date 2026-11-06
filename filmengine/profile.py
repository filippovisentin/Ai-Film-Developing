"""Profili pellicola: file JSON in `profiles/` che descrivono come si comporta una pellicola."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

FilmType = Literal["color_negative", "bw_negative", "slide"]

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


@dataclass(frozen=True)
class FilmProfile:
    id: str
    name: str
    type: FilmType
    mask_rgb: tuple[float, float, float]
    gamma_rgb: tuple[float, float, float]
    print_contrast: float
    color_matrix: tuple[tuple[float, ...], ...]


def _triple(data: dict, key: str) -> tuple[float, float, float]:
    v = data[key]
    if len(v) != 3 or any(float(x) <= 0 for x in v):
        raise ValueError(f"'{key}' deve contenere 3 valori positivi")
    return tuple(float(x) for x in v)  # type: ignore[return-value]


def _parse(data: dict) -> FilmProfile:
    try:
        if data["type"] not in get_args(FilmType):
            raise ValueError(f"Tipo di pellicola non valido: {data['type']!r}")
        matrix = data["color_matrix"]
        if len(matrix) != 3 or any(len(r) != 3 for r in matrix):
            raise ValueError("'color_matrix' deve essere una matrice 3x3")
        contrast = float(data["print_contrast"])
        if contrast <= 0:
            raise ValueError("'print_contrast' deve essere positivo")
        return FilmProfile(
            id=str(data["id"]),
            name=str(data["name"]),
            type=data["type"],
            mask_rgb=_triple(data, "mask_rgb"),
            gamma_rgb=_triple(data, "gamma_rgb"),
            print_contrast=contrast,
            color_matrix=tuple(tuple(float(x) for x in r) for r in matrix),
        )
    except KeyError as e:
        raise ValueError(f"Campo mancante nel profilo: {e.args[0]}") from None


def list_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def load_profile(id_or_path: str) -> FilmProfile:
    path = Path(id_or_path)
    if path.suffix.lower() != ".json" or not path.exists():
        path = PROFILES_DIR / f"{id_or_path}.json"
    if not path.exists():
        raise ValueError(
            f"Profilo sconosciuto: {id_or_path!r}. Disponibili: {', '.join(list_profiles())}"
        )
    return _parse(json.loads(path.read_text(encoding="utf-8")))
