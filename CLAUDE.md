# CLAUDE.md — Olimpia PB · Volleycup Basic Tracker

Questo file è il punto di riferimento principale per Claude Code e Claude Cowork
in tutti i repository e script di questo progetto.

---

## Panoramica del progetto

Raccogliere, aggiornare e pubblicare i **risultati e il calendario** della squadra
**Olimpia PB** (categoria Mista) nel campionato **Volleycup Basic — Girone 910**,
organizzato da US ACLI Milano (territorio 3, campionato 342, stagione 2025-26).

### Obiettivi principali

| # | Obiettivo |
|---|-----------|
| 1 | Recuperare automaticamente i risultati delle partite dal sito IVL USACLI |
| 2 | Aggiornare la classifica locale (basata sui set vinti, non sulle partite) |
| 3 | Pubblicare una pagina web pubblica su **GitHub Pages** (in italiano) |
| 4 | Eseguire aggiornamenti giornalieri tramite **Claude Cowork** |

### Regole del campionato (IMPORTANTE)

- Il campionato è **Mista Senior**: uomini e donne giocano insieme.
- La classifica **non si basa sulle vittorie di partita** ma sul **totale dei set vinti**.
- Ogni incontro è composto da **5 set** (tutti e 5 vengono sempre giocati).
- La posizione in classifica dipende esclusivamente dal **numero cumulativo di set vinti**.
- Non esistono set "decisivi" o vittorie per forfait nel computo: contano solo i punteggi reali.

---

## Struttura dei repository

```
olimpia-pb-volleycup/          ← repository principale (questo)
├── CLAUDE.md                  ← questo file
├── data/
│   ├── partite.json           ← tutte le partite con risultati (fonte di verità)
│   ├── classifica.json        ← classifica aggiornata
│   └── squadre.json           ← elenco squadre del girone
├── scripts/
│   ├── fetch_data.py          ← scraping dal sito IVL (usa Playwright)
│   ├── update_classifica.py   ← ricalcola la classifica dai dati grezzi
│   ├── build_site.py          ← genera i file HTML statici per GitHub Pages
│   └── cowork_daily.md        ← istruzioni per il task Cowork giornaliero
├── site/                      ← output GitHub Pages (pubblicato su /docs o branch gh-pages)
│   ├── index.html             ← homepage (classifica + prossima partita)
│   ├── calendario.html        ← tutte le partite passate e future
│   ├── classifica.html        ← classifica completa del girone
│   └── assets/
│       ├── style.css
│       └── logo.png
├── .github/
│   └── workflows/
│       └── update.yml         ← GitHub Actions: aggiornamento giornaliero automatico
└── README.md
```

> **Multi-repo**: Se in futuro si separa il sito dalla logica di scraping,
> creare `olimpia-pb-site` (solo GitHub Pages) e `olimpia-pb-scripts`
> (solo automazione). Questo CLAUDE.md rimane nel repo principale e va
> copiato/linkato negli altri.

---

## Fonti dati

### Calendario e risultati

```
URL: https://ivl.usacli.it/CalendarioView
Parametri:
  girone_id=910
  territorio_id=3
  campionato_id=342
  inizio_stagione=2025-09-01T00:00:00.000Z
  fine_stagione=2026-08-31T00:00:00.000Z
  societa_id=null
  squadra_id=null
```

### Classifica

```
URL: https://ivl.usacli.it/classificaterritorio/3
Parametri:
  girone_id=910
```

> ⚠️ **Attenzione**: Il sito IVL è un'applicazione a pagina singola (SPA) che
> carica i dati tramite JavaScript. **Non è sufficiente un semplice HTTP GET.**
> Usare sempre **Playwright** (Python) per il rendering completo della pagina
> prima di estrarre i dati.

### Colonne della classifica (struttura attesa)

| Campo | Descrizione |
|-------|-------------|
| `squadra` | Nome della squadra |
| `punti` | Punti classifica (calcolati dal sistema IVL) |
| `partite_giocate` | Partite totali giocate (G) |
| `partite_vinte` | Partite vinte (V) |
| `partite_perse` | Partite perse (P) |
| `set_vinti` | **Set vinti — campo principale per l'ordinamento** |
| `set_persi` | Set persi |
| `quoziente_set` | Rapporto set V/P |
| `punti_vinti` | Punti (palloni) vinti |
| `punti_persi` | Punti (palloni) persi |
| `quoziente_punti` | Rapporto punti V/P |

### Schema `partite.json`

