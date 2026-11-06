"""Ricettario: processi di sviluppo letti da file JSON con la fonte obbligatoria."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

RECIPES_DIR = Path(__file__).resolve().parent.parent / "recipes"


@dataclass(frozen=True)
class Source:
    title: str
    url: str
    date: str


@dataclass(frozen=True)
class Agitation:
    initial_s: int     # agitazione iniziale (inversioni o continua) in secondi
    every_s: int       # poi un'agitazione ogni ... secondi
    inversions: int    # numero di inversioni per agitazione
    window_s: int      # durata di ogni agitazione


@dataclass(frozen=True)
class Bath:
    name: str
    minutes: float
    note: str


@dataclass(frozen=True)
class BWRecipe:
    id: str
    film: str
    iso_box: int
    developers: dict[str, dict[str, dict[int, float]]]
    temp_ref_c: float
    temp_range_c: tuple[float, float]
    temp_examples: list[tuple[float, float, float]]
    agitation: Agitation
    stop: Bath
    fix: Bath
    wash: str
    notes: list[str]
    source: Source
    process: str = "bw"


@dataclass(frozen=True)
class C41Kit:
    id: str
    name: str
    temps_c: list[float]
    times: dict[str, list[float | None]]
    agitation_by_temp: list[tuple[float, Agitation]]
    presoak: Bath
    blix: Bath
    wash: Bath
    stabilizer: Bath
    reuse_pct_per_roll: dict[str, float]
    capacity_rolls: dict[str, int]
    notes: list[str]
    source: Source
    process: str = "c41"


def _positive(v, what: str) -> float:
    v = float(v)
    if v <= 0:
        raise ValueError(f"{what}: il tempo deve essere positivo")
    return v


def _source(d: dict) -> Source:
    s = d.get("source")
    if not s or not str(s.get("url", "")).startswith("https://"):
        raise ValueError("Ricetta senza fonte: ogni tempo deve citare la scheda del produttore (url https)")
    return Source(str(s["title"]), str(s["url"]), str(s["date"]))


def _bath(d: dict) -> Bath:
    return Bath(str(d["name"]), _positive(d["minutes"], d["name"]), str(d.get("note", "")))


def _agitation(d: dict) -> Agitation:
    return Agitation(int(d["initial_s"]), int(d["every_s"]), int(d["inversions"]), int(d["window_s"]))


def _bw(d: dict) -> BWRecipe:
    devs = {
        dev: {dil: {int(ei): _positive(t, f"{dev} {dil} EI {ei}") for ei, t in eis.items()}
              for dil, eis in dils.items()}
        for dev, dils in d["developers"].items()
    }
    lo, hi = (float(x) for x in d["temp_range_c"])
    return BWRecipe(
        id=d["id"], film=d["film"], iso_box=int(d["iso_box"]), developers=devs,
        temp_ref_c=float(d["temp_ref_c"]), temp_range_c=(lo, hi),
        temp_examples=[tuple(float(x) for x in e) for e in d["temp_examples"]],
        agitation=_agitation(d["agitation"]), stop=_bath(d["stop"]), fix=_bath(d["fix"]),
        wash=str(d["wash"]), notes=list(d.get("notes", [])), source=_source(d),
    )


def _c41(d: dict) -> C41Kit:
    temps = [float(t) for t in d["temps_c"]]
    if temps != sorted(temps):
        raise ValueError("temps_c deve essere in ordine crescente")
    times = {}
    for k, row in d["times"].items():
        if len(row) != len(temps):
            raise ValueError(f"Riga '{k}': {len(row)} valori per {len(temps)} temperature")
        times[k] = [None if v is None else _positive(v, k) for v in row]
    return C41Kit(
        id=d["id"], name=d["name"], temps_c=temps, times=times,
        agitation_by_temp=[(float(t), _agitation(a)) for t, a in d["agitation_by_temp"]],
        presoak=_bath(d["presoak"]), blix=_bath(d["blix"]), wash=_bath(d["wash"]),
        stabilizer=_bath(d["stabilizer"]),
        reuse_pct_per_roll={k: float(v) for k, v in d["reuse_pct_per_roll"].items()},
        capacity_rolls={k: int(v) for k, v in d["capacity_rolls"].items()},
        notes=list(d.get("notes", [])), source=_source(d),
    )


def list_recipes() -> list[str]:
    return sorted(p.stem for p in RECIPES_DIR.glob("*.json"))


def load_recipe(id_or_path: str) -> BWRecipe | C41Kit:
    path = Path(id_or_path)
    if path.suffix.lower() != ".json" or not path.exists():
        path = RECIPES_DIR / f"{id_or_path}.json"
    if not path.exists():
        raise ValueError(f"Ricetta sconosciuta: {id_or_path!r}. Disponibili: {', '.join(list_recipes())}")
    d = json.loads(path.read_text(encoding="utf-8"))
    try:
        if d.get("process") == "bw":
            return _bw(d)
        if d.get("process") == "c41":
            return _c41(d)
    except KeyError as e:
        raise ValueError(f"Campo mancante nella ricetta: {e.args[0]}") from None
    raise ValueError(f"Processo non supportato: {d.get('process')!r}")
