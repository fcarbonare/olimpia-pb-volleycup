#!/usr/bin/env python3
"""
fetch_storico.py — Posizioni finali delle squadre avversarie nelle stagioni passate.

Fonte: GET https://ivl.usacli.it/ClassificheArchivioData?anno=YY&territorio_id=3
(lo stesso endpoint JSON usato dalla pagina "Storico → Classifica YY-YY" del sito IVL).

Per ogni squadra presente in data/partite.json (esclusa Olimpia PB) raccoglie tutte le
classifiche di campionati misti (Basic, Superbasic, Pre Basic, Top, Ghelabasic…) e scrive
data/storico_avversari.json. Va rieseguito a mano, una volta l'anno o quando serve.

    /usr/bin/python3 scripts/fetch_storico.py
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
TERRITORIO_ID = os.getenv("IVL_TERRITORIO_ID", "3")
SQUADRA_MONITORATA = os.getenv("SQUADRA_MONITORATA", "Olimpia PB")
ANNI = [21, 22, 23, 24, 25]  # inizio stagione (21 = 2021-22)
ESCLUDI = re.compile(r"under|femminil|open fem", re.I)  # solo campionati misti
SUFFISSI = re.compile(r"\b(basic|superbasic|super|top|pre|misto)\b", re.I)


def chiave(nome: str) -> str:
    """Nome squadra senza categoria (Basic/Superbasic/Top…), per riconoscere lo stesso club."""
    return re.sub(r"\s+", " ", SUFFISSI.sub("", nome or "")).strip().lower()


def main() -> int:
    partite = json.load(open(DATA_DIR / "partite.json", encoding="utf-8")).get("partite", [])
    avversari = {}
    for p in partite:
        for n in (p["squadra_casa"], p["squadra_ospite"]):
            if SQUADRA_MONITORATA.lower() not in n.lower():
                avversari[chiave(n)] = n

    storico = {k: [] for k in avversari}
    for anno in ANNI:
        r = requests.get("https://ivl.usacli.it/ClassificheArchivioData",
                         params={"anno": anno, "territorio_id": TERRITORIO_ID}, timeout=30)
        r.raise_for_status()
        gironi = r.json()
        print(f"anno {anno}: {len(gironi)} gironi")
        for g in gironi:
            if ESCLUDI.search(g.get("campionato") or ""):
                continue
            classifica = json.loads(g.get("classifica") or "[]")
            for pos, t in enumerate(classifica, 1):
                k = chiave(t.get("name"))
                if k in storico:
                    storico[k].append({
                        "stagione": f"20{anno}-{anno + 1}",
                        "campionato": (g.get("campionato") or "").strip(),
                        "girone": (g.get("girone") or "").strip(),
                        "nome": t["name"],
                        "posizione": pos,
                        "squadre": len(classifica),
                        "punti": t.get("Punteggio"),
                        "giocate": t.get("PartiteGiocate"),
                        "set_vinti": t.get("SetVinti"),
                        "set_persi": t.get("SetPersi"),
                        "data_fine": (g.get("data_orario") or "")[:10],
                    })

    for voci in storico.values():
        voci.sort(key=lambda v: (v["stagione"], v["data_fine"]))
    out = {
        "generato": datetime.now(timezone.utc).isoformat(),
        "squadre": {avversari[k]: v for k, v in storico.items()},
    }
    with open(DATA_DIR / "storico_avversari.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    for n, v in out["squadre"].items():
        print(f"  {n}: {len(v)} classifiche")
    return 0


if __name__ == "__main__":
    sys.exit(main())
