#!/usr/bin/env python3
"""
update_classifica.py — Ricalcola la classifica locale da partite.json.

Logica di ordinamento (priorità decrescente):
  1. Set vinti totali (DESC)
  2. Quoziente set (set_v / set_p) (DESC)
  3. Quoziente punti (pt_v / pt_p) (DESC)
  4. Nome squadra (ASC)
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
LOG_DIR = BASE_DIR / os.getenv("LOG_DIR", "logs")


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def append_log(esito: str, dettagli: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / "ultimo_aggiornamento.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{ts} | update_classifica | {esito} | {dettagli}\n")


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calcola_classifica(partite: list[dict]) -> list[dict]:
    """
    Calcola la classifica dal risultato di tutte le partite giocate.
    """
    stats: dict[str, dict] = defaultdict(lambda: {
        "partite_giocate": 0,
        "partite_vinte": 0,
        "partite_perse": 0,
        "set_vinti": 0,
        "set_persi": 0,
        "punti_vinti": 0,
        "punti_persi": 0,
    })

    for partita in partite:
        if not partita.get("giocata"):
            continue
        risultato = partita.get("risultato")
        if not risultato:
            continue

        casa = partita["squadra_casa"]
        ospite = partita["squadra_ospite"]
        sv_casa = risultato["set_vinti_casa"]
        sv_ospite = risultato["set_vinti_ospite"]
        set_casa = risultato.get("set_casa", [])
        set_ospite = risultato.get("set_ospite", [])

        # Punti (palloni) totali
        pt_casa = sum(set_casa)
        pt_ospite = sum(set_ospite)

        # Aggiornamento stats casa
        stats[casa]["partite_giocate"] += 1
        stats[casa]["set_vinti"] += sv_casa
        stats[casa]["set_persi"] += sv_ospite
        stats[casa]["punti_vinti"] += pt_casa
        stats[casa]["punti_persi"] += pt_ospite
        if sv_casa > sv_ospite:
            stats[casa]["partite_vinte"] += 1
        else:
            stats[casa]["partite_perse"] += 1

        # Aggiornamento stats ospite
        stats[ospite]["partite_giocate"] += 1
        stats[ospite]["set_vinti"] += sv_ospite
        stats[ospite]["set_persi"] += sv_casa
        stats[ospite]["punti_vinti"] += pt_ospite
        stats[ospite]["punti_persi"] += pt_casa
        if sv_ospite > sv_casa:
            stats[ospite]["partite_vinte"] += 1
        else:
            stats[ospite]["partite_perse"] += 1

    # Costruzione lista con quozienti
    classifica = []
    for squadra, s in stats.items():
        q_set = (
            round(s["set_vinti"] / s["set_persi"], 3)
            if s["set_persi"] > 0
            else float("inf")
        )
        q_punti = (
            round(s["punti_vinti"] / s["punti_persi"], 3)
            if s["punti_persi"] > 0
            else float("inf")
        )
        classifica.append({
            "squadra": squadra,
            "punti": 0,  # Il sistema IVL calcola i punti ufficiali; qui usiamo set_vinti
            "partite_giocate": s["partite_giocate"],
            "partite_vinte": s["partite_vinte"],
            "partite_perse": s["partite_perse"],
            "set_vinti": s["set_vinti"],
            "set_persi": s["set_persi"],
            "quoziente_set": q_set,
            "punti_vinti": s["punti_vinti"],
            "punti_persi": s["punti_persi"],
            "quoziente_punti": q_punti,
        })

    # Ordinamento: 1. set_vinti DESC, 2. quoziente_set DESC, 3. quoziente_punti DESC, 4. nome ASC
    classifica.sort(key=lambda r: (
        -r["set_vinti"],
        -(r["quoziente_set"] if r["quoziente_set"] != float("inf") else 9999),
        -(r["quoziente_punti"] if r["quoziente_punti"] != float("inf") else 9999),
        r["squadra"],
    ))

    # Aggiunge posizione
    for i, r in enumerate(classifica, start=1):
        r["posizione"] = i

    return classifica


def main() -> int:
    log("=== update_classifica.py avviato ===")

    partite_path = DATA_DIR / "partite.json"
    if not partite_path.exists():
        log("ERRORE: partite.json non trovato")
        append_log("ERRORE", "partite.json non trovato")
        return 1

    dati = load_json(partite_path)
    partite = dati.get("partite", [])

    if not partite:
        log("ATTENZIONE: nessuna partita in partite.json")
        append_log("ATTENZIONE", "nessuna partita trovata")
        return 0

    partite_giocate = [p for p in partite if p.get("giocata")]
    log(f"Partite totali: {len(partite)}, giocate: {len(partite_giocate)}")

    classifica = calcola_classifica(partite)

    ts = datetime.now(timezone.utc).isoformat()
    save_json(DATA_DIR / "classifica.json", {
        "classifica": classifica,
        "fonte": "calcolata_localmente",
        "ultimo_aggiornamento": ts,
    })

    log(f"classifica.json aggiornato: {len(classifica)} squadre")
    for r in classifica:
        inf_str = lambda v: "∞" if v == float("inf") else str(v)
        log(
            f"  {r['posizione']:2}. {r['squadra']:<30} "
            f"SV={r['set_vinti']:3}  SP={r['set_persi']:3}  "
            f"QS={inf_str(r['quoziente_set'])}"
        )

    append_log("OK", f"classifica aggiornata con {len(classifica)} squadre")
    log("=== update_classifica.py completato ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
