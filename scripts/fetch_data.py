#!/usr/bin/env python3
"""
fetch_data.py — Recupera calendario e classifica dal sito IVL USACLI.

Usa Playwright per il rendering JavaScript della SPA e salva i dati
in data/partite.json e data/classifica.json.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

load_dotenv()

# Parametri campionato
GIRONE_ID = os.getenv("IVL_GIRONE_ID", "910")
TERRITORIO_ID = os.getenv("IVL_TERRITORIO_ID", "3")
CAMPIONATO_ID = os.getenv("IVL_CAMPIONATO_ID", "342")
STAGIONE_INIZIO = os.getenv("IVL_STAGIONE_INIZIO", "2025-09-01T00:00:00.000Z")
STAGIONE_FINE = os.getenv("IVL_STAGIONE_FINE", "2026-08-31T00:00:00.000Z")
SQUADRA_MONITORATA = os.getenv("SQUADRA_MONITORATA", "Olimpia PB")

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
LOG_DIR = BASE_DIR / os.getenv("LOG_DIR", "logs")

CALENDARIO_URL = (
    f"https://ivl.usacli.it/CalendarioView"
    f"?girone_id={GIRONE_ID}"
    f"&territorio_id={TERRITORIO_ID}"
    f"&campionato_id={CAMPIONATO_ID}"
    f"&inizio_stagione={STAGIONE_INIZIO}"
    f"&fine_stagione={STAGIONE_FINE}"
    f"&societa_id=null"
    f"&squadra_id=null"
)

CLASSIFICA_URL = (
    f"https://ivl.usacli.it/classificaterritorio/{TERRITORIO_ID}"
    f"?girone_id={GIRONE_ID}"
)

TIMEOUT_MS = 30_000


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def append_log(esito: str, dettagli: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / "ultimo_aggiornamento.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{ts} | {esito} | {dettagli}\n")


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_risultato(testo: str):
    """
    Tenta di estrarre il risultato da una stringa come "3-2 (25-20, 18-25, 25-22, 22-25, 15-12)".
    Restituisce None se la stringa non contiene un risultato riconoscibile.
    """
    import re

    testo = testo.strip()
    # Pattern: "X-Y (a-b, c-d, ...)"
    m = re.match(
        r"(\d+)-(\d+)\s*\(([^)]+)\)",
        testo,
    )
    if not m:
        return None

    set_vinti_casa = int(m.group(1))
    set_vinti_ospite = int(m.group(2))
    set_scores_raw = m.group(3)

    set_casa = []
    set_ospite = []
    for coppia in set_scores_raw.split(","):
        coppia = coppia.strip()
        parti = coppia.split("-")
        if len(parti) == 2:
            try:
                set_casa.append(int(parti[0]))
                set_ospite.append(int(parti[1]))
            except ValueError:
                continue

    return {
        "set_casa": set_casa,
        "set_ospite": set_ospite,
        "set_vinti_casa": set_vinti_casa,
        "set_vinti_ospite": set_vinti_ospite,
    }


def fetch_calendario(page) -> list:
    """Recupera tutte le partite del girone dal calendario IVL."""
    log(f"Caricamento calendario: {CALENDARIO_URL}")
    page.goto(CALENDARIO_URL)

    try:
        # Attende la tabella principale del calendario
        page.wait_for_selector("table", timeout=TIMEOUT_MS)
    except PlaywrightTimeoutError:
        log("ERRORE: timeout in attesa della tabella calendario")
        return []

    # Attende che le righe siano popolate
    page.wait_for_timeout(2000)

    rows = page.query_selector_all("table tr")
    if not rows:
        log("ATTENZIONE: nessuna riga trovata nella tabella calendario")
        return []

    partite = []
    for i, row in enumerate(rows):
        cells = row.query_selector_all("td")
        if len(cells) < 10:
            continue  # header, toolbar o riga vuota

        testi = [c.inner_text().strip() for c in cells]

        # Scarta righe senza data (celle [1] deve contenere dd-mm-yyyy)
        import re as _re
        if not _re.search(r"\d{2}-\d{2}-\d{4}", testi[1] if len(testi) > 1 else ""):
            continue

        log(f"  Riga {i}: {testi}")

        # Struttura attesa (da adattare alla struttura reale del sito IVL):
        # [data_ora, squadra_casa, squadra_ospite, palestra, risultato, ...]
        try:
            partita = _parse_riga_calendario(testi, i)
            if partita:
                partite.append(partita)
        except Exception as e:
            log(f"  Errore parsing riga {i}: {e}")

    log(f"Partite trovate: {len(partite)}")
    return partite


def _parse_riga_calendario(testi: list, idx: int):
    """
    Struttura reale IVL (rilevata da ispezione):
    [0] id_partita  (es. "BA - L 135")
    [1] data_ora    (es. "Mer 08-04-2026\nOra 21:30")
    [2] vuoto
    [3] squadra_casa
    [4] vuoto
    [5] vuoto / risultato_casa (se giocata: "3")
    [6] squadra_ospite
    [7] vuoto
    [8] vuoto / risultato_ospite (se giocata: "2")
    [9] palestra\nindirizzo
    [10] vuoto
    [11] campionato
    """
    import re

    if len(testi) < 10:
        return None

    data_ora_raw = testi[1].strip()
    squadra_casa = testi[3].strip()
    squadra_ospite = testi[6].strip()
    palestra_raw = testi[9].strip()

    # Parse data: "Mer 08-04-2026\nOra 21:30" → "2026-04-08", "21:30"
    data_match = re.search(r"(\d{2}-\d{2}-\d{4})", data_ora_raw)
    ora_match = re.search(r"(\d{2}:\d{2})", data_ora_raw)

    if not data_match or not squadra_casa or not squadra_ospite:
        return None

    try:
        data_iso = datetime.strptime(data_match.group(1), "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

    ora_iso = ora_match.group(1) if ora_match else ""

    # Palestra e indirizzo separati da \n
    palestra_parti = palestra_raw.split("\n", 1)
    palestra = palestra_parti[0].strip()
    indirizzo = palestra_parti[1].strip() if len(palestra_parti) > 1 else ""

    # Risultato: se [5] e [8] sono numeri interi la partita è giocata
    # Formato alternativo: risultato completo in una cella come "3-2 (25-20, ...)"
    risultato = None
    giocata = False

    # Prova il formato "X-Y (set scores)" in qualsiasi cella
    for t in testi:
        r = parse_risultato(t)
        if r:
            risultato = r
            giocata = True
            break

    # Altrimenti controlla celle [5] e [8] come set vinti
    if not giocata:
        try:
            sv_casa = int(testi[5].strip()) if len(testi) > 5 and testi[5].strip().isdigit() else None
            sv_ospite = int(testi[8].strip()) if len(testi) > 8 and testi[8].strip().isdigit() else None
            if sv_casa is not None and sv_ospite is not None:
                risultato = {
                    "set_casa": [],
                    "set_ospite": [],
                    "set_vinti_casa": sv_casa,
                    "set_vinti_ospite": sv_ospite,
                }
                giocata = True
        except (ValueError, IndexError):
            pass

    olimpia_pb_gioca = (SQUADRA_MONITORATA.lower() in squadra_casa.lower() or
                        SQUADRA_MONITORATA.lower() in squadra_ospite.lower())
    olimpia_pb_casa = SQUADRA_MONITORATA.lower() in squadra_casa.lower()

    partita_id = f"{data_iso}_{squadra_casa}_{squadra_ospite}".replace(" ", "_").lower()

    return {
        "id": partita_id,
        "data": data_iso,
        "ora": ora_iso,
        "squadra_casa": squadra_casa,
        "squadra_ospite": squadra_ospite,
        "palestra": palestra,
        "indirizzo": indirizzo,
        "risultato": risultato,
        "olimpia_pb_gioca": olimpia_pb_gioca,
        "olimpia_pb_casa": olimpia_pb_casa,
        "giocata": giocata,
    }


def fetch_classifica(page) -> list:
    """Recupera la classifica del girone dal sito IVL."""
    log(f"Caricamento classifica: {CLASSIFICA_URL}")
    page.goto(CLASSIFICA_URL)

    try:
        page.wait_for_selector("table", timeout=TIMEOUT_MS)
    except PlaywrightTimeoutError:
        log("ERRORE: timeout in attesa della tabella classifica")
        return []

    page.wait_for_timeout(2000)

    rows = page.query_selector_all("table tr")
    if not rows:
        log("ATTENZIONE: nessuna riga trovata nella tabella classifica")
        return []

    squadre = []
    for i, row in enumerate(rows):
        cells = row.query_selector_all("td, th")
        testi = [c.inner_text().strip() for c in cells]
        log(f"  Riga classifica {i}: {testi}")

        try:
            squadra = _parse_riga_classifica(testi)
            if squadra:
                squadre.append(squadra)
        except Exception as e:
            log(f"  Errore parsing riga classifica {i}: {e}")

    log(f"Squadre in classifica: {len(squadre)}")
    return squadre


def _parse_riga_classifica(testi: list):
    """
    Struttura reale IVL classifica (rilevata da ispezione):
    [0] squadra  [1] punti  [2] G  [3] V  [4] P  [5] SV  [6] SP  [7] q_set  [8] PV  [9] PP  [10] q_pt

    Righe non-dati (header, filtri) vengono scartate perché testi[1] non è un intero.
    """
    if len(testi) < 8:
        return None

    nome = testi[0].strip()
    if not nome:
        return None

    # Scarta righe header: se testi[1] non è numerico non è una riga dati
    try:
        int(testi[1].strip())
    except ValueError:
        return None

    def to_int(s: str) -> int:
        try:
            return int(s.replace(",", "").strip())
        except ValueError:
            return 0

    def to_float(s: str) -> float:
        try:
            return float(s.replace(",", ".").strip())
        except ValueError:
            return 0.0

    return {
        "squadra": nome,
        "punti": to_int(testi[1]),
        "partite_giocate": to_int(testi[2]),
        "partite_vinte": to_int(testi[3]),
        "partite_perse": to_int(testi[4]),
        "set_vinti": to_int(testi[5]),
        "set_persi": to_int(testi[6]),
        "quoziente_set": to_float(testi[7]),
        "punti_vinti": to_int(testi[8]) if len(testi) > 8 else 0,
        "punti_persi": to_int(testi[9]) if len(testi) > 9 else 0,
        "quoziente_punti": to_float(testi[10]) if len(testi) > 10 else 0.0,
    }


def merge_partite(esistenti: list, nuove: list):
    """
    Unisce le partite esistenti con quelle nuove.
    Protegge i risultati già presenti se lo scraping restituisce dati vuoti.
    Restituisce (lista_aggiornata, nuove_aggiunte, risultati_aggiornati).
    """
    mappa = {p["id"]: p for p in esistenti}
    nuove_count = 0
    aggiornati_count = 0

    for nuova in nuove:
        pid = nuova["id"]
        if pid not in mappa:
            mappa[pid] = nuova
            nuove_count += 1
        else:
            esistente = mappa[pid]
            # Aggiorna risultato solo se il nuovo ha dati
            if nuova.get("risultato") and not esistente.get("risultato"):
                mappa[pid] = {**esistente, **nuova}
                aggiornati_count += 1
            elif not nuova.get("risultato") and esistente.get("risultato"):
                # Mantieni risultato esistente (protezione da regressioni)
                pass
            else:
                # Aggiorna metadati non-risultato
                mappa[pid] = {**mappa[pid], **{
                    k: v for k, v in nuova.items()
                    if k not in ("risultato", "giocata")
                }}

    partite_ordinate = sorted(mappa.values(), key=lambda p: (p["data"], p.get("ora", "")))
    return partite_ordinate, nuove_count, aggiornati_count


def main() -> int:
    log("=== fetch_data.py avviato ===")

    partite_esistenti = load_json(DATA_DIR / "partite.json").get("partite", [])
    nuove_partite_count = 0
    risultati_aggiornati_count = 0
    classifica_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # --- Calendario ---
        try:
            nuove_partite = fetch_calendario(page)
        except Exception as e:
            log(f"ERRORE CRITICO nel fetch calendario: {e}")
            append_log("ERRORE", f"fetch calendario: {e}")
            browser.close()
            return 1

        if not nuove_partite:
            log("ATTENZIONE: scraping calendario ha restituito 0 partite — non sovrascrivere")
        else:
            partite_merge, nuove_partite_count, risultati_aggiornati_count = merge_partite(
                partite_esistenti, nuove_partite
            )
            ts = datetime.now(timezone.utc).isoformat()
            save_json(DATA_DIR / "partite.json", {
                "partite": partite_merge,
                "ultimo_aggiornamento": ts,
            })
            log(f"partite.json aggiornato: +{nuove_partite_count} nuove, {risultati_aggiornati_count} risultati aggiornati")

        # --- Classifica ---
        try:
            classifica = fetch_classifica(page)
        except Exception as e:
            log(f"ERRORE nel fetch classifica: {e}")
            classifica = []

        if not classifica:
            log("ATTENZIONE: classifica vuota — non sovrascrivere")
        else:
            classifica_count = len(classifica)
            ts = datetime.now(timezone.utc).isoformat()
            save_json(DATA_DIR / "classifica.json", {
                "classifica": classifica,
                "ultimo_aggiornamento": ts,
            })
            log(f"classifica.json aggiornato: {classifica_count} squadre")

        browser.close()

    dettagli = (
        f"partite nuove={nuove_partite_count}, "
        f"risultati aggiornati={risultati_aggiornati_count}, "
        f"squadre classifica={classifica_count}"
    )
    append_log("OK", dettagli)
    log("=== fetch_data.py completato ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
