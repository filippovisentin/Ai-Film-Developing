# Sviluppo a casa — Piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prototipo Python (portabile in Dart) del modulo "Sviluppo a casa": ricettario verificato, calcolo dei tempi e timer guidato.

**Architecture:** Pacchetto `devguide/` separato da `filmengine/`. Dati in `recipes/*.json` con la fonte obbligatoria. Tre moduli: `recipes.py` (caricamento + validazione), `calculator.py` (tempi: temperatura, push/pull, riuso), `timer.py` (macchina a stati basata su orari, non su tick, quindi robusta allo schermo spento). CLI `python -m devguide`.

**Tech Stack:** Python 3.12, solo libreria standard; pytest.

**Spec:** `docs/specs/2026-11-06-app-sviluppo-pellicola-design.md` §10

## Global Constraints

- **Nessun tempo inventato**: ogni tempo viene da una scheda del produttore, citata nel file. Un caso non coperto dalla scheda (EI assente, "X" in tabella, temperatura fuori intervallo) è un **errore esplicito**, mai una stima.
- Valori derivati (interpolazione tra colonne, compensazione della temperatura) sono permessi solo dentro l'intervallo della scheda e marcati come `derived` nel risultato.
- Tempi in secondi interi nell'API; minuti con decimali solo nella presentazione.
- Testi per l'utente in italiano.

## Dati verificati (fonti)

- **Ilford HP5 Plus**, scheda tecnica Nov 2018 (ilfordphoto.com): tabella a 20 °C; esempi di temperatura "6 min a 20 °C → 4½ a 23 °C, 9 a 16 °C"; agitazione: 4 inversioni nei primi 10 s, poi 4 nei primi 10 s di ogni minuto; ILFOSTOP 1+19, 10 s; RAPID FIXER 1+4, 2–5 min; lavaggio 5/10/20 inversioni; soluzioni 18–24 °C.
- **CineStill CS41 Liquid**, istruzioni 2026 (cinestill.film), tabella letta sull'immagine della pagina: colonne 22/24/27/29,5/32/35/39 °C × normale/push+1/+2/+3/pull−1; agitazione per fascia; blix 8 min a 24–40 °C; lavaggio 3 min; riuso +2 %/rullino (quart), +4 % (pint), +0,5 % (gallon); riuso sconsigliato col push; capacità consigliata 8 rullini 135-36 per quart.

## Review Focus

1. Temperatura tra due colonne della tabella C-41: interpolazione log-lineare, marcata come derivata, mai estrapolazione → test in Task 2.
2. Push con chimici riusati: avviso del produttore riportato, non blocco → test in Task 2.
3. Timer con l'app in background per minuti: lo stato si ricalcola dall'orologio → test in Task 3.
4. Pausa durante un bagno: il tempo del bagno non scorre → test in Task 3.
5. Rullini oltre la capacità consigliata: avviso → test in Task 2.

---

### Task 1: Ricettario e validazione

**Files:** `devguide/__init__.py`, `devguide/recipes.py`, `recipes/bw_hp5_plus.json`, `recipes/c41_cinestill_cs41_liquid.json`; Test `tests/test_devguide_recipes.py`

**Interfaces — Produces:**
```python
@dataclass(frozen=True) class Source: title: str; url: str; date: str
@dataclass(frozen=True) class Agitation: initial_s: int; every_s: int; inversions: int; window_s: int
@dataclass(frozen=True) class Bath: name: str; minutes: float; note: str
@dataclass(frozen=True) class BWRecipe:
    id: str; film: str; process: "bw"; iso_box: int
    developers: dict[str, dict[str, dict[int, float]]]   # sviluppo -> diluizione -> EI -> minuti a 20 °C
    temp_ref_c: float; temp_range_c: tuple[float, float]
    temp_examples: list[tuple[float, float, float]]      # (minuti a ref, temperatura, minuti)
    agitation: Agitation; stop: Bath; fix: Bath; wash: str; source: Source
@dataclass(frozen=True) class C41Kit:
    id: str; name: str; process: "c41"; temps_c: list[float]
    times: dict[str, list[float | None]]                 # "normal","push1","push2","push3","pull1"
    agitation_by_temp: list[tuple[float, Agitation]]     # (temperatura minima della fascia, agitazione)
    blix: Bath; wash: Bath; stabilizer: Bath; presoak: Bath
    reuse_pct_per_roll: dict[str, float]; capacity_rolls: dict[str, int]; source: Source
def load_recipe(id: str) -> BWRecipe | C41Kit
def list_recipes() -> list[str]
```
- [ ] Test: HP5 Ilfosol 3 1+9 EI 400 = 6.5; DD-X 1+4 EI 3200 = 20; ID-11 1+1 EI 800 = 16.5; CS41 normale a 39 °C = 3.5, push2 a 27 °C = 37, push3 a 27 °C = None; ogni ricetta ha `source.url`; JSON senza fonte → ValueError "fonte"; tempi ≤ 0 → ValueError.
- [ ] Implementa; pass; commit.

