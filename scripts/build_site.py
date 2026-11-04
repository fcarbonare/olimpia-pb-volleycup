#!/usr/bin/env python3
"""
build_site.py — Genera i file HTML statici per GitHub Pages.

Produce:
  docs/{index,calendario,classifica}.html + docs/partite/  — stagione corrente
  docs/<anno>/...                                         — stagioni archiviate (dati in data/archivio/)
"""

import json
import os
import sys
from dataclasses import dataclass
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


@dataclass
class Stagione:
    """Configurazione di una stagione (corrente o archiviata)."""
    anno: str                 # "2026‑27"
    girone_label: str         # "Girone D"
    girone_id: int
    campionato_id: int
    data_dir: Path
    out_dir: Path
    profondita: int = 0       # livelli di cartella sotto docs/ (per asset e link)
    archivio: bool = False    # stagione conclusa, non più sincronizzata con IVL
    campioni: bool = False    # banner "campioni" in homepage
    foto_partite: bool = False  # foto nelle pagine delle singole partite

    @property
    def ivl_url(self) -> str:
        return (f"https://ivl.usacli.it/CalendarioView?girone_id={self.girone_id}"
                f"&territorio_id=3&campionato_id={self.campionato_id}")


CORRENTE = Stagione(
    anno="2026‑27", girone_label="Girone D", girone_id=1078, campionato_id=389,
    data_dir=DATA_DIR, out_dir=SITE_DIR,
)
ARCHIVIO = [
    Stagione(
        anno="2025‑26", girone_label="Girone 910", girone_id=910, campionato_id=342,
        data_dir=DATA_DIR / "archivio" / "2025-26", out_dir=SITE_DIR / "2025-26",
        profondita=1, archivio=True, campioni=True, foto_partite=True,
    ),
]


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


GIORNI_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def fmt_data(iso_date: str) -> str:
    """Converte 'YYYY-MM-DD' in 'gg/mm/aaaa'."""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def fmt_data_con_giorno(iso_date: str) -> str:
    """Converte 'YYYY-MM-DD' in 'gg/mm/aaaa<br><small>giorno</small>'."""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
        giorno = GIORNI_IT[d.weekday()]
        return f'{d.strftime("%d/%m/%Y")}<br><small class="giorno">{giorno}</small>'
    except ValueError:
        return iso_date


def fmt_luogo(partita: dict) -> str:
    """Restituisce indirizzo con link Google Maps basato sul testo dell'indirizzo."""
    indirizzo = partita.get("indirizzo", "").strip()
    if not indirizzo:
        return ""
    import urllib.parse
    maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(indirizzo)}"
    return f'<a href="{maps_url}" target="_blank" rel="noopener">{indirizzo}</a>'


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
    return f'{sv_c}-{sv_o}<br><small class="set-dettaglio">({set_str})</small>'


def nav_html(pagina_attiva: str, cfg: Stagione, depth: int = 0) -> str:
    prefix = "../" * depth
    pages = [
        ("index", f"{prefix}index.html", "Home"),
        ("calendario", f"{prefix}calendario.html", "Calendario"),
        ("classifica", f"{prefix}classifica.html", "Classifica"),
    ]
    if cfg.archivio:
        pages.append(("", "../" * (depth + cfg.profondita) + "index.html", "← Stagione corrente"))
    else:
        for a in ARCHIVIO:
            pages.append(("", f"{prefix}{a.out_dir.name}/index.html", f"Stagione {a.anno}"))
    items = []
    for key, href, label in pages:
        cls = ' class="active"' if key and pagina_attiva == key else ""
        items.append(f'<li><a href="{href}"{cls}>{label}</a></li>')
    return "<nav><ul>" + "".join(items) + "</ul></nav>"


def page_shell(title: str, body: str, pagina_attiva: str, ultimo_agg: str,
               cfg: Stagione, depth: int = 0) -> str:
    asset_prefix = "../" * (depth + cfg.profondita)
    css = f"{asset_prefix}assets/style.css"
    logo = f"{asset_prefix}assets/logo.png"
    nota_archivio = (
        '<p>Stagione conclusa: dati archiviati, non più aggiornati.</p>' if cfg.archivio else ""
    )
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Olimpia PB Volleycup</title>
  <link rel="stylesheet" href="{css}">
