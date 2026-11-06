# App di sviluppo digitale della pellicola — Flusso di lavoro

*Bozza v0.1 — 6 novembre 2026. Nome dell'app da decidere.*

## Obiettivo

Un'app per smartphone che trasforma una pellicola fisica in un file digitale:
l'utente sceglie la pellicola, la inquadra con la fotocamera del telefono e
ottiene **due versioni** di ogni fotogramma:

- **Originale**: conversione fedele del negativo, senza interventi dell'AI.
  È l'immagine come l'avrebbe stampata un buon laboratorio da quella pellicola.
- **Migliorata (AI)**: la stessa immagine ripulita e migliorata dall'AI.

L'utente passa dall'una all'altra con un tocco.

## Principi

1. **L'originale non si perde mai.** Lo scatto grezzo e la versione Originale
   restano sempre salvati; la versione AI è uno strato in più, mai una sostituzione.
2. **Non distruttivo.** Ogni modifica è un insieme di parametri che si può
   cambiare o annullare in qualsiasi momento.
3. **Il carattere viene dalla pellicola.** Il "look" autentico si ottiene
   conoscendo la pellicola scelta (profilo di colore e contrasto), non con filtri finti.
4. **AI trasparente.** L'utente vede sempre il prima/dopo e può dosare l'intensità.

---

## Il flusso, passo per passo

### Passo 0 — Preparazione (fuori dall'app, guidata dall'app)

- **Fonte di luce**: un tablet o un secondo telefono con schermo bianco
  (l'app può fornire una "modalità pannello luminoso"), oppure un pannello LED.
- **Supporto**: la pellicola deve stare piatta e parallela al telefono
  (porta-negativi, vetrino o supporto stampato in 3D).
- **Pulizia**: soffiare via la polvere prima di scattare.
- Brevi schermate di tutorial alla prima apertura.

### Passo 1 — Scelta della pellicola

- **Tipo**: negativo a colori (C-41), negativo bianco e nero, diapositiva (E-6).
- **Marca e modello** da un catalogo (es. Kodak Portra 400, Ilford HP5, Fuji Superia…).
  Ogni modello porta con sé un **profilo pellicola**: colore della maschera,
  curva di contrasto, resa dei colori.
- **Formato**: 35 mm (MVP), poi 120 medio formato.
- **"Non lo so"**: l'app prova a riconoscere il tipo dalla prima inquadratura
  (colore della base, scritte sul bordo) e propone un profilo generico.
- Si lavora **per rullino**: si crea un rullino (nome, data, pellicola) e i
  fotogrammi si aggiungono in sequenza.

### Passo 2 — Inquadratura e cattura

- **Anteprima dal vivo già invertita**: l'utente vede il positivo in tempo
  reale, non il negativo arancione.
- **Guide in tempo reale**:
  - rilevamento automatico dei bordi del fotogramma;
  - indicatore di allineamento (telefono parallelo alla pellicola);
  - controllo di messa a fuoco (scatto bloccato se l'immagine è sfocata);
  - esposizione e bilanciamento del bianco **bloccati** per tutto il rullino,
    così i fotogrammi restano coerenti.
- **Calibrazione della base**: una volta per rullino si inquadra una zona di
  pellicola non esposta (tra due fotogrammi) per misurare la maschera esatta.
- **Cattura**:
  - RAW se il telefono lo supporta, altrimenti la massima qualità con
    l'elaborazione automatica del telefono il più possibile disattivata;
  - opzione **multi-scatto** (più foto unite) per ridurre il rumore;
  - scatto automatico quando il fotogramma è allineato e a fuoco, poi
    "avanza al prossimo fotogramma".

### Passo 3 — Elaborazione: versione Originale

Pipeline fissa e ripetibile, **senza AI generativa**:

1. Linearizzazione dei dati dello scatto
2. Correzione dell'illuminazione non uniforme della fonte di luce
3. Raddrizzamento prospettico e ritaglio sul fotogramma
4. Neutralizzazione della maschera usando la calibrazione della base
5. Inversione negativo → positivo (saltata per le diapositive)
6. Applicazione del profilo della pellicola scelta (curve, colore)
7. Bilanciamento automatico di esposizione e punto di bianco/nero

Risultato: la versione **Originale**, fedele e senza invenzioni.

### Passo 4 — Elaborazione: versione Migliorata (AI)

Parte dalla versione Originale e applica, ognuno attivabile e dosabile:

| Intervento AI | Cosa fa |
|---|---|
| Polvere e graffi | Individua e ricostruisce puntini, peli, graffi |
| Riduzione rumore | Rimuove il rumore del sensore del telefono, **conservando la grana** della pellicola |
| Correzione colore | Corregge dominanti e sbiadimenti (utile su negativi vecchi o mal conservati) |
| Nitidezza / super-risoluzione | Recupera dettaglio e aumenta la risoluzione |
| Recupero ombre e luci | Migliora la gamma dinamica senza appiattire l'immagine |

Ogni intervento ha un cursore d'intensità; un cursore generale "AI 0–100%"
li regola tutti insieme.

### Passo 5 — Revisione

- **Interruttore Originale ⇄ AI** e vista prima/dopo con cursore divisorio.
- Regolazioni manuali di base: esposizione, temperatura, contrasto, ritaglio, rotazione.
- **Applica a tutto il rullino**: le correzioni di un fotogramma si copiano sugli altri.

### Passo 6 — Esportazione e archivio

- Formati: JPEG o HEIC per la condivisione, TIFF a 16 bit per l'archivio.
- Si possono esportare l'Originale, la versione AI o entrambe.
- **Metadati** scritti nei file: pellicola, rullino, numero del fotogramma,
  data dello scatto (se nota), data della digitalizzazione.
- Salvataggio in galleria, in un album per rullino, e condivisione diretta.

---

## Modello dei dati

```
Rullino ─ nome, data, pellicola (profilo), formato, calibrazione base
 └─ Fotogramma ─ numero
     ├─ scatto grezzo (RAW/immagine originale del telefono)
     ├─ parametri versione Originale
     ├─ parametri versione AI (interventi + intensità)
     └─ anteprime generate
```

Le versioni finali si possono sempre rigenerare da scatto grezzo + parametri.

## Proposta di MVP (prima versione)

Per arrivare presto a qualcosa di funzionante:

- negativo a colori e bianco e nero, **solo 35 mm**;
- catalogo di 10–15 pellicole popolari più un profilo generico;
- cattura guidata con rilevamento dei bordi e calibrazione della base;
- versione Originale completa;
- versione AI con **due interventi**: polvere/graffi e correzione colore;
- esportazione JPEG e TIFF con metadati.

Rimandati: diapositive, medio formato, super-risoluzione, riconoscimento
automatico della pellicola, scatto automatico.

## Decisioni ancora aperte

1. **Piattaforma**: ✅ iOS e Android, architettura **ibrida**:
   - interfaccia in Flutter, unica per i due sistemi;
   - modulo fotocamera nativo per sistema (AVFoundation su iOS, Camera2 su Android);
   - motore di conversione condiviso in C++ (identico su iOS e Android);
   - modelli AI richiamati dal codice nativo.
2. **Dove gira l'AI**: ✅ **misto**. L'AI essenziale gira sul telefono
   (privata, offline, senza costi); più avanti si aggiunge un modulo "AI Pro"
   nel cloud, opzionale e attivato solo su richiesta dell'utente.
   La prima versione (MVP) usa solo l'AI sul telefono.
3. **Destinazione**: uso personale o prodotto da pubblicare, e con quale modello
   di prezzo.
4. **Nome e identità** dell'app.
