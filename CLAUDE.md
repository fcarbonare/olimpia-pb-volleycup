# CLAUDE.md — Olimpia PB · Volleycup Basic Tracker

Questo file è il punto di riferimento principale per Claude Code
in tutti i repository e script di questo progetto.

---

## Panoramica del progetto

Raccogliere, aggiornare e pubblicare i **risultati e il calendario** della squadra
**Olimpia PB Basic** (categoria Mista) nel campionato **Volleycup Basic — Girone L (910)**,
organizzato da US ACLI Milano (territorio 3, campionato 342, stagione 2025-26).

### Obiettivi principali

| # | Obiettivo |
|---|-----------|
| 1 | Recuperare automaticamente i risultati delle partite via API JSON IVL USACLI |
| 2 | Aggiornare la classifica locale (basata sui set vinti, non sulle partite) |
| 3 | Pubblicare una pagina web pubblica su **GitHub Pages** (in italiano) |
| 4 | Eseguire aggiornamenti giornalieri automatici tramite **GitHub Actions** |

### Regole del campionato (IMPORTANTE)

- Il campionato è **Mista Senior**: uomini e donne giocano insieme.
- La classifica **non si basa sulle vittorie di partita** ma sul **totale dei set vinti**.
- Ogni incontro è composto da **5 set** (tutti e 5 vengono sempre giocati).
- La posizione in classifica dipende esclusivamente dal **numero cumulativo di set vinti**.
- Non esistono set "decisivi" o vittorie per forfait nel computo: contano solo i punteggi reali.

---

## Struttura del repository

```
olimpia-pb-volleycup/
├── CLAUDE.md                  ← questo file
├── data/
│   ├── partite.json           ← tutte le partite con risultati (fonte di verità)
│   ├── classifica.json        ← classifica aggiornata
│   └── squadre.json           ← elenco squadre del girone
├── scripts/
│   ├── fetch_data.py          ← fetch dati via API JSON IVL
│   ├── update_classifica.py   ← ricalcola la classifica dai dati grezzi
│   └── build_site.py          ← genera i file HTML statici per GitHub Pages
├── docs/                      ← output GitHub Pages (pubblicato da /docs su main)
│   ├── index.html             ← homepage (classifica top 5 + prossima/ultima partita)
│   ├── calendario.html        ← tutte le partite del girone
│   ├── classifica.html        ← classifica completa del girone
│   └── assets/
│       ├── style.css          ← stile rosso/nero/bianco (colori Dobermanns)
│       └── logo.png           ← logo Olimpia PB Dobermanns
├── .claude/
│   └── settings.json          ← hook pre-commit: git pull --rebase automatico
├── .github/
│   └── workflows/
│       └── update.yml         ← GitHub Actions: aggiornamento giornaliero 07:00 UTC
├── .env.example               ← template variabili d'ambiente
├── requirements.txt           ← requests, python-dotenv
└── .gitignore
```

---

## Fonti dati (API JSON)

Il sito IVL espone endpoint JSON che si chiamano direttamente con `requests` — **niente browser headless**.

### Partite (calendario + risultati)

```
GET https://ivl.usacli.it/PartiteData
  ?girone_id=910
  &territorio_id=3
  &campionato_id=342
  &inizio_stagione=2025-09-01T00:00:00.000Z
  &fine_stagione=2026-08-31T00:00:00.000Z
  &societa_id=null
  &squadra_id=null
  &pubblicato=1
  &offset=0
  &limit=500
```

Risposta: `{ "rows": [...], "total": N }` — una riga per partita.

Campi rilevanti per riga:

| Campo API | Significato |
|-----------|-------------|
| `data_orario` | Data e ora (`YYYY-MM-DD HH:MM:SS`) |
| `squadra_casa_name` | Nome squadra casa |
| `squadra_ospite_name` | Nome squadra ospite |
| `palestra1_name` | Nome palestra |
| `Palestra_indirizzo` | Indirizzo completo |
| `ris_set_casa` / `ris_set_ospite` | Set vinti (null se non giocata) |
| `ris_punti1set_casa` … `ris_punti5set_casa` | Punti per set (casa) |
| `ris_punti1set_ospite` … `ris_punti5set_ospite` | Punti per set (ospite) |
| `npartita_custom` | Codice partita (es. `BA - L 135`) |

### Classifica

```
GET https://ivl.usacli.it/Classifica/910
  ?_a=
  &inizio_stagione=2025-09-01T00:00:00.000Z
  &fine_stagione=2026-08-31T00:00:00.000Z
```

Risposta: array di oggetti squadra.

| Campo API | Significato |
|-----------|-------------|
| `name` | Nome squadra |
| `Punteggio` | Punti classifica IVL |
| `PartiteGiocate` | Partite giocate |
| `PartiteVinte` | Partite vinte |
| `SetVinti` / `SetPersi` | Set vinti/persi |
| `PuntiVinti` / `PuntiPersi` | Punti (palloni) vinti/persi |

### Schema `partite.json`

```json
{
  "partite": [
    {
      "id": "2026-04-08_pinco_pallino_volley_basic_olimpia_pb_basic",
      "ivl_id": 32281,
      "npartita": "BA - L 135",
      "data": "2026-04-08",
      "ora": "21:30",
      "squadra_casa": "PINCO PALLINO VOLLEY Basic",
      "squadra_ospite": "OLIMPIA PB Basic",
      "palestra": "Palestra Istituto ALEXIS CARREL",
      "indirizzo": "Via Inganni 12 MILANO",
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
  "ultimo_aggiornamento": "2026-04-08T11:25:40.870492+00:00"
}
```

