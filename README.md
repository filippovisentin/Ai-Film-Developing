# Ai-Film-Developing
Los ultimos son los primeros

Prototipo di un'app che accompagna la pellicola dal rullino scattato alla foto digitale:
**sviluppo a casa guidato** e **digitalizzazione del negativo con lo smartphone**, con una
versione "Originale" fedele e, in futuro, una versione migliorata dall'AI.

> Stato: prototipi Python testati (motore di conversione e guida allo sviluppo). L'app per
> iPhone/Android verrà dopo; per ora c'è una pagina web di prova.

## Come funziona

1. **Scatti** il rullino con la tua macchina a pellicola.
2. **Sviluppi a casa**: `devguide` calcola tempi e bagni dalle schede ufficiali dei produttori
   e guida il timer (agitazione, temperatura, riuso dei chimici).
3. **Fotografi il negativo** con il telefono, appoggiato su una luce (tablet o pannello LED).
4. **Il motore** (`filmengine`) trova il fotogramma, toglie la maschera arancione, inverte in
   densità e simula la carta da stampa.

Si parte dal **negativo** (la striscia di pellicola), non dalla stampa dell'album.
Guida illustrata: [`web/come-funziona.html`](web/come-funziona.html).

## Struttura

| Cartella | Contenuto |
|---|---|
| `filmengine/` | Motore di conversione: lettura (DNG/JPEG/TIFF), correzione della luce, ritaglio, inversione in densità, carta da stampa, multi-scatto |
| `profiles/` | Profili pellicola (JSON) |
| `devguide/` | Sviluppo a casa: ricettario, calcolo dei tempi, timer guidato |
| `recipes/` | Ricette con fonte obbligatoria (Ilford HP5 Plus, CineStill Cs41) |
| `tools/` | Valutazione su negativi reali, simulatore di scatto da telefono, pagina di confronto |
| `web/` | Pagine di prova (`come-funziona.html`, `index.html`) |
| `docs/` | Specifica di progetto e piani di implementazione |
| `tests/` | Test automatici (pytest) |

## Uso rapido

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e .[dev]     # su macOS/Linux: .venv/bin/python
.venv/Scripts/python -m pytest -q
```

Sviluppare negativi fotografati (anche più scatti per fotogramma):

```bash
.venv/Scripts/python -m filmengine develop foto/*.jpg --profile generic_color --base base.jpg --light luce.jpg --stack 4
```

Piano di sviluppo a casa:

```bash
.venv/Scripts/python -m devguide plan bw --recipe bw_hp5_plus --developer ilfosol3 --dilution 1+9 --ei 400 --temp 21
.venv/Scripts/python -m devguide plan c41 --recipe c41_cinestill_cs41_liquid --temp 39
```

## Dati e fonti

- **Tempi di sviluppo**: solo da schede tecniche pubbliche dei produttori, citate in ogni ricetta.
  L'app non stima tempi che la scheda non fornisce. Verifica sempre sulla scheda aggiornata.
- **Negativi di prova**: non inclusi nel repository. Le valutazioni usano il dataset
  [BlueNeg](https://huggingface.co/datasets/ttgroup/blueneg-release)
  ("Copyrighted by Tien-Tsin Wong"); `tools/evaluate.py` e `tools/build_gallery.py`
  lavorano su una copia locale in `testdata/`.

## Sicurezza

Lo sviluppo usa chimici: guanti, occhiali, ambiente aerato. Fissaggio e sbianca-fissaggio
contengono argento e vanno smaltiti in un centro di raccolta, non nello scarico.
Un rullino non sviluppato non va mai aperto alla luce.
