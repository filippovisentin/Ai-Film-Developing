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
