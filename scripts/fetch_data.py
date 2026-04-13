#!/usr/bin/env python3
"""
fetch_data.py — Recupera calendario e classifica dal sito IVL USACLI via API JSON.

Endpoint:
  Partite:   GET https://ivl.usacli.it/PartiteData?...
  Classifica: GET https://ivl.usacli.it/Classifica/910?...
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# Parametri campionato
GIRONE_ID       = os.getenv("IVL_GIRONE_ID", "910")
TERRITORIO_ID   = os.getenv("IVL_TERRITORIO_ID", "3")
CAMPIONATO_ID   = os.getenv("IVL_CAMPIONATO_ID", "342")
STAGIONE_INIZIO = os.getenv("IVL_STAGIONE_INIZIO", "2025-09-01T00:00:00.000Z")
STAGIONE_FINE   = os.getenv("IVL_STAGIONE_FINE",   "2026-08-31T00:00:00.000Z")
SQUADRA_MONITORATA = os.getenv("SQUADRA_MONITORATA", "Olimpia PB")

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
LOG_DIR  = BASE_DIR / os.getenv("LOG_DIR",  "logs")

PARTITE_URL = (
    f"https://ivl.usacli.it/PartiteData"
    f"?girone_id={GIRONE_ID}"
    f"&territorio_id={TERRITORIO_ID}"
    f"&campionato_id={CAMPIONATO_ID}"
    f"&inizio_stagione={STAGIONE_INIZIO}"
    f"&fine_stagione={STAGIONE_FINE}"
    f"&societa_id=null&squadra_id=null&pubblicato=1"
    f"&search=&sort=&order=&offset=0&limit=500"
)

CLASSIFICA_URL = (
    f"https://ivl.usacli.it/Classifica/{GIRONE_ID}"
    f"?_a=&inizio_stagione={STAGIONE_INIZIO}&fine_stagione={STAGIONE_FINE}"
)

TIMEOUT = 15  # secondi


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def append_log(esito: str, dettagli: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / "ultimo_aggiornamento.log", "a", encoding="utf-8") as f:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{ts} | {esito} | {dettagli}\n")


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Parsing partite ───────────────────────────────────────────────────────────

def parse_partita(r: dict) -> dict:
    """Converte una riga dell'API PartiteData nel formato interno."""
    # Data e ora
    data_orario = r.get("data_orario", "") or ""
    try:
        dt = datetime.strptime(data_orario, "%Y-%m-%d %H:%M:%S")
        data_iso = dt.strftime("%Y-%m-%d")
        ora_iso  = dt.strftime("%H:%M")
    except ValueError:
        data_iso = data_orario[:10] if len(data_orario) >= 10 else ""
        ora_iso  = ""

    casa    = (r.get("squadra_casa_name")    or "").strip()
    ospite  = (r.get("squadra_ospite_name")  or "").strip()
    palestra = (r.get("palestra1_name")      or r.get("Palestra") or "").strip()
    indirizzo = (r.get("Palestra_indirizzo") or "").strip()

    # Risultato — set_vinti_casa/ospite + punteggi set singoli
    sv_casa   = r.get("ris_set_casa")
    sv_ospite = r.get("ris_set_ospite")
    giocata   = sv_casa is not None and sv_ospite is not None

    if giocata:
        set_casa   = [r[f"ris_punti{i}set_casa"]   for i in range(1, 6) if r.get(f"ris_punti{i}set_casa") is not None]
        set_ospite = [r[f"ris_punti{i}set_ospite"] for i in range(1, 6) if r.get(f"ris_punti{i}set_ospite") is not None]
        risultato = {
            "set_casa":          set_casa,
            "set_ospite":        set_ospite,
            "set_vinti_casa":    int(sv_casa),
            "set_vinti_ospite":  int(sv_ospite),
        }
    else:
        risultato = None

    olimpia_pb_gioca = SQUADRA_MONITORATA.lower() in casa.lower() or \
                       SQUADRA_MONITORATA.lower() in ospite.lower()
    olimpia_pb_casa  = SQUADRA_MONITORATA.lower() in casa.lower()

    partita_id = f"{data_iso}_{casa}_{ospite}".replace(" ", "_").lower()

    return {
        "id":               partita_id,
        "ivl_id":           r.get("id"),
        "npartita":         r.get("npartita_custom", ""),
        "data":             data_iso,
        "ora":              ora_iso,
        "squadra_casa":     casa,
        "squadra_ospite":   ospite,
        "palestra":         palestra,
        "indirizzo":        indirizzo,
        "lat":              r.get("palestra1_latitude"),
        "lon":              r.get("palestra1_longitude"),
        "risultato":        risultato,
        "olimpia_pb_gioca": olimpia_pb_gioca,
        "olimpia_pb_casa":  olimpia_pb_casa,
        "giocata":          giocata,
    }


# ── Parsing classifica ────────────────────────────────────────────────────────

