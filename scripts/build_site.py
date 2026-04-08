#!/usr/bin/env python3
"""
build_site.py — Genera i file HTML statici per GitHub Pages.

Produce:
  site/index.html      — classifica top-5 + prossima/ultima partita Olimpia PB
  site/calendario.html — tutte le partite del girone
  site/classifica.html — classifica completa
"""

import json
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
SITE_DIR = BASE_DIR / os.getenv("SITE_DIR", "docs")
LOG_DIR = BASE_DIR / os.getenv("LOG_DIR", "logs")
SQUADRA_MONITORATA = os.getenv("SQUADRA_MONITORATA", "Olimpia PB")


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def append_log(esito: str, dettagli: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / "ultimo_aggiornamento.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{ts} | build_site | {esito} | {dettagli}\n")


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def fmt_data(iso_date: str) -> str:
    """Converte 'YYYY-MM-DD' in 'gg/mm/aaaa'."""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def fmt_ts(iso_ts: Optional[str]) -> str:
    if not iso_ts:
        return "N/D"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y alle %H:%M")
    except ValueError:
        return iso_ts


def fmt_risultato(risultato) -> str:
    if not risultato:
        return ""
    sv_c = risultato.get("set_vinti_casa", 0)
    sv_o = risultato.get("set_vinti_ospite", 0)
    set_c = risultato.get("set_casa", [])
    set_o = risultato.get("set_ospite", [])
    set_str = ", ".join(f"{a}-{b}" for a, b in zip(set_c, set_o))
    return f"{sv_c}-{sv_o} ({set_str})"


def css_path() -> str:
    return "assets/style.css"


def nav_html(pagina_attiva: str) -> str:
    pages = [
        ("index.html", "Home"),
        ("calendario.html", "Calendario"),
        ("classifica.html", "Classifica"),
    ]
    items = []
    for href, label in pages:
        cls = ' class="active"' if href == pagina_attiva else ""
        items.append(f'<li><a href="{href}"{cls}>{label}</a></li>')
    return "<nav><ul>" + "".join(items) + "</ul></nav>"


