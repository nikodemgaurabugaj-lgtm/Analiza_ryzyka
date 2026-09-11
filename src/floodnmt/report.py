"""Raport inżynierski HTML + JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

from floodnmt.constants import DISCLAIMER_PL

_TEMPLATE = Template(
    """
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8"/>
<title>{{ title }}</title>
<style>
  :root { --ink:#1b2430; --muted:#5c6b7a; --line:#d7dee6; --acc:#1f4e79; --bg:#f6f3ee; }
  body { font-family: "Source Serif 4", "Libertinus Serif", Georgia, serif; color:var(--ink);
         max-width: 980px; margin: 2rem auto; padding: 0 1.2rem 3rem; background: var(--bg); line-height: 1.45; }
  h1,h2,h3 { font-family: "IBM Plex Sans", "Source Sans 3", system-ui, sans-serif; color:var(--acc); }
  h1 { font-size: 1.7rem; margin-bottom: .2rem; }
  .sub { color: var(--muted); margin-top: 0; }
  .warn { border-left: 4px solid #b45309; background: #fff7ed; padding: .8rem 1rem; margin: 1.2rem 0; }
  .meta { display:grid; grid-template-columns: 1fr 1fr; gap:.3rem 1.5rem; font-size:.95rem; }
  table { border-collapse: collapse; width:100%; font-size:.82rem; background:white; }
  th,td { border:1px solid var(--line); padding:.35rem .45rem; text-align:right; }
  th:first-child, td:first-child { text-align:left; }
  th { background:#e8eef4; font-family: "IBM Plex Sans", sans-serif; }
  img { max-width:100%; height:auto; border:1px solid var(--line); background:white; }
  figure { margin: 1.1rem 0 1.4rem; }
  figcaption { font-size:.85rem; color:var(--muted); margin-top:.35rem; }
  footer { margin-top:2rem; font-size:.8rem; color:var(--muted); }
</style>
</head>
<body>
<h1>{{ title }}</h1>
<p class="sub">Automatyczna ocena zasięgu zalewu z numerycznego modelu terenu — FalaNMT 1.0</p>
<p>{{ generated }}</p>

<div class="warn"><strong>Zastrzeżenie.</strong> {{ disclaimer }}</div>

<h2>1. Dane wejściowe i metoda</h2>
<div class="meta">
  {% for k,v in meta.items() %}
  <div><strong>{{ k }}</strong></div><div>{{ v }}</div>
  {% endfor %}
</div>

{% if warnings %}
<h3>Ostrzeżenia walidacji NMT</h3>
<ul>{% for w in warnings %}<li>{{ w }}</li>{% endfor %}</ul>
{% endif %}

<h2>2. Założenia</h2>
<ul>
  {% for a in assumptions %}<li>{{ a }}</li>{% endfor %}
</ul>

<h2>3. Wyniki — zasięg i głębokość</h2>
{% for fig in figures %}
<figure>
  <img src="{{ fig.src }}" alt="{{ fig.caption }}"/>
  <figcaption>{{ fig.caption }}</figcaption>
</figure>
{% endfor %}

<h2>4. Ocena działek</h2>
<p>Metryki liczone na pikselach NMT przecinających geometrię działki (ULDK / wgrany wektor).
Procent odnosi się do komórek rastra na działce, nie do pola ewidencyjnego z KW.</p>
{{ table_html | safe }}

<h2>5. Czego model nie robi</h2>
<ul>
  <li>Nie liczy przepływu Q₁₀ / Q₁ / Q₀,₂ i nie odtwarza map ISOK.</li>
  <li>Nie uwzględnia wałów, mostów, przepustów i kanalizacji (chyba że są w NMT).</li>
  <li>Nie podaje prędkości, czasu dojścia fali ani strat.</li>
  <li>HAND źródłuje zalew z najbliższego cieku — ujścia i kilka rzek jednocześnie są uproszczone.</li>
</ul>

<footer>
Wygenerowano przez FalaNMT. NMT: GUGiK, działki: ULDK (jeśli użyto). Literatura: Nobre et al. 2011/2016;
Barnes et al. 2014; Wang &amp; Liu 2006. Oficjalne mapy: Hydroportal ISOK.
</footer>
</body>
</html>
"""
)


def write_json(path: Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_html(
    path: Path,
    *,
    title: str,
    meta: dict[str, str],
    warnings: list[str],
    assumptions: list[str],
    figures: list[dict[str, str]],
    table_html: str,
) -> Path:
    path = Path(path)
    html = _TEMPLATE.render(
        title=title,
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        disclaimer=DISCLAIMER_PL,
        meta=meta,
        warnings=warnings,
        assumptions=assumptions,
        figures=figures,
        table_html=table_html,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