</head>
<body>
  <header>
    <div class="header-inner">
      <img src="{logo}" alt="Logo Olimpia PB" class="header-logo">
      <div class="header-text">
        <span class="logo-text">OLIMPIA <span>P.B.</span></span>
        <span class="subtitle">Volleycup Basic — {cfg.girone_label} · {cfg.anno}</span>
      </div>
    </div>
    {nav_html(pagina_attiva, cfg, depth)}
  </header>
  <main>
    {body}
  </main>
  <footer>
    {nota_archivio}
    <p>Ultimo aggiornamento: {ultimo_agg}</p>
    <p>Dati: <a href="{cfg.ivl_url}" target="_blank" rel="noopener">IVL USACLI</a> — Campionato Mista Senior {cfg.anno}</p>
  </footer>
</body>
</html>"""


# ── index.html ────────────────────────────────────────────────────────────────

def _match_cards_html(partite: list) -> str:
    """Card 'Prossima partita' e 'Ultima partita' per la stagione in corso."""
    oggi = date.today().isoformat()
    olimpia_partite = [p for p in partite if p.get("olimpia_pb_gioca")]
    prossima = next(
        (p for p in olimpia_partite if not p.get("giocata") and p["data"] >= oggi),
        None,
    )
    ultima = next((p for p in reversed(olimpia_partite) if p.get("giocata")), None)

    if prossima:
        casa_cls = " olimpia" if prossima.get("olimpia_pb_casa") else ""
        ospite_cls = "" if prossima.get("olimpia_pb_casa") else " olimpia"
        prossima_html = f"""
<section class="card">
  <h2>Prossima partita</h2>
  <div class="match-card olimpia-match">
    <div class="match-date">{fmt_data(prossima['data'])} ore {prossima.get('ora','--:--')}</div>
    <div class="match-teams">
      <span class="team{casa_cls}">{prossima['squadra_casa']}</span>
      <span class="vs">vs</span>
      <span class="team{ospite_cls}">{prossima['squadra_ospite']}</span>
    </div>
    <div class="match-venue">📍 {prossima.get('palestra','')}</div>
    {f'<div class="match-venue">🗺 {fmt_luogo(prossima)}</div>' if prossima.get('indirizzo') else ''}
  </div>
  <p class="link-more"><a href="partite/{prossima['id']}.html">Dettagli →</a></p>
</section>"""
    else:
        prossima_html = '<section class="card"><h2>Prossima partita</h2><p>Nessuna partita in programma.</p></section>'

    if ultima:
        casa_cls = " olimpia" if ultima.get("olimpia_pb_casa") else ""
        ospite_cls = "" if ultima.get("olimpia_pb_casa") else " olimpia"
        r = ultima.get("risultato") or {}
        ris = f'{r.get("set_vinti_casa", 0)}-{r.get("set_vinti_ospite", 0)}'
        ultima_html = f"""
<section class="card">
  <h2>Ultima partita</h2>
  <div class="match-card olimpia-match">
    <div class="match-date">{fmt_data(ultima['data'])}</div>
    <div class="match-teams">
      <span class="team{casa_cls}">{ultima['squadra_casa']}</span>
      <span class="vs">{ris}</span>
      <span class="team{ospite_cls}">{ultima['squadra_ospite']}</span>
    </div>
  </div>
  <p class="link-more"><a href="partite/{ultima['id']}.html">Dettagli →</a></p>
</section>"""
    else:
        ultima_html = '<section class="card"><h2>Ultima partita</h2><p>Nessun risultato disponibile.</p></section>'
    return prossima_html + ultima_html


def build_index(partite: list, classifica: list, ultimo_agg: str, cfg: Stagione) -> str:
    if cfg.campioni:
        intro_html = f"""
<section class="card campioni-card">
  <div class="campioni-banner">
    <div class="campioni-trofeo">🏆</div>
    <div class="campioni-testo">
      <div class="campioni-titolo">CAMPIONI!</div>
      <div class="campioni-sottotitolo">Volleycup Basic — {cfg.girone_label}</div>
      <div class="campioni-stagione">Stagione {cfg.anno}</div>
    </div>
  </div>
</section>"""
        titolo_classifica = "Classifica finale (top 5)"
    else:
        intro_html = _match_cards_html(partite)
        titolo_classifica = "Classifica (top 5)"

    righe = ""
    for r in classifica[:5]:
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
  <h2>{titolo_classifica}</h2>
  <table>
    <thead><tr><th>#</th><th>Squadra</th><th>SV</th><th>SP</th><th>G</th></tr></thead>
    <tbody>{righe}</tbody>
  </table>
  <p class="link-more"><a href="classifica.html">Classifica completa →</a></p>
</section>"""

    return page_shell("Home", intro_html + classifica_html, "index", ultimo_agg, cfg)


# ── calendario.html ───────────────────────────────────────────────────────────

