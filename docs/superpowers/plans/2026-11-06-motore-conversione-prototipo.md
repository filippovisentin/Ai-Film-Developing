# Prototipo del motore di conversione — Piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uno strumento Python da riga di comando che converte le foto di negativi fatte con lo smartphone nella versione **Originale** (fase 1 della specifica).

**Architecture:** Un pacchetto `filmengine` con un modulo per ogni fase della pipeline (lettura, calibrazione, geometria, inversione, profilo) più `pipeline.py`, che le concatena, e una CLI. Ogni fase è una funzione pura su array NumPy `float32` lineari HxWx3, così la logica si potrà tradurre 1:1 in C++. I test usano negativi **sintetici** generati da un positivo noto, per verificare il ritorno al positivo.

**Tech Stack:** Python 3.12, NumPy, OpenCV (`opencv-python`), `rawpy` (DNG), `imageio` + `tifffile` (lettura e scrittura), pytest.

**Spec:** `docs/specs/2026-11-06-app-sviluppo-pellicola-design.md` (sezioni 3 e 8, fase 1)

## Global Constraints

- Tutte le fasi lavorano su `np.ndarray` `float32`, forma `(H, W, 3)`, valori lineari (proporzionali alla luce), mai sRGB, salvo l'uscita finale.
- Risultato deterministico: stessi ingressi → stesso output bit per bit (niente casualità, niente dipendenza dall'ordine dei file).
- Pipeline in 7 fasi nell'ordine della spec §3: linearizzazione → correzione luce → geometria → neutralizzazione della maschera → inversione in densità (saltata per le diapositive) → profilo pellicola → bilanciamento sul rullino intero.
- Profili pellicola come file JSON in `profiles/`, mai nel codice.
- Nessuna AI in questa fase.
- Uscita: TIFF RGB a 16 bit (archivio) e JPEG qualità 95 (anteprima), entrambi in sRGB.

## Review Focus

1. **Input JPEG/HEIC invece di RAW**: un JPEG va linearizzato (curva sRGB inversa) con un avviso; un formato non supportato (es. HEIC) deve dare un errore chiaro, non un crash → test in Task 2.
2. **Base o luce sovraesposte / pixel a zero**: `log10(0)` e divisioni per zero non devono produrre NaN o inf nell'immagine → test in Task 3 e Task 4.
3. **Fotogramma non trovato** (bordi poco netti, pellicola storta): si usa l'immagine intera con un avviso, senza fallire → test in Task 5.
4. **Fotogramma molto sotto- o sovraesposto nel rullino**: il bilanciamento sul rullino non deve renderlo nero o bruciato; gli altri fotogrammi non devono cambiare se se ne aggiunge uno estremo → test in Task 4.
5. **Negativo B/N fotografato a colori**: l'uscita deve essere neutra (R=G=B), senza dominanti → test in Task 4.

---

## Struttura dei file

```
pyproject.toml
profiles/generic_color.json   profiles/generic_bw.json
profiles/portra_400.json      profiles/hp5_400.json
filmengine/__init__.py
filmengine/profile.py      # FilmProfile + load_profile
filmengine/imageio_.py     # load_image, save_outputs
filmengine/calibration.py  # correct_light, measure_base, estimate_base_from_border
filmengine/geometry.py     # find_frame_corners, warp_frame
filmengine/invert.py       # to_density, RollLevels, compute_roll_levels, render_positive
filmengine/pipeline.py     # Calibration, develop_roll
filmengine/__main__.py     # CLI
tests/synthetic.py         # generatore di negativi sintetici
tests/test_*.py
```

---

### Task 1: Progetto e profili pellicola

**Files:**
- Create: `pyproject.toml`, `filmengine/__init__.py`, `filmengine/profile.py`, `profiles/*.json` (4 file)
- Test: `tests/test_profile.py`

**Interfaces:**
- Produces:
  ```python
  FilmType = Literal["color_negative", "bw_negative", "slide"]
  @dataclass(frozen=True)
  class FilmProfile:
      id: str; name: str; type: FilmType
      mask_rgb: tuple[float, float, float]      # colore tipico della base (lineare, 0–1)
      gamma_rgb: tuple[float, float, float]     # contrasto del negativo per canale
      print_contrast: float                     # pendenza della curva a S di stampa
      color_matrix: tuple[tuple[float, ...], ...]  # 3x3, applicata in lineare
  def load_profile(id_or_path: str) -> FilmProfile
  def list_profiles() -> list[str]
  ```

- [ ] **Step 1: Inizializza git e il progetto.** `git init`; `pyproject.toml` con dipendenze `numpy`, `opencv-python`, `rawpy`, `imageio`, `tifffile` e `pytest` come dipendenza di sviluppo; `pip install -e .[dev]`.
- [ ] **Step 2: Scrivi i test che falliscono**
  ```python
  def test_load_builtin_profile():
      p = load_profile("portra_400")
      assert p.type == "color_negative" and len(p.gamma_rgb) == 3
  def test_list_profiles_contains_generics():
      assert {"generic_color", "generic_bw", "portra_400", "hp5_400"} <= set(list_profiles())
  def test_unknown_profile_raises_clear_error():
      with pytest.raises(ValueError, match="Profilo sconosciuto"): load_profile("nope")
  def test_bad_matrix_shape_rejected(tmp_path): ...  # matrice 2x3 → ValueError
  ```
- [ ] **Step 3: Esegui** `pytest tests/test_profile.py -v` → FAIL (modulo mancante).
- [ ] **Step 4: Implementa `profile.py` e i 4 JSON.** Valori iniziali: generic_color e portra_400 con `mask_rgb` ≈ (0.80, 0.50, 0.32), `gamma_rgb` (0.60, 0.60, 0.60) e matrice identità; i profili B/N e hp5_400 con `mask_rgb` (0.85, 0.85, 0.85) e gamma 0.65. `print_contrast` 1.0 per i generici, 1.1 per portra, 1.25 per hp5. Sono valori di partenza da tarare in Task 6.
- [ ] **Step 5: Esegui** i test → PASS.
- [ ] **Step 6: Commit** `feat: profili pellicola e caricamento`

### Task 2: Lettura e linearizzazione

**Files:** Create `filmengine/imageio_.py`; Test `tests/test_imageio.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class LoadedImage:
      rgb: np.ndarray          # float32 (H,W,3) lineare 0–1
      is_raw: bool
      warnings: list[str]
  def load_image(path: str | Path) -> LoadedImage
  def save_outputs(rgb_linear: np.ndarray, out_stem: Path) -> tuple[Path, Path]  # (tiff16, jpeg)
  ```

- [ ] **Step 1: Test che falliscono**
  - `test_jpeg_is_linearized`: un PNG/JPEG grigio uniforme a valore sRGB 128 → media lineare ≈ 0.2158 (±0.01), `is_raw` False, un avviso che contiene "non RAW".
  - `test_unsupported_format_raises`: un file `.heic` → `ValueError` con "Formato non supportato" e l'elenco dei formati ammessi (`.dng .jpg .jpeg .png .tif .tiff`).
  - `test_save_outputs_roundtrip`: un gradiente lineare salvato → il TIFF è `uint16` a 3 canali; ricaricato con `load_image` coincide entro 1/1000.
  - `test_16bit_tiff_input_keeps_precision`.
- [ ] **Step 2: Esegui** → FAIL.
- [ ] **Step 3: Implementa.** DNG con `rawpy.postprocess(gamma=(1,1), no_auto_bright=True, output_bps=16, use_camera_wb=False, user_wb=[1,1,1,1], output_color=rawpy.ColorSpace.raw)` → /65535. JPEG/PNG/TIFF con imageio, poi curva sRGB inversa (dati a 8 bit) o /65535 (TIFF a 16 bit, già lineare). L'uscita applica la curva sRGB diretta.
- [ ] **Step 4: Esegui** → PASS. **Step 5: Commit** `feat: lettura e scrittura immagini lineari`

### Task 3: Calibrazione (luce e base)

**Files:** Create `filmengine/calibration.py`; Test `tests/test_calibration.py`, `tests/synthetic.py`

**Interfaces:**
- Consumes: `LoadedImage.rgb`
- Produces:
  ```python
  def correct_light(img: np.ndarray, light: np.ndarray | None) -> np.ndarray
  def measure_base(base_img: np.ndarray) -> np.ndarray          # (3,) float32 > 0
  def estimate_base_from_border(img: np.ndarray) -> np.ndarray  # (3,), fallback
  ```
  `tests/synthetic.py`:
  `make_scene(h=200, w=300, seed=0) -> np.ndarray` (positivo lineare 0.01–1, con patch colorate e un grigio neutro in posizione nota);
  `make_negative(scene, mask_rgb, gamma_rgb, border_px=20, vignette=0.0) -> np.ndarray` con T_c = mask_c · (scene_c / 0.01)^(−gamma_c), più un bordo di base pura.

- [ ] **Step 1: Test che falliscono**
  - `test_correct_light_removes_vignette`: negativo con `vignette=0.3` e la luce corrispondente → la deviazione standard della base dopo la correzione è < 1%.
  - `test_correct_light_none_is_identity`.
  - `test_measure_base_uses_median_of_center`: patch uniforme (0.8, 0.5, 0.3) con il 5% di pixel di "polvere" a 0 → risultato entro ±0.01.
  - `test_base_never_zero`: patch nera → ogni canale ≥ 1e-4.
  - `test_estimate_base_from_border`: dal negativo sintetico → entro il 3% di `mask_rgb`.
- [ ] **Step 2: Esegui** → FAIL.
- [ ] **Step 3: Implementa.** `correct_light`: luce sfocata (Gaussian, sigma = 2% del lato minore), normalizzata sul suo 99° percentile, poi divisione con `np.maximum(light, 1e-4)`. `measure_base`: mediana per canale del 50% centrale. `estimate_base_from_border`: 99,5° percentile per canale di una fascia del 5% sui bordi (la base è la zona più trasparente).
- [ ] **Step 4: Esegui** → PASS. **Step 5: Commit** `feat: calibrazione di luce e base`

### Task 4: Inversione, profilo e bilanciamento sul rullino

**Files:** Create `filmengine/invert.py`; Test `tests/test_invert.py`

**Interfaces:**
- Consumes: `FilmProfile`, base `(3,)`
- Produces:
  ```python
  def to_density(img: np.ndarray, base: np.ndarray) -> np.ndarray   # D = -log10(clip(img/base, 1e-5, 1))
  @dataclass(frozen=True)
  class RollLevels:
      low: np.ndarray; high: np.ndarray      # (3,) in "log-esposizione" per canale
  def compute_roll_levels(densities: list[np.ndarray], profile: FilmProfile) -> RollLevels
  def render_positive(density_or_slide: np.ndarray, profile: FilmProfile, levels: RollLevels) -> np.ndarray  # lineare 0–1
  ```

  Algoritmo (non determinato dai test, va seguito così):
  ```
  colore/B&N: L_c = D_c / gamma_c            # log10 dell'esposizione relativa
  B&N:        L = media dei 3 canali, replicata su R,G,B
  diapositiva: L_c = log10(clip(img_c,1e-5,1)), nessuna base
  livelli rullino: per ogni fotogramma, 0,1° e 99,9° percentile di L_c
                   (sottocampionati a passo fisso, niente casualità);
                   low_c / high_c = MEDIANA di quei percentili su tutto il rullino
  n_c = clip((L_c - low_c) / (high_c - low_c), 0, 1)
  scena lineare: s_c = 10 ** ((n_c - 1) * (high_c - low_c))   # 1.0 = bianco
  curva di stampa: s' = s ** print_contrast, poi color_matrix, clip 0–1
  ```
- [ ] **Step 1: Test che falliscono**
  - `test_roundtrip_color_negative`: `make_scene` → `make_negative(mask=(0.8,0.5,0.32), gamma=(0.6,0.55,0.5))` → `to_density` con la base vera → `render_positive` con un profilo di pari gamma, `print_contrast=1` e matrice identità → dopo la normalizzazione per il bianco l'errore assoluto medio rispetto alla scena è < 0.02, e la patch grigia esce neutra (max−min dei canali < 0.01).
  - `test_bw_output_is_neutral`: profilo B/N su un negativo a colori → R==G==B ovunque.
  - `test_slide_skips_inversion`: tipo `slide` su un positivo → monotono crescente rispetto all'ingresso.
  - `test_no_nan_with_zero_pixels`: immagine con zeri e valori sopra la base → nessun NaN o inf, valori in [0,1].
  - `test_roll_levels_robust_to_outlier_frame`: livelli da 5 fotogrammi normali e livelli dagli stessi più uno quasi nero → ogni fotogramma normale cambia, in media, meno di 0.03.
  - `test_deterministic`: due esecuzioni → `np.array_equal`.
- [ ] **Step 2: Esegui** → FAIL.
- [ ] **Step 3: Implementa** seguendo l'algoritmo sopra. È la mediana dei percentili per fotogramma, e non i pixel concatenati, a rendere il rullino robusto a un fotogramma estremo.
- [ ] **Step 4: Esegui** → PASS. **Step 5: Commit** `feat: inversione in densità e livelli del rullino`

### Task 5: Geometria del fotogramma

**Files:** Create `filmengine/geometry.py`; Test `tests/test_geometry.py`

**Interfaces:**
- Produces:
  ```python
  def find_frame_corners(img: np.ndarray, aspect: float = 1.5) -> np.ndarray | None  # (4,2) float32, ordine TL,TR,BR,BL
  def warp_frame(img: np.ndarray, corners: np.ndarray, aspect: float = 1.5) -> np.ndarray
  ```
- [ ] **Step 1: Test che falliscono**
  - `test_finds_rotated_frame`: un fotogramma scuro 3:2 ruotato di 7° e leggermente in prospettiva, dentro una base chiara → angoli entro 3 px da quelli veri.
  - `test_returns_none_on_uniform_image`.
  - `test_warp_output_aspect`: uscita con larghezza/altezza = 1.5 ±1%, lato lungo uguale al lato lungo misurato.
  - `test_portrait_frame_keeps_orientation`: un fotogramma verticale non viene messo in orizzontale.
- [ ] **Step 2: Esegui** → FAIL.
- [ ] **Step 3: Implementa** con OpenCV: luminanza in log → sfocatura → soglia di Otsu (il fotogramma è più denso della base) → contorno più grande → `approxPolyDP`; si accetta solo un quadrilatero con area ≥ 20% dell'immagine; ordinamento degli angoli; `getPerspectiveTransform` + `warpPerspective` (INTER_CUBIC).
- [ ] **Step 4: Esegui** → PASS. **Step 5: Commit** `feat: rilevamento e raddrizzamento del fotogramma`

### Task 6: Pipeline, CLI e prova su foto reali

**Files:** Create `filmengine/pipeline.py`, `filmengine/__main__.py`; Test `tests/test_pipeline.py`

**Interfaces:**
- Consumes: tutte le funzioni dei Task 1–5
- Produces:
  ```python
  @dataclass
  class Calibration:
      base_rgb: np.ndarray | None = None
      light: np.ndarray | None = None
  @dataclass
  class FrameResult:
      source: Path; outputs: tuple[Path, Path]; warnings: list[str]
  def develop_roll(frames: list[Path], profile: FilmProfile, calib: Calibration, out_dir: Path) -> list[FrameResult]
  ```
  CLI:
  `python -m filmengine develop FRAMES... --profile ID [--base FILE] [--light FILE] [--out DIR] [--no-crop]`
  e `python -m filmengine profiles` (elenca i profili).

- [ ] **Step 1: Test che falliscono**
  - `test_develop_roll_end_to_end` (tmp_path): 3 negativi sintetici salvati come TIFF a 16 bit, con bordo e vignettatura, più la luce → 3 coppie TIFF/JPEG; la patch grigia del primo esce neutra (< 0.02).
  - `test_frame_not_found_falls_back_with_warning`: immagine senza bordi → elaborata comunque, avviso che contiene "fotogramma non trovato".
  - `test_no_base_uses_border_estimate_with_warning`.
  - `test_frames_processed_in_sorted_order`: l'ordine di uscita non dipende dall'ordine degli argomenti.
  - `test_cli_profiles_lists_builtin` (via `subprocess` o chiamata a `main(argv)`).
- [ ] **Step 2: Esegui** → FAIL.
- [ ] **Step 3: Implementa.** `develop_roll`: ordina i frame → per ciascuno carica, corregge la luce, ritaglia, calcola la densità → livelli dall'intero rullino → `render_positive` → `save_outputs(out_dir / f"{stem}_originale")`. Gli avvisi vanno sia in `FrameResult.warnings` sia sulla console.
- [ ] **Step 4: Esegui** `pytest -v` (tutta la suite) → PASS.
- [ ] **Step 5: Prova su foto reali (con l'utente).** Con le foto fornite: `python -m filmengine develop foto/*.dng --profile generic_color --base foto/base.dng --out risultati/`. Atteso: nessun errore; il risultato non ha dominante arancione o ciano e il grigio appare neutro. Annota cosa non convince e tara i valori in `profiles/*.json` (non il codice).
- [ ] **Step 6: Commit** `feat: pipeline completa e CLI del prototipo`