def parse_classifica(rows: list) -> list:
    """Converte la lista dell'API Classifica nel formato interno."""
    classifica = []
    for r in rows:
        nome = (r.get("name") or "").strip()
        if not nome:
            continue
        sv = r.get("SetVinti", 0) or 0
        sp = r.get("SetPersi", 0) or 0
        pv = r.get("PuntiVinti", 0) or 0
        pp = r.get("PuntiPersi", 0) or 0
        pg = r.get("PartiteGiocate", 0) or 0
        pwin = r.get("PartiteVinte", 0) or 0

        classifica.append({
            "squadra":          nome,
            "punti":            r.get("Punteggio", 0) or 0,
            "partite_giocate":  pg,
            "partite_vinte":    pwin,
            "partite_perse":    pg - pwin,
            "set_vinti":        sv,
            "set_persi":        sp,
            "quoziente_set":    round(sv / sp, 3) if sp > 0 else None,
            "punti_vinti":      pv,
            "punti_persi":      pp,
            "quoziente_punti":  round(pv / pp, 3) if pp > 0 else None,
        })

    # Ordina: set_vinti DESC, quoziente_set DESC, quoziente_punti DESC, nome ASC
    classifica.sort(key=lambda r: (
        -(r["set_vinti"]),
        -(r["quoziente_set"]  or 0),
        -(r["quoziente_punti"] or 0),
        r["squadra"],
    ))
    for i, r in enumerate(classifica, 1):
        r["posizione"] = i

    return classifica


# ── Merge partite (protezione da regressioni) ─────────────────────────────────

def merge_partite(esistenti: list, nuove: list) -> tuple:
    mappa = {p["id"]: p for p in esistenti}
    nuove_count = aggiornati_count = 0

    for nuova in nuove:
        pid = nuova["id"]
        if pid not in mappa:
            mappa[pid] = nuova
            nuove_count += 1
        else:
            old = mappa[pid]
            if nuova.get("risultato") and not old.get("risultato"):
                mappa[pid] = {**old, **nuova}
                aggiornati_count += 1
            elif not nuova.get("risultato") and old.get("risultato"):
                pass  # mantieni risultato già presente
            else:
                mappa[pid] = {**old, **nuova}

    ordinate = sorted(mappa.values(), key=lambda p: (p["data"], p.get("ora", "")))
    return ordinate, nuove_count, aggiornati_count


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    log("=== fetch_data.py avviato ===")

    esistenti = load_json(DATA_DIR / "partite.json").get("partite", [])
    nuove_count = aggiornati_count = classifica_count = 0

    # --- Partite ---
    log(f"GET {PARTITE_URL}")
    try:
        resp = requests.get(PARTITE_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        log(f"ERRORE fetch partite: {e}")
        append_log("ERRORE", f"fetch partite: {e}")
        return 1

    rows = payload.get("rows", []) if isinstance(payload, dict) else payload
    log(f"Righe ricevute: {len(rows)}  (total={payload.get('total', '?') if isinstance(payload, dict) else '?'})")

    if not rows:
        log("ATTENZIONE: 0 partite ricevute — non sovrascrivere")
    else:
        nuove = [parse_partita(r) for r in rows]
        merge, nuove_count, aggiornati_count = merge_partite(esistenti, nuove)
        ts = datetime.now(timezone.utc).isoformat()
        save_json(DATA_DIR / "partite.json", {"partite": merge, "ultimo_aggiornamento": ts})
        log(f"partite.json: +{nuove_count} nuove, {aggiornati_count} risultati aggiornati, {len(merge)} totali")

    # --- Classifica ---
    log(f"GET {CLASSIFICA_URL}")
    try:
        resp = requests.get(CLASSIFICA_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        classifica_raw = resp.json()
    except Exception as e:
        log(f"ERRORE fetch classifica: {e}")
        classifica_raw = []

    if not classifica_raw:
        log("ATTENZIONE: classifica vuota — non sovrascrivere")
    else:
        classifica = parse_classifica(classifica_raw)
        classifica_count = len(classifica)
        ts = datetime.now(timezone.utc).isoformat()
        save_json(DATA_DIR / "classifica.json", {"classifica": classifica, "ultimo_aggiornamento": ts})
        log(f"classifica.json: {classifica_count} squadre")
        for r in classifica:
            qs  = f"{r['quoziente_set']:.3f}"  if r["quoziente_set"]  is not None else "∞"
            qp  = f"{r['quoziente_punti']:.3f}" if r["quoziente_punti"] is not None else "∞"
            log(f"  {r['posizione']:2}. {r['squadra']:<35} SV={r['set_vinti']:3}  QS={qs}")

    dettagli = f"partite +{nuove_count}/{aggiornati_count} aggiornate, classifica {classifica_count} sq."
    append_log("OK", dettagli)
    log("=== fetch_data.py completato ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