> `risultato` è `null` se la partita non è ancora stata giocata.

---

## Script principali

### `scripts/fetch_data.py`

**Scopo**: Recupera partite e classifica aggiornate via API JSON IVL.

**Comportamento**:
1. `GET /PartiteData` con `limit=500` — recupera tutte le partite in una chiamata.
2. `GET /Classifica/910` — recupera la classifica ufficiale IVL.
3. Fa merge delle partite nuove con quelle esistenti (protezione da regressioni: non sovrascrive risultati già presenti se il nuovo fetch li restituisce vuoti).
4. Aggiorna `data/partite.json` e `data/classifica.json`.
5. Appende una riga a `logs/ultimo_aggiornamento.log`.

**Dipendenze**: `requests`, `python-dotenv`

```bash
python3 scripts/fetch_data.py
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

```bash
python3 scripts/update_classifica.py
```

---

### `scripts/build_site.py`

**Scopo**: Genera i file HTML statici nella cartella `docs/`.

| File | Contenuto |
|------|-----------|
| `index.html` | Classifica top 5 + prossima partita Olimpia PB + ultima con risultato |
| `calendario.html` | Tutte le partite del girone ordinate per data |
| `classifica.html` | Classifica completa con tutti i dettagli |

**Requisiti UI/UX**:
- Testo in **italiano**. Formato data: `gg/mm/aaaa`. Formato ora: `HH:MM`.
- Colori squadra: **rosso, bianco, nero** (Dobermanns).
- Le partite di Olimpia PB Basic sono **evidenziate** (sfondo rosso chiaro, testo rosso).
- Sito **responsive**, ottimizzato per smartphone.
- HTML + CSS puro, nessun framework JS.

```bash
python3 scripts/build_site.py
```

---

## GitHub Actions

File: `.github/workflows/update.yml`
- Schedule: **ogni giorno alle 07:00 UTC** (09:00 ora italiana)
- Trigger manuale disponibile da GitHub UI (`workflow_dispatch`)
- Dipendenze: `pip install requests python-dotenv` (niente browser)
- Passi: fetch → update classifica → build site → commit & push `data/` e `docs/`
- Sito live: **https://fcarbonare.github.io/olimpia-pb-volleycup/**

---

## GitHub Pages

- Configurato su branch `main`, cartella `/docs`.
- URL: `https://fcarbonare.github.io/olimpia-pb-volleycup/`

---

## Claude Code — hook pre-commit

Configurato in `.claude/settings.json` (PreToolUse su `git commit`):

```bash
git fetch origin main && git rebase --autostash origin/main
```

Previene conflitti con i commit automatici di GitHub Actions sincronizzando il branch locale prima di ogni commit.

---

## Convenzioni di codice

- **Linguaggio**: Python 3.12+
- **Dipendenze**: `requests`, `python-dotenv` (niente Playwright, niente framework)
- **Commit message**: in italiano, formato `tipo: descrizione breve`
  - `fix:` — correzione bug
  - `feat:` — nuova funzionalità
  - `data:` — aggiornamento dati/risultati
  - `chore:` — manutenzione, config
- **Nessun segreto nel codice**: usare `.env` (mai committare `.env`)

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
SITE_DIR=docs
LOG_DIR=logs
```

---

## Linee guida per Claude

1. **La classifica si basa sui set, non sulle vittorie**: ogni partita ha sempre 5 set,
   la posizione dipende dal totale dei set vinti durante la stagione.

2. **Usare sempre le API JSON IVL**: `GET /PartiteData` e `GET /Classifica/910`
   con `requests`. Non usare Playwright o scraping HTML — gli endpoint JSON
   restituiscono dati strutturati completi.

3. **Non perdere dati esistenti**: se il fetch restituisce 0 partite, è un errore —
   non sovrascrivere `partite.json`.

4. **Output in `docs/`**: il sito statico va in `docs/`, non in `site/`.
   GitHub Pages è configurato su `/docs` del branch `main`.

5. **Evidenziare sempre Olimpia PB Basic**: righe evidenziate in rosso chiaro
   in calendario e classifica, nome in rosso.

6. **Commit: sincronizzare prima**: l'hook pre-commit fa `git fetch && git rebase`
   automaticamente. In caso di conflitti, risolvere prima di riprovare.

7. **Log degli aggiornamenti**: ogni script appende a `logs/ultimo_aggiornamento.log`
   (la cartella `logs/` è in `.gitignore`).

---

## Stato del progetto

| Componente | Stato |
|------------|-------|
| `fetch_data.py` (API JSON) | ✅ completato |
| `update_classifica.py` | ✅ completato |
| `build_site.py` | ✅ completato |
| Sito GitHub Pages | ✅ live su fcarbonare.github.io/olimpia-pb-volleycup |
| GitHub Actions (aggiornamento giornaliero) | ✅ attivo |
| Hook pre-commit anti-conflitti | ✅ configurato |

---

*Aggiornato: aprile 2026 — Aggiornare questo file se cambiano i parametri
del campionato, la struttura dei dati o l'architettura del progetto.*