def build_calendario(partite: list, ultimo_agg: str, cfg: Stagione) -> str:
    if not partite:
        body = '<section class="card"><p>Nessuna partita disponibile.</p></section>'
        return page_shell("Calendario", body, "calendario", ultimo_agg, cfg)

    oggi = date.today().isoformat()
    righe = ""
    for p in partite:
        is_olimpia = p.get("olimpia_pb_gioca", False)
        is_casa = p.get("olimpia_pb_casa", False)
        row_cls = "olimpia-row" if is_olimpia else ""
        badge = ""

        casa = p["squadra_casa"]
        ospite = p["squadra_ospite"]
        if is_olimpia:
            casa_cls = " olimpia" if is_casa else ""
            ospite_cls = "" if is_casa else " olimpia"
        else:
            casa_cls = ospite_cls = ""

        luogo = fmt_luogo(p)
        if p.get("giocata") and p.get("risultato"):
            ris = fmt_risultato(p["risultato"])
            risultato_td = f'<td class="risultato">{ris}</td>'
        elif p["data"] < oggi:
            risultato_td = '<td class="risultato tbd">Risultato non disponibile</td>'
        else:
            luogo_str = f'<br><small class="set-dettaglio">{luogo}</small>' if luogo else ""
            risultato_td = f'<td class="risultato futuro">ore {p.get("ora","--:--")}{luogo_str}</td>'

        if is_olimpia:
            row_extra = f' onclick="window.location.href=\'partite/{p["id"]}.html\'" style="cursor:pointer"'
        else:
            row_extra = ""

        data_html = fmt_data_con_giorno(p['data'])
        if p.get("rinviata"):
            data_orig = fmt_data(p.get("data_originale", "")) if p.get("data_originale") else ""
            tooltip = f"Rinviata dal {data_orig}" if data_orig else "Partita rinviata"
            data_html = data_html.replace(
                '<br>',
                f'<span class="rinviata-asterisk" title="{tooltip}">*</span><br>',
                1,
            )

        righe += f"""<tr class="{row_cls}"{row_extra}>
  <td class="data">{data_html}</td>
  <td class="team{casa_cls}">{badge}{casa}</td>
  <td class="vs">vs</td>
  <td class="team{ospite_cls}">{ospite}</td>
  {risultato_td}
</tr>"""

    has_rinviate = any(p.get("rinviata") for p in partite)
    nota_rinviate = (
        '<p class="nota"><span class="rinviata-asterisk">*</span> Partita rinviata rispetto alla data originale.</p>'
        if has_rinviate else ""
    )

    body = f"""
<section class="card">
  <h2>Calendario partite — {cfg.girone_label}</h2>
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
  {nota_rinviate}
</section>"""

    return page_shell("Calendario", body, "calendario", ultimo_agg, cfg)


# ── classifica.html ───────────────────────────────────────────────────────────

def build_classifica(classifica: list, ultimo_agg: str, cfg: Stagione) -> str:
    if not classifica:
        body = '<section class="card"><p>Classifica non disponibile.</p></section>'
        return page_shell("Classifica", body, "classifica", ultimo_agg, cfg)

    righe = ""
    for r in classifica:
        is_olimpia = SQUADRA_MONITORATA.lower() in r["squadra"].lower()
        row_cls = ' class="olimpia-row"' if is_olimpia else ""
        badge = ' <span class="badge">★</span>' if is_olimpia else ""

        qs = r.get("quoziente_set")
        qp = r.get("quoziente_punti")
        qs_str = "∞" if qs is None else f"{qs:.3f}"
        qp_str = "∞" if qp is None else f"{qp:.3f}"

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
  <h2>Classifica completa — {cfg.girone_label}</h2>
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

    return page_shell("Classifica", body, "classifica", ultimo_agg, cfg)


# ── partite individuali ───────────────────────────────────────────────────────

