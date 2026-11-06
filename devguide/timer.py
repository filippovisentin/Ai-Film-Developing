"""Timer guidato dello sviluppo.

Lo stato non dipende da "tick": si ricalcola sempre dall'orologio a partire da orari salvati,
così resta corretto anche se il telefono sospende l'app con lo schermo spento.
Un bagno non passa da solo al successivo: bisogna svuotare la tank, quindi lo decide l'utente.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .calculator import bw_dev_time, c41_dev_time
from .recipes import Agitation, BWRecipe, C41Kit


@dataclass(frozen=True)
class Step:
    name: str
    seconds: int                    # 0 = passo manuale senza conto alla rovescia
    agitation: Agitation | None
    note: str = ""


@dataclass
class SessionState:
    step_index: int
    step_name: str
    remaining_s: int
    overdue_s: int
    agitate_now: bool
    next_agitation_in_s: int | None
    paused: bool
    finished: bool


def _agitating(a: Agitation, elapsed: float) -> bool:
    if elapsed < a.initial_s:
        return True
    if a.every_s <= 0:
        return False
    k = int(elapsed // a.every_s)
    return k >= 1 and k * a.every_s >= a.initial_s and elapsed - k * a.every_s < a.window_s


def _next_agitation(a: Agitation, elapsed: float, duration: int) -> int | None:
    if a.every_s <= 0:
        return None
    k = int(elapsed // a.every_s) + 1
    while k * a.every_s < a.initial_s:
        k += 1
    start = k * a.every_s
    return int(round(start - elapsed)) if start < duration else None


class Session:
    def __init__(self, steps: list[Step], clock: Callable[[], float] = time.monotonic):
        if not steps:
            raise ValueError("La sessione non ha passi")
        self.steps = steps
        self._clock = clock
        self._index = 0
        self._step_start: float | None = None
        self._paused_at: float | None = None
        self._paused_total = 0.0

    def start(self) -> None:
        self._index, self._step_start = 0, self._clock()
        self._paused_at, self._paused_total = None, 0.0

    def pause(self) -> None:
        if self._paused_at is None:
            self._paused_at = self._clock()

    def resume(self) -> None:
        if self._paused_at is not None:
            self._paused_total += self._clock() - self._paused_at
            self._paused_at = None

    def next_step(self) -> None:
        self.resume()
        self._index += 1
        self._step_start, self._paused_total = self._clock(), 0.0

    def state(self) -> SessionState:
        if self._step_start is None:
            raise RuntimeError("Sessione non avviata: chiama start()")
        if self._index >= len(self.steps):
            return SessionState(len(self.steps), "Fine", 0, 0, False, None, False, True)
        step = self.steps[self._index]
        now = self._paused_at if self._paused_at is not None else self._clock()
        elapsed = max(0.0, now - self._step_start - self._paused_total)
        remaining = max(0, int(round(step.seconds - elapsed)))
        overdue = max(0, int(round(elapsed - step.seconds)))
        running = remaining > 0
        a = step.agitation
        return SessionState(
            step_index=self._index,
            step_name=step.name,
            remaining_s=remaining,
            overdue_s=overdue,
            agitate_now=bool(a and running and _agitating(a, elapsed)),
            next_agitation_in_s=_next_agitation(a, elapsed, step.seconds) if a and running else None,
            paused=self._paused_at is not None,
            finished=False,
        )


def _minutes_note(t) -> list[str]:
    return list(t.warnings)


def build_bw_session(r: BWRecipe, developer: str, dilution: str, ei: int,
                     temp_c: float) -> tuple[list[Step], list[str]]:
    t = bw_dev_time(r, developer, dilution, ei, temp_c)
    warnings = _minutes_note(t)
    if t.derived:
        warnings.append(f"Tempo ricalcolato per {temp_c:g} °C dagli esempi della scheda "
                        f"(riferimento {r.temp_ref_c:g} °C).")
    steps = [
        Step(f"Rivelatore {developer} {dilution}", t.seconds, t.agitation,
             f"EI {ei}, {temp_c:g} °C"),
        Step(r.stop.name, int(round(r.stop.minutes * 60)), None, r.stop.note),
        Step(r.fix.name, int(round(r.fix.minutes * 60)), None, r.fix.note),
        Step("Lavaggio", 0, None, r.wash),
    ]
    return steps, warnings


def build_c41_session(k: C41Kit, temp_c: float, push: int = 0, rolls_done: int = 0,
                      volume: str = "quart", presoak: bool = True) -> tuple[list[Step], list[str]]:
    t = c41_dev_time(k, temp_c, push, rolls_done, volume)
    warnings = _minutes_note(t)
    if t.derived:
        warnings.append(f"{temp_c:g} °C non è una colonna della tabella: tempo interpolato tra le "
                        "temperature vicine della scheda.")
    steps = []
    if presoak:
        steps.append(Step(k.presoak.name, int(round(k.presoak.minutes * 60)), None, k.presoak.note))
    steps += [
        Step("Rivelatore", t.seconds, t.agitation, f"{temp_c:g} °C"),
        Step(k.blix.name, int(round(k.blix.minutes * 60)), t.agitation, k.blix.note),
        Step(k.wash.name, int(round(k.wash.minutes * 60)), None, k.wash.note),
        Step(k.stabilizer.name, int(round(k.stabilizer.minutes * 60)),
             Agitation(initial_s=15, every_s=0, inversions=0, window_s=0), k.stabilizer.note),
    ]
    return steps, warnings
