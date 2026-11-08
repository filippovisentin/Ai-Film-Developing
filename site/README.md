# Sito pubblico

Pubblicato con GitHub Pages: **https://filippovisentin.github.io/Ai-Film-Developing/**
(workflow `.github/workflows/pages.yml`, a ogni push su `main` che tocca `site/` o `profiles/`).

Tre pagine statiche: **Progetto** (`/`), **Galleria** (`/galleria`) e **Applicativo** (`/app`).
L'applicativo esegue nel browser un port JavaScript di `filmengine` (`src/engine/`): le foto non
lasciano il dispositivo. Modalità: Originale, Migliorata e Ingrandimento AI ×2/×4 (Real-ESRGAN con
ONNX Runtime Web). Il Restauro AI resta nella versione locale, perché i pesi non sono pubblicati.

## Comandi

```bash
cd site
npm ci
npm run build      # crea dist/ (scarica e verifica il modello AI la prima volta)
npm test           # confronta il motore JS con quello Python (servono i dati qui sotto)
npm run serve      # anteprima locale con le stesse regole di Cloudflare: http://localhost:8788
npm run deploy     # build + pubblicazione con wrangler (serve "npx wrangler login" una volta)
```

## Landing e confronto colore

La home presenta un confronto negativo/positivo animato, rivelazioni allo scorrimento,
una piccola parallasse della montatura e un comando per fermare il movimento. Rispetta
`prefers-reduced-motion`; il contenuto resta leggibile anche senza JavaScript.

In galleria, `#colore` confronta tredici JPEG già inclusi nel repository. Per rigenerarli:

```bash
cd site
npm ci
npm run compare:colors
npm test
npm run build
```

Ogni coppia usa lo stesso JPEG da telefono simulato, lo stesso ritaglio, la stessa
calibrazione automatica e nessuna pulizia/AI. Il nuovo file `data/color-comparison.json`
registra gli input e i profili. Non sono le fixture RAW private: le metriche storiche
della galleria **non** misurano questi confronti.

Il motore mantiene `colorMode: "legacy"` come default. L'opzione `"natural"` in
`developFrame`/`renderPositive` ricostruisce RGB dalla densità, applica la matrice colore
e usa una sola curva sulla luminanza; i rapporti RGB vengono conservati fino al gamut
mapping. Il nome è interno: nell'interfaccia è indicata come **sperimentale**, perché
può conservare anche dominanti di acquisizione e richiede una base attendibile.
`frame_balance` e i livelli RGB del rullino appartengono al renderer legacy e non vengono
riutilizzati dal renderer sperimentale, che lavora per fotogramma. Il bianco e nero e
le diapositive continuano a usare il percorso legacy.

La foto separata del bordo è trattata come primo piano: non viene corretta con il campo
luce del negativo. Per una base ripresa con la stessa inquadratura del negativo, usare
esplicitamente `baseFraming: "negative"` (anche nelle fixture del simulatore).
La decodifica nel browser richiede la conversione colore predefinita e una canvas sRGB;
la resa dei file con profili ICC va verificata anche sui browser/dispositivi di destinazione.

I test colore sintetici e quello sulla calibrazione sono eseguibili senza dataset privato.
I test fotografici di parità Python e quello AI sono indicati come saltati se mancano le
fixture; un esito verde dei soli test pubblici non certifica la fedeltà sui negativi reali.

## In alternativa: Cloudflare Pages

**Collegato a GitHub (si ripubblica a ogni push):** Cloudflare → Workers & Pages → Create →
Pages → Connect to Git → `Ai-Film-Developing`, poi:

| Impostazione | Valore |
|---|---|
| Production branch | `main` |
| Root directory | `site` |
| Build command | `npm ci && npm run build` |
| Build output directory | `dist` |
| Variabile d'ambiente | `NODE_VERSION` = `22` |

**Dal computer:** `npx wrangler login`, poi `npm run deploy` (crea il progetto
`ai-film-developing` al primo invio; indirizzo `https://ai-film-developing.pages.dev`).

## Da dove vengono i file

| Cartella | Origine |
|---|---|
| `src/engine/` | port di `filmengine/` (calibrazione, geometria, inversione, Migliorata, AI) |
| `src/img/g/`, `src/data/gallery.json` | `scripts/build_gallery_assets.py` da `web/img` e `testdata/` (BlueNeg, Copyrighted by Tien-Tsin Wong) |
| `src/img/esempio/` | scatto di esempio dell'applicativo, simulato dallo stesso script |
| `dist/vendor/` | OpenCV.js 4.10 (Apache 2.0) e ONNX Runtime Web 1.20.1 (MIT), da `node_modules` |
| `dist/models/` | Real-ESRGAN General x4v3, Qualcomm AI Hub (BSD-3-Clause), verificato con SHA-256 |

## Verifica del motore JavaScript

```bash
.venv/Scripts/python site/scripts/export_fixtures.py   # dalla radice: servono testdata/ e models/
cd site && npm test
```

Ultimo risultato su tre pellicole (Fuji 100, Kodak Gold 100, Portra 400): scarto medio rispetto a
Python 0,03–0,07 livelli su 255 per l'Originale, 0,04–0,11 per la Migliorata, ~0 per l'AI.

Limiti nel browser: il negativo viene ridotto a 3000 px sul lato lungo e l'AI lavora su una
versione da 1024 px (risultato fino a 4096 px); i DNG non sono letti (servono JPEG, PNG o HEIC in Safari).