def _storico_avversario(avversario: str, partite: list, escludi_id: str) -> str:
    """Costruisce la tabella con lo storico delle partite dell'avversario."""
    giocate = [
        p for p in partite
        if p.get("giocata") and p["id"] != escludi_id
        and (avversario.lower() in p["squadra_casa"].lower()
             or avversario.lower() in p["squadra_ospite"].lower())
    ]
    if not giocate:
        return '<p class="nota">Nessuna partita giocata dall\'avversario finora.</p>'

    righe = ""
    for p in giocate:
        casa_nome = p["squadra_casa"]
        ospite_nome = p["squadra_ospite"]
        sv_casa = p["risultato"]["set_vinti_casa"]
        sv_ospite = p["risultato"]["set_vinti_ospite"]
        e_casa = avversario.lower() in casa_nome.lower()
        avv_sv = sv_casa if e_casa else sv_ospite
        opp_sv = sv_ospite if e_casa else sv_casa
        esito_cls = "vittoria" if avv_sv > opp_sv else "sconfitta"
        esito_txt = "V" if avv_sv > opp_sv else "S"
        set_c = p["risultato"]["set_casa"]
        set_o = p["risultato"]["set_ospite"]
        set_str = ", ".join(f"{a}-{b}" for a, b in zip(set_c, set_o))
        is_olimpia_row = (SQUADRA_MONITORATA.lower() in casa_nome.lower()
                          or SQUADRA_MONITORATA.lower() in ospite_nome.lower())
        row_cls = ' class="olimpia-row"' if is_olimpia_row else ""
        casa_cls = " olimpia" if SQUADRA_MONITORATA.lower() in casa_nome.lower() else ""
        ospite_cls = " olimpia" if SQUADRA_MONITORATA.lower() in ospite_nome.lower() else ""
        righe += f"""<tr{row_cls}>
  <td class="data">{fmt_data(p['data'])}</td>
  <td class="team-name{casa_cls}">{casa_nome}</td>
  <td class="vs">vs</td>
  <td class="team-name{ospite_cls}">{ospite_nome}</td>
  <td class="storico-score">{sv_casa}-{sv_ospite}</td>
  <td><small class="set-dettaglio">{set_str}</small></td>
  <td><span class="esito {esito_cls}">{esito_txt}</span></td>
</tr>"""

    return f"""<div class="table-scroll">
  <table class="calendario-table">
    <thead>
      <tr>
        <th>Data</th>
        <th colspan="3">Partita</th>
        <th>Set</th>
        <th>Dettaglio</th>
        <th>Esito</th>
      </tr>
    </thead>
    <tbody>{righe}</tbody>
  </table>
</div>"""


def build_partita(partita: dict, partite: list, formazioni: dict, ultimo_agg: str, cfg: Stagione) -> str:
    pid = partita["id"]
    casa = partita["squadra_casa"]
    ospite = partita["squadra_ospite"]
    is_casa = partita.get("olimpia_pb_casa", False)
    avversario = ospite if is_casa else casa
    olimpia_cls = "olimpia" if True else ""

    data_str = fmt_data(partita["data"])
    ora_str = partita.get("ora", "--:--")
    palestra = partita.get("palestra", "")
    luogo = fmt_luogo(partita)

    titolo = f"{casa} vs {ospite}"

    if partita.get("giocata") and partita.get("risultato"):
        # ── Partita giocata ────────────────────────────────────────────────
        ris = partita["risultato"]
        sv_c = ris["set_vinti_casa"]
        sv_o = ris["set_vinti_ospite"]
        set_c = ris.get("set_casa", [])
        set_o = ris.get("set_ospite", [])
        set_detail = " &nbsp;|&nbsp; ".join(f"<b>{a}</b>-{b}" if a > b else f"{a}-<b>{b}</b>"
                                            for a, b in zip(set_c, set_o))

        olimpia_vince = (is_casa and sv_c > sv_o) or (not is_casa and sv_o > sv_c)
        esito_cls = "vittoria" if olimpia_vince else "sconfitta"
        esito_txt = "VITTORIA" if olimpia_vince else "SCONFITTA"

        foto = formazioni.get(pid, {}).get("foto") if cfg.foto_partite else None
        if foto:
            foto_html = f'<img src="{foto}" alt="Foto partita {titolo}" class="foto-partita">'
        elif cfg.foto_partite:
            foto_html = """<div class="foto-placeholder">
    <span class="foto-icon">📷</span>
    <p>Foto della partita non ancora disponibile</p>
  </div>"""
        else:
            foto_html = ""

        formazione = formazioni.get(pid, {}).get("giocatori", [])
        if formazione:
            righe_form = "".join(
                f'<tr><td class="maglia">{g.get("numero","")}</td><td class="team-name">{g.get("nome","")}</td></tr>'
                for g in sorted(formazione, key=lambda x: x.get("nome", ""))
            )
            tabella_form = f"""<div class="table-scroll">
  <table class="formazione-table">
    <thead><tr><th>#</th><th>Giocatore</th></tr></thead>
    <tbody>{righe_form}</tbody>
  </table>
</div>"""
        else:
            tabella_form = '<p class="nota">Formazione non ancora disponibile.</p>'

        if cfg.foto_partite:
            sezione_formazione = f"""<section class="card">
  <h2>Foto &amp; Formazione</h2>
  <div class="foto-formazione-grid">
    <div class="foto-col">{foto_html}</div>
    <div class="form-col">
      <h3 class="form-subtitle">Formazione Olimpia PB</h3>
      {tabella_form}
    </div>
  </div>
</section>"""
        else:
            sezione_formazione = f"""<section class="card">
  <h2>Formazione Olimpia PB</h2>
  {tabella_form}
</section>"""

        body = f"""
<section class="card">
  <a href="../calendario.html" class="back-link">← Torna al calendario</a>
  <h2>{titolo}</h2>
  <div class="partita-meta">{data_str}</div>
  <div class="risultato-hero {esito_cls}">
    <div class="score-principale">{sv_c} – {sv_o}</div>
    <div class="esito-label">{esito_txt}</div>
    <div class="score-set">{set_detail}</div>
  </div>
</section>

{sezione_formazione}"""
    else:
        # ── Partita futura ─────────────────────────────────────────────────
        storico_html = _storico_avversario(avversario, partite, pid)
        luogo_html = f'<div class="match-venue">📍 {palestra}</div><div class="match-venue">🗺 {luogo}</div>' if luogo else (f'<div class="match-venue">📍 {palestra}</div>' if palestra else "")
        casa_cls = " olimpia" if is_casa else ""
        ospite_cls = "" if is_casa else " olimpia"

        body = f"""
<section class="card">
  <a href="../calendario.html" class="back-link">← Torna al calendario</a>
  <h2>Prossima partita</h2>
  <div class="match-card olimpia-match">
    <div class="match-date">{data_str} ore {ora_str}</div>
    <div class="match-teams">
      <span class="team{casa_cls}">{casa}</span>
      <span class="vs">vs</span>
      <span class="team{ospite_cls}">{ospite}</span>
    </div>
    {luogo_html}
  </div>
</section>

<section class="card">
  <h2>Storico avversario: {avversario}</h2>
  {storico_html}
</section>"""

    return page_shell(titolo, body, "calendario", ultimo_agg, cfg, depth=1)