```json
{
  "partite": [
    {
      "id": "string",
      "data": "YYYY-MM-DD",
      "ora": "HH:MM",
      "squadra_casa": "string",
      "squadra_ospite": "string",
      "palestra": "string",
      "indirizzo": "string",
      "risultato": {
        "set_casa": [25, 18, 25, 22, 15],
        "set_ospite": [20, 25, 20, 25, 12],
        "set_vinti_casa": 3,
        "set_vinti_ospite": 2
      },
      "olimpia_pb_gioca": true,
      "olimpia_pb_casa": false,
      "giocata": true
    }
  ],
  "ultimo_aggiornamento": "ISO8601"
}
```

> `risultato` è `null` se la partita non è ancora stata giocata.
> `olimpia_pb_gioca` è `true` quando una delle due squadre è Olimpia PB.

---

## Script principali

### `scripts/fetch_data.py`

**Scopo**: Recupera il calendario e la classifica aggiornati dal sito IVL USACLI.

**Comportamento atteso**:
1. Apre il browser headless con Playwright.
2. Naviga su entrambi gli URL (calendario + classifica).
3. Attende che la tabella dati sia visibile nel DOM.
4. Estrae tutte le righe e aggiorna `data/partite.json` e `data/classifica.json`.
5. Non sovrascrive i risultati già presenti se il sito li mostra vuoti (protezione da regressioni).
6. Stampa un riepilogo: quante partite nuove, quanti risultati aggiornati.

**Dipendenze**:
```
playwright
python-dotenv
```

**Esecuzione**:
```bash
python scripts/fetch_data.py
```

---

### `scripts/update_classifica.py`

**Scopo**: Ricalcola la classifica locale da `data/partite.json` come verifica
indipendente rispetto alla classifica ufficiale IVL.

**Logica di ordinamento** (in ordine di priorità):
1. Set vinti totali (DESC) — **criterio principale**
2. Quoziente set (set vinti / set persi) (DESC)
3. Quoziente punti (punti vinti / punti persi) (DESC)
4. Nome squadra (ASC) — spareggio alfabetico

**Output**: aggiorna `data/classifica.json` con la classifica ricalcolata.

---

### `scripts/build_site.py`

**Scopo**: Genera tutti i file HTML statici nella cartella `site/`.

**Pagine generate**:

| File | Contenuto |
|------|-----------|
| `index.html` | Classifica sintetica (top 5) + prossima partita di Olimpia PB + ultima partita con risultato |
| `calendario.html` | Tutte le partite del girone, ordinate per data, con evidenza delle partite di Olimpia PB |
| `classifica.html` | Classifica completa del girone con tutti i dettagli |

**Requisiti UI/UX**:
- Tutto il testo è in **italiano**.
- Le partite di Olimpia PB sono **evidenziate visivamente** (sfondo colorato, bordo, badge).
- Le partite future mostrano data, ora e palestra.
- Le partite passate mostrano il risultato set per set (es. `3-2 (25-20, 18-25, 25-22, 22-25, 15-12)`).
- Il sito è **responsive** (funziona bene su smartphone).
- In fondo a ogni pagina: data e ora dell'ultimo aggiornamento.
- Nessuna dipendenza da framework JavaScript pesanti: HTML + CSS puro, al massimo vanilla JS.

---

### `scripts/cowork_daily.md`

Questo file contiene le istruzioni per il **task Claude Cowork** che esegue
l'aggiornamento giornaliero. Claude Cowork leggerà questo file per sapere
cosa fare.

**Contenuto di `cowork_daily.md`**:

```markdown
# Task: Aggiornamento giornaliero Olimpia PB

## Quando eseguire
Ogni giorno, preferibilmente la mattina (08:00 ora italiana).

## Passi

1. Apri il terminale nel repository `olimpia-pb-volleycup`.
2. Esegui: `python scripts/fetch_data.py`
3. Controlla l'output: se ci sono errori, annotali e ferma il task.
4. Esegui: `python scripts/update_classifica.py`
5. Esegui: `python scripts/build_site.py`
6. Fai commit e push dei file modificati:
   ```
   git add data/ site/
   git commit -m "aggiornamento automatico: $(date '+%Y-%m-%d')"
   git push
   ```
7. Verifica che GitHub Pages pubblichi correttamente (attendi 1-2 minuti).

## In caso di errore
- Se lo scraping fallisce (timeout, sito non raggiungibile), non fare commit.
- Se i dati sembrano anomali (es. classifica vuota), non sovrascrivere.
- Annota l'errore nel file `logs/ultimo_aggiornamento.log`.
```

