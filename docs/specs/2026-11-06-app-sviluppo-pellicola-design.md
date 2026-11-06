# App di sviluppo digitale della pellicola — Specifica di progetto

*v1.0 — 6 novembre 2026. Basata su [flusso-di-lavoro.md](../../flusso-di-lavoro.md).*

## 1. Obiettivo e decisioni prese

App per smartphone (iOS e Android) che digitalizza la pellicola fisica usando la
fotocamera del telefono e una fonte di luce. Per ogni fotogramma produce:

- **Originale**: conversione fedele, deterministica, senza AI generativa;
- **Migliorata (AI)**: l'Originale migliorata dall'AI, con intensità regolabile.

| Decisione | Scelta |
|---|---|
| Destinazione | Prodotto da pubblicare (ipotesi da confermare) |
| Piattaforme | iOS e Android |
| Architettura | Ibrida: UI Flutter, fotocamera nativa, motore C++ condiviso |
| AI | Mista: sul telefono nell'MVP; "AI Pro" nel cloud in seguito, su richiesta |

## 2. Componenti

1. **Interfaccia (Flutter)**: schermate, catalogo pellicole, rullini, revisione,
   esportazione. Non elabora immagini.
2. **Modulo fotocamera (nativo)**: AVFoundation su iOS, Camera2 su Android.
   Interfaccia comune: `avviaAnteprima`, `bloccaEsposizione`, `scatta`, `scattoMultiplo`.
3. **Motore di conversione (C++)**: scatto grezzo + profilo + calibrazione →
   Originale. Contiene anche una versione veloce per l'anteprima dal vivo.
4. **Modulo AI**: Originale + intensità → Migliorata. Un modello per intervento.
5. **Archivio**: rullini, fotogrammi, scatti grezzi, parametri; rigenera le versioni finali.

Percorso: fotocamera → grezzo → archivio → motore → Originale → AI → Migliorata → UI.

## 3. Motore di conversione

Ingressi: scatto grezzo, profilo della pellicola, calibrazione del rullino
(colore della base + "foto della luce").

1. Linearizzazione (RAW preciso; senza RAW si annulla la curva del telefono, con avviso)
2. Correzione della luce non uniforme (divisione per la "foto della luce")
3. Geometria: rilevamento dei 4 angoli, raddrizzamento, ritaglio (modificabile a mano)
4. Neutralizzazione della maschera: divisione per canale per il colore della base
5. Inversione in densità (log), saltata per le diapositive
6. Curve caratteristiche e matrice di colore del profilo della pellicola
7. Bilanciamento di nero, bianco ed esposizione calcolato **sul rullino intero**

**Profilo della pellicola**: un file di dati (JSON) con tipo, colore tipico della
maschera, curve per canale e matrice di colore. Il profilo generico stima le curve
dall'immagine.

**Requisito**: risultato deterministico, identico su ogni dispositivo.

## 4. Cattura guidata

- Preparazione del rullino: "foto della luce" → calibrazione della base →
  blocco di esposizione, bilanciamento del bianco e messa a fuoco.
- Indicatori in tempo reale: fotogramma trovato, allineamento, messa a fuoco,
  esposizione. Lo scatto si abilita quando sono tutti verdi.
- Scatto RAW o in qualità massima, con l'elaborazione automatica del telefono
  disattivata; multi-scatto (3–5) opzionale.
- Dopo lo scatto: anteprima dell'Originale, poi "avanti" o "riscatta".
- Gestione dei problemi: niente RAW, pellicola non piatta, riflessi, fotogramma
  non trovato (ritaglio manuale), permesso della fotocamera negato.

## 5. Modulo AI

- **MVP, sul telefono**: (a) polvere e graffi: rilevamento dei difetti +
  ricostruzione locale; (b) correzione del colore: stima delle dominanti e degli sbiadimenti.
- In seguito: riduzione del rumore che conserva la grana, nitidezza e
  super-risoluzione, recupero di ombre e luci.
- Runtime: Core ML su iOS, TensorFlow Lite o ONNX Runtime su Android, con modelli
  convertiti dalla stessa fonte.
- Ogni intervento ha un cursore 0–100%; un cursore generale li regola tutti.
- L'AI non modifica mai l'Originale: produce uno strato separato.
- "AI Pro" (cloud, dopo l'MVP): stessa interfaccia del modulo; invio solo su
  azione esplicita dell'utente, con informativa privacy (GDPR).

## 6. Archivio ed esportazione

- Modello: Rullino (nome, data, profilo, formato, calibrazione) → Fotogramma
  (numero, grezzo, parametri Originale, parametri AI, anteprime).
- Tutto in locale; le versioni finali si rigenerano da grezzo + parametri.
- Esportazione: JPEG o HEIC, TIFF a 16 bit; Originale, AI o entrambe; metadati
  (pellicola, rullino, fotogramma, date); album per rullino.

## 7. Verifica della qualità

- **Set di riferimento**: negativi reali (colore e B/N) fotografati con più
  telefoni, con le scansioni di laboratorio come confronto.
- **Test del motore**: dati fissi → immagine attesa (determinismo e regressioni);
  misure di differenza di colore (ΔE) rispetto alla scansione di laboratorio.
- **Test AI**: l'AI non deve peggiorare l'Originale (metriche + revisione visiva);
  verifica che la grana sopravviva alla riduzione del rumore.
- **Test sui dispositivi**: almeno un iPhone e due Android di fasce diverse.

## 8. Fasi di sviluppo

1. **Prototipo del motore** (sul PC): pipeline di conversione su foto di negativi
   fatte con il telefono. Prova che la qualità dell'Originale è all'altezza.
2. **Scheletro dell'app**: Flutter + fotocamera nativa + motore C++ collegato.
3. **Cattura guidata** completa.
4. **AI sul telefono** (polvere, colore).
5. **Archivio, esportazione, catalogo pellicole** → MVP.
6. Dopo l'MVP: diapositive, medio formato, AI Pro, scatto automatico.

## 9. Fuori dall'MVP

Diapositive, medio formato (120), super-risoluzione, riconoscimento automatico
della pellicola, scatto automatico, AI Pro nel cloud.
