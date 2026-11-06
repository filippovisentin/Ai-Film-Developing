"""Calcolo dei tempi di sviluppo. Regola: mai un tempo che la scheda del produttore non copre."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .recipes import Agitation, BWRecipe, C41Kit

COLUMN_TOLERANCE_C = 0.25
PUSH_ROWS = {-1: "pull1", 0: "normal", 1: "push1", 2: "push2", 3: "push3"}


@dataclass
class Timing:
    seconds: int
    derived: bool                  # True se calcolato (temperatura/interpolazione), non letto in tabella
    warnings: list[str] = field(default_factory=list)
    agitation: Agitation | None = None


def _bw_factor_per_degree(r: BWRecipe) -> float:
    """Fattore per grado ricavato dagli esempi numerici della scheda (media geometrica)."""
    logs = [math.log(t / t_ref) / (temp - r.temp_ref_c) for t_ref, temp, t in r.temp_examples]
    return math.exp(sum(logs) / len(logs))


def bw_dev_time(r: BWRecipe, developer: str, dilution: str, ei: int, temp_c: float) -> Timing:
    if developer not in r.developers:
        raise ValueError(f"Rivelatore non presente nella scheda di {r.film}. "
                         f"Disponibili: {', '.join(sorted(r.developers))}")
    dils = r.developers[developer]
    if dilution not in dils:
        raise ValueError(f"Diluizione {dilution} non indicata per {developer}. Disponibili: {', '.join(dils)}")
    eis = dils[dilution]
    if ei not in eis:
        raise ValueError(f"EI {ei} non indicato dalla scheda per {developer} {dilution}: "
                         f"EI disponibili {', '.join(str(e) for e in sorted(eis))}. "
                         "L'app non stima tempi che il produttore non fornisce.")
    lo, hi = r.temp_range_c
    if not lo <= temp_c <= hi:
        raise ValueError(f"Temperatura {temp_c:g} °C fuori dall'intervallo della scheda ({lo:g}-{hi:g} °C)")
    minutes = eis[ei]
    derived = abs(temp_c - r.temp_ref_c) > 1e-9
    if derived:
        minutes *= _bw_factor_per_degree(r) ** (temp_c - r.temp_ref_c)
    return Timing(int(round(minutes * 60)), derived, [], r.agitation)


def _c41_agitation(k: C41Kit, temp_c: float) -> Agitation:
    band = k.agitation_by_temp[0][1]
    for t_min, ag in k.agitation_by_temp:
        if temp_c >= t_min - COLUMN_TOLERANCE_C:
            band = ag
    return band


def c41_dev_time(k: C41Kit, temp_c: float, push: int = 0, rolls_done: int = 0,
                 volume: str = "quart") -> Timing:
    if push not in PUSH_ROWS:
        raise ValueError("Push/pull supportati dalla scheda: -1, 0, +1, +2, +3 stop")
    row_name = PUSH_ROWS[push]
    row = k.times[row_name]
    label = "normale" if push == 0 else (f"push +{push}" if push > 0 else "pull -1")
    temps = k.temps_c
    lo, hi = temps[0], temps[-1]
    if not lo - COLUMN_TOLERANCE_C <= temp_c <= hi + COLUMN_TOLERANCE_C:
        raise ValueError(f"Temperatura {temp_c:g} °C fuori dalla tabella ({lo:g}-{hi:g} °C)")

    exact = [i for i, t in enumerate(temps) if abs(t - temp_c) <= COLUMN_TOLERANCE_C]
    if exact:
        minutes = row[exact[0]]
        derived = False
        if minutes is None:
            raise ValueError(f"Sviluppo {label} non previsto dalla scheda a {temps[exact[0]]:g} °C")
    else:
        hi_i = next(i for i, t in enumerate(temps) if t > temp_c)
        a, b = row[hi_i - 1], row[hi_i]
        if a is None or b is None:
            raise ValueError(f"Sviluppo {label} non previsto dalla scheda tra "
                             f"{temps[hi_i - 1]:g} e {temps[hi_i]:g} °C")
        f = (temp_c - temps[hi_i - 1]) / (temps[hi_i] - temps[hi_i - 1])
        minutes = math.exp((1 - f) * math.log(a) + f * math.log(b))
        derived = True

    warnings: list[str] = []
    if rolls_done:
        if volume not in k.reuse_pct_per_roll:
            raise ValueError(f"Volume '{volume}' non previsto. Disponibili: {', '.join(k.reuse_pct_per_roll)}")
        minutes *= 1 + k.reuse_pct_per_roll[volume] / 100 * rolls_done
        if push > 0:
            warnings.append("Il produttore sconsiglia il riuso dei chimici per il push.")
        cap = k.capacity_rolls.get(volume)
        if cap is not None and rolls_done >= cap:
            warnings.append(f"Superata la capacità consigliata ({cap} rullini per {volume}): "
                            "i risultati possono peggiorare, conviene un rullino di prova.")
    return Timing(int(round(minutes * 60)), derived, warnings, _c41_agitation(k, temp_c))