def build_partite_pages(partite: list, formazioni: dict, ultimo_agg: str, cfg: Stagione) -> int:
    olimpia_partite = [p for p in partite if p.get("olimpia_pb_gioca")]
    partite_dir = cfg.out_dir / "partite"
    fotos_dir = partite_dir / "fotos"
    partite_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for p in olimpia_partite:
        pid = p["id"]

        # Merge: dati manuali da formazioni.json + auto-rilevamento foto per filename
        form = dict(formazioni.get(pid, {}))
        if cfg.foto_partite and not form.get("foto"):
            for ext in ("jpg", "jpeg", "png", "webp"):
                if (fotos_dir / f"{pid}.{ext}").exists():
                    form["foto"] = f"fotos/{pid}.{ext}"
                    log(f"  foto auto-rilevata: {pid}.{ext}")
                    break

        html = build_partita(p, partite, {**formazioni, pid: form}, ultimo_agg, cfg)
        path = partite_dir / f"{pid}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
    return count


# ── main ──────────────────────────────────────────────────────────────────────

def build_stagione(cfg: Stagione) -> tuple:
    dati_partite = load_json(cfg.data_dir / "partite.json")
    dati_classifica = load_json(cfg.data_dir / "classifica.json")
    dati_formazioni = load_json(cfg.data_dir / "formazioni.json")

    partite = dati_partite.get("partite", [])
    classifica = dati_classifica.get("classifica", [])
    formazioni = dati_formazioni.get("formazioni", {})

    ultimo_agg = fmt_ts(dati_partite.get("ultimo_aggiornamento") or dati_classifica.get("ultimo_aggiornamento"))

    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    pages = {
        "index.html": build_index(partite, classifica, ultimo_agg, cfg),
        "calendario.html": build_calendario(partite, ultimo_agg, cfg),
        "classifica.html": build_classifica(classifica, ultimo_agg, cfg),
    }
    for filename, html in pages.items():
        path = cfg.out_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"Generato: {path}")

    n_partite = build_partite_pages(partite, formazioni, ultimo_agg, cfg)
    log(f"[{cfg.anno}] generate {n_partite} pagine partita in {cfg.out_dir / 'partite'}")
    return len(pages), n_partite


def main() -> int:
    log("=== build_site.py avviato ===")
    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "assets").mkdir(exist_ok=True)

    tot_pagine = tot_partite = 0
    for cfg in [CORRENTE, *ARCHIVIO]:
        n_pagine, n_partite = build_stagione(cfg)
        tot_pagine += n_pagine
        tot_partite += n_partite

    append_log("OK", f"generate {tot_pagine} pagine HTML + {tot_partite} pagine partita")
    log("=== build_site.py completato ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