---

## GitHub Actions (automazione alternativa/complementare)

File: `.github/workflows/update.yml`

```yaml
name: Aggiornamento giornaliero Olimpia PB

on:
  schedule:
    - cron: '0 7 * * *'   # ogni giorno alle 07:00 UTC (09:00 ora italiana)
  workflow_dispatch:        # esecuzione manuale dalla UI GitHub

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Installa dipendenze
        run: |
          pip install playwright python-dotenv
          playwright install chromium
      - name: Recupera dati
        run: python scripts/fetch_data.py
      - name: Aggiorna classifica
        run: python scripts/update_classifica.py
      - name: Genera sito
        run: python scripts/build_site.py
      - name: Commit e push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ site/
          git diff --staged --quiet || git commit -m "aggiornamento: $(date '+%Y-%m-%d')"
          git push
```

---

## GitHub Pages

- Configurare GitHub Pages per pubblicare dalla cartella `site/` del branch `main`
  (oppure da un branch dedicato `gh-pages`).
- L'URL del sito sarà del tipo: `https://<username>.github.io/olimpia-pb-volleycup/`
- Non committare mai file generati automaticamente nel branch `main` se si usa
  il branch `gh-pages`; in quel caso il workflow fa push direttamente sul branch
  corretto.

---

## Convenzioni di codice

- **Linguaggio principale**: Python 3.12+
- **Formattazione**: `black` + `isort`
- **Linting**: `ruff`
- **Commit message**: in italiano, formato `tipo: descrizione breve`
  - Es: `fix: correzione estrazione set dalla tabella IVL`
  - Es: `feat: aggiunta pagina calendario`
  - Es: `data: aggiornamento risultati giornata 12`
- **Nessun segreto nel codice**: usare `.env` per variabili d'ambiente (mai
  committare `.env`).

---

## Variabili d'ambiente (`.env`)

```ini
# Parametri IVL
IVL_GIRONE_ID=910
IVL_TERRITORIO_ID=3
IVL_CAMPIONATO_ID=342
IVL_STAGIONE_INIZIO=2025-09-01T00:00:00.000Z
IVL_STAGIONE_FINE=2026-08-31T00:00:00.000Z

# Squadra da monitorare
SQUADRA_MONITORATA=Olimpia PB Basic

# Percorsi output
DATA_DIR=data
SITE_DIR=site
LOG_DIR=logs
```

---

## Linee guida per Claude

Quando lavori su questo progetto, tieni sempre presente:

1. **La classifica si basa sui set, non sulle vittorie**: non confonderti con i
   campionati di volley standard. Ogni partita ha sempre 5 set e la posizione
   dipende dal totale dei set vinti durante la stagione.

2. **Il sito IVL richiede rendering JavaScript**: non usare `requests` o `httpx`
   per estrarre i dati dalla tabella. Usa sempre Playwright con attesa esplicita
   sul selettore della tabella.

3. **Non perdere dati esistenti**: prima di sovrascrivere `partite.json`,
   verifica che i nuovi dati siano completi. Se lo scraping restituisce 0 partite,
   è un errore — non sovrascrivere.

4. **Tutte le pagine web in italiano**: label, intestazioni, date, messaggi di
   errore — tutto in italiano. Formato data: `gg/mm/aaaa`. Formato ora: `HH:MM`.

5. **Evidenziare sempre Olimpia PB**: in qualsiasi pagina che elenca partite o
   classifiche, le righe di Olimpia PB devono essere visivamente distinte.

6. **Semplicità del sito**: il sito è statico, per uso amatoriale, visto
   principalmente da smartphone. Priorità a leggibilità e velocità di caricamento.

7. **Log degli aggiornamenti**: ogni esecuzione degli script deve appendere
   una riga a `logs/ultimo_aggiornamento.log` con timestamp, esito e numero
   di record aggiornati.

---

## Stato del progetto

| Componente | Stato |
|------------|-------|
| `fetch_data.py` | 🔲 da implementare |
| `update_classifica.py` | 🔲 da implementare |
| `build_site.py` | 🔲 da implementare |
| Sito GitHub Pages | 🔲 da configurare |
| GitHub Actions workflow | 🔲 da configurare |
| Task Claude Cowork | 🔲 da configurare |

Aggiorna questa tabella man mano che i componenti vengono completati.

---

*Generato il: aprile 2026 — Aggiornare questo file se cambiano i parametri
del campionato, la struttura dei dati o l'architettura del progetto.*