### Task 2: Calcolatore

**Files:** `devguide/calculator.py`; Test `tests/test_devguide_calculator.py`

**Interfaces — Produces:**
```python
@dataclass class Timing: seconds: int; derived: bool; warnings: list[str]; agitation: Agitation
def bw_dev_time(r: BWRecipe, developer: str, dilution: str, ei: int, temp_c: float) -> Timing
def c41_dev_time(k: C41Kit, temp_c: float, push: int = 0, rolls_done: int = 0, volume: str = "quart") -> Timing
```
- Temperatura B/N: `t = t_ref * f ** (temp - ref)`, con `f` = media geometrica dei fattori per grado degli esempi Ilford (≈ 0,906); fuori da `temp_range_c` → ValueError.
- C-41: colonna esatta se la temperatura coincide (±0,25 °C), altrimenti interpolazione log-lineare tra le colonne vicine non vuote (derived=True); fuori intervallo o cella "X" → ValueError.
- Riuso: `t *= 1 + pct/100 * rolls_done`; push e riuso insieme → avviso; `rolls_done >= capacità` → avviso.
- [ ] Test: HP5 Ilfosol 1+9 EI 400 a 23 °C ≈ 6,5·0,75 min (±5 s); a 18 °C ≈ 6,5·0,906⁻² min; 16 °C → errore (fuori 18–24); Ilfosol 1+9 EI 1600 → errore "non indicato"; CS41 39 °C dopo 4 rullini = 227 s, dopo 8 = 244 s; pint 4 rullini = +16 %; 37 °C → derived, tra 210 s e 345 s; 20 °C → errore; push 3 a 27 °C → errore; push+riuso → avviso; agitazione a 24 °C = continua 60 s, poi 4 inversioni ogni 120 s.
- [ ] Implementa; pass; commit.

### Task 3: Timer guidato

**Files:** `devguide/timer.py`; Test `tests/test_devguide_timer.py`

**Interfaces — Produces:**
```python
@dataclass(frozen=True) class Step: name: str; seconds: int; agitation: Agitation | None; note: str = ""
@dataclass class SessionState: step_index: int; step_name: str; remaining_s: int; overdue_s: int; agitate_now: bool; next_agitation_in_s: int | None; paused: bool; finished: bool
class Session:
    def __init__(self, steps: list[Step], clock: Callable[[], float] = time.monotonic)
    def start(self) -> None; def pause(self) -> None; def resume(self) -> None; def next_step(self) -> None
    def state(self) -> SessionState
def build_bw_session(r, developer, dilution, ei, temp_c) -> tuple[list[Step], list[str]]
def build_c41_session(k, temp_c, push=0, rolls_done=0, volume="quart", presoak=True) -> tuple[list[Step], list[str]]
```
- Lo stato si **ricalcola** da orari salvati (inizio bagno, pause accumulate), non da tick.
- Un bagno non passa da solo al successivo (bisogna svuotare la tank): `next_step()`; a tempo scaduto lo stato riporta `overdue_s`.
- [ ] Test con orologio finto: agitazione HP5 attiva a 0–10 s, 60–70 s, 120–130 s; pausa di 30 s non consuma tempo; salto di 10 min (app in background) → remaining 0 e overdue corretto; sequenza C-41 = [pre-bagno, rivelatore, blix, lavaggio, stabilizzatore]; sequenza B/N = [rivelatore, arresto, fissaggio, lavaggio].
- [ ] Implementa; pass; commit.

### Task 4: CLI

**Files:** `devguide/__main__.py`; Test `tests/test_devguide_cli.py`
- `python -m devguide list`; `python -m devguide plan bw --recipe bw_hp5_plus --developer ilfosol3 --dilution 1+9 --ei 400 --temp 21`; `python -m devguide plan c41 --recipe c41_cinestill_cs41_liquid --temp 39 --push 1 --rolls-done 3`. Stampa passi, tempi mm:ss, agitazione, avvisi, fonte, promemoria di sicurezza e smaltimento.
- [ ] Test: exit 0 e tempo atteso nel testo; caso non coperto → exit 2 con messaggio chiaro.
- [ ] Implementa; pass; commit.