def page_shell(title: str, body: str, pagina_attiva: str, ultimo_agg: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Olimpia PB Volleycup</title>
  <link rel="stylesheet" href="{css_path()}">
</head>
<body>
  <header>
    <div class="header-inner">
      <img src="assets/logo.png" alt="Logo Olimpia PB" class="header-logo">
      <div class="header-text">
        <span class="logo-text">OLIMPIA <span>P.B.</span></span>
        <span class="subtitle">Volleycup Basic — Girone 910</span>
      </div>
    </div>
    {nav_html(pagina_attiva)}
  </header>
  <main>
    {body}
  </main>
  <footer>
    <p>Ultimo aggiornamento: {ultimo_agg}</p>
    <p>Dati: <a href="https://ivl.usacli.it" target="_blank">IVL USACLI</a> — Campionato Mista Senior 2025‑26</p>
  </footer>
</body>
</html>"""


# ── index.html ────────────────────────────────────────────────────────────────

def build_index(partite: list, classifica: list, ultimo_agg: str) -> str:
    oggi = date.today().isoformat()

    olimpia_partite = [p for p in partite if p.get("olimpia_pb_gioca")]
    prossima = next(
        (p for p in olimpia_partite if not p.get("giocata") and p["data"] >= oggi),
        None,
    )
    ultima = next(
        (p for p in reversed(olimpia_partite) if p.get("giocata")),
        None,
    )

    # Prossima partita
    if prossima:
        casa = prossima["squadra_casa"]
        ospite = prossima["squadra_ospite"]
        casa_cls = " olimpia" if prossima.get("olimpia_pb_casa") else ""
        ospite_cls = "" if prossima.get("olimpia_pb_casa") else " olimpia"
        prossima_html = f"""
<section class="card">
  <h2>Prossima partita</h2>
  <div class="match-card olimpia-match">
    <div class="match-date">{fmt_data(prossima['data'])} ore {prossima.get('ora','--:--')}</div>
    <div class="match-teams">
      <span class="team{casa_cls}">{casa}</span>
      <span class="vs">vs</span>
      <span class="team{ospite_cls}">{ospite}</span>
    </div>
    <div class="match-venue">📍 {prossima.get('palestra','')}</div>
  </div>
</section>"""
    else:
        prossima_html = '<section class="card"><h2>Prossima partita</h2><p>Nessuna partita in programma.</p></section>'

    # Ultima partita
    if ultima:
        casa = ultima["squadra_casa"]
        ospite = ultima["squadra_ospite"]
        casa_cls = " olimpia" if ultima.get("olimpia_pb_casa") else ""
        ospite_cls = "" if ultima.get("olimpia_pb_casa") else " olimpia"
        ris = fmt_risultato(ultima.get("risultato"))
        ultima_html = f"""
<section class="card">
  <h2>Ultima partita</h2>
  <div class="match-card olimpia-match">
    <div class="match-date">{fmt_data(ultima['data'])}</div>
    <div class="match-teams">
      <span class="team{casa_cls}">{casa}</span>
      <span class="vs">{ris}</span>
      <span class="team{ospite_cls}">{ospite}</span>
    </div>
  </div>
</section>"""
    else:
        ultima_html = '<section class="card"><h2>Ultima partita</h2><p>Nessun risultato disponibile.</p></section>'

    # Classifica top-5
    top5 = classifica[:5]
    righe = ""
    for r in top5:
        cls = ' class="olimpia-row"' if SQUADRA_MONITORATA.lower() in r["squadra"].lower() else ""
        righe += f"""<tr{cls}>
  <td>{r.get('posizione','')}</td>
  <td class="team-name">{r['squadra']}</td>
  <td>{r['set_vinti']}</td>
  <td>{r['set_persi']}</td>
  <td>{r['partite_giocate']}</td>
</tr>"""

    classifica_html = f"""
<section class="card">
  <h2>Classifica (top 5)</h2>
  <table>
    <thead><tr><th>#</th><th>Squadra</th><th>SV</th><th>SP</th><th>G</th></tr></thead>
    <tbody>{righe}</tbody>
  </table>
  <p class="link-more"><a href="classifica.html">Classifica completa →</a></p>
</section>"""

    body = prossima_html + ultima_html + classifica_html
    return page_shell("Home", body, "index.html", ultimo_agg)


# ── calendario.html ───────────────────────────────────────────────────────────

def build_calendario(partite: list, ultimo_agg: str) -> str:
    if not partite:
        body = '<section class="card"><p>Nessuna partita disponibile.</p></section>'
        return page_shell("Calendario", body, "calendario.html", ultimo_agg)

    oggi = date.today().isoformat()
    righe = ""
    for p in partite:
        is_olimpia = p.get("olimpia_pb_gioca", False)
        is_casa = p.get("olimpia_pb_casa", False)
        row_cls = "olimpia-row" if is_olimpia else ""
        badge = '<span class="badge">Olimpia PB</span> ' if is_olimpia else ""

        casa = p["squadra_casa"]
        ospite = p["squadra_ospite"]
        if is_olimpia:
            casa_cls = " olimpia" if is_casa else ""
            ospite_cls = "" if is_casa else " olimpia"
        else:
            casa_cls = ospite_cls = ""

        if p.get("giocata") and p.get("risultato"):
            ris = fmt_risultato(p["risultato"])
            risultato_td = f'<td class="risultato">{ris}</td>'
        elif p["data"] < oggi:
            risultato_td = '<td class="risultato tbd">Risultato non disponibile</td>'
        else:
            risultato_td = f'<td class="risultato futuro">ore {p.get("ora","--:--")} — {p.get("palestra","")}</td>'

        righe += f"""<tr class="{row_cls}">
  <td class="data">{fmt_data(p['data'])}</td>
  <td class="team{casa_cls}">{badge}{casa}</td>
  <td class="vs">vs</td>
  <td class="team{ospite_cls}">{ospite}</td>
  {risultato_td}
</tr>"""

    body = f"""
<section class="card">
  <h2>Calendario partite — Girone 910</h2>
  <div class="table-scroll">
    <table class="calendario-table">
      <thead>
        <tr>
          <th>Data</th>
          <th>Casa</th>
          <th></th>
          <th>Ospite</th>
          <th>Risultato / Orario</th>
        </tr>
      </thead>
      <tbody>{righe}</tbody>
    </table>
  </div>
</section>"""

    return page_shell("Calendario", body, "calendario.html", ultimo_agg)


# ── classifica.html ───────────────────────────────────────────────────────────

def build_classifica(classifica: list, ultimo_agg: str) -> str:
    if not classifica:
        body = '<section class="card"><p>Classifica non disponibile.</p></section>'
        return page_shell("Classifica", body, "classifica.html", ultimo_agg)

    righe = ""
    for r in classifica:
        is_olimpia = SQUADRA_MONITORATA.lower() in r["squadra"].lower()
        row_cls = ' class="olimpia-row"' if is_olimpia else ""
        badge = ' <span class="badge">★</span>' if is_olimpia else ""

        qs = r.get("quoziente_set", 0)
        qp = r.get("quoziente_punti", 0)
        qs_str = "∞" if qs == float("inf") else f"{qs:.3f}"
        qp_str = "∞" if qp == float("inf") else f"{qp:.3f}"

        righe += f"""<tr{row_cls}>
  <td class="pos">{r.get('posizione','')}</td>
  <td class="team-name">{r['squadra']}{badge}</td>
  <td>{r.get('punti', '')}</td>
  <td>{r['partite_giocate']}</td>
  <td>{r['partite_vinte']}</td>
  <td>{r['partite_perse']}</td>
  <td class="highlight">{r['set_vinti']}</td>
  <td>{r['set_persi']}</td>
  <td>{qs_str}</td>
  <td>{r['punti_vinti']}</td>
  <td>{r['punti_persi']}</td>
  <td>{qp_str}</td>
</tr>"""

    body = f"""
<section class="card">
  <h2>Classifica completa — Girone 910</h2>
  <p class="nota">Ordinamento: set vinti (criteri IVL campionato Mista Senior)</p>
  <div class="table-scroll">
    <table class="classifica-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Squadra</th>
          <th>Pt</th>
          <th>G</th>
          <th>V</th>
          <th>P</th>
          <th title="Set vinti">SV</th>
          <th title="Set persi">SP</th>
          <th title="Quoziente set">QS</th>
          <th title="Punti vinti">PV</th>
          <th title="Punti persi">PP</th>
          <th title="Quoziente punti">QP</th>
        </tr>
      </thead>
      <tbody>{righe}</tbody>
    </table>
  </div>
</section>"""

    return page_shell("Classifica", body, "classifica.html", ultimo_agg)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    log("=== build_site.py avviato ===")

    dati_partite = load_json(DATA_DIR / "partite.json")
    dati_classifica = load_json(DATA_DIR / "classifica.json")

    partite = dati_partite.get("partite", [])
    classifica = dati_classifica.get("classifica", [])

    ultimo_agg_ts = dati_partite.get("ultimo_aggiornamento") or dati_classifica.get("ultimo_aggiornamento")
    ultimo_agg = fmt_ts(ultimo_agg_ts)

    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "assets").mkdir(exist_ok=True)

    # Genera le pagine
    pages = {
        "index.html": build_index(partite, classifica, ultimo_agg),
        "calendario.html": build_calendario(partite, ultimo_agg),
        "classifica.html": build_classifica(classifica, ultimo_agg),
    }

    for filename, html in pages.items():
        path = SITE_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"Generato: {path}")

    append_log("OK", f"generate {len(pages)} pagine HTML")
    log("=== build_site.py completato ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
