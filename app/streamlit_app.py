"""FalaNMT — aplikacja do screeningu zalewu z NMT."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import folium
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib import cm
from pyproj import Transformer
from streamlit_folium import st_folium

from floodnmt.constants import DISCLAIMER_PL, ISOK_DEPTH_LABELS
from floodnmt.dem import load_dem
from floodnmt.hydrology import derive_hydrology
from floodnmt.inundation import depth_summary, inundate_connected, inundate_hand
from floodnmt.parcels import load_parcels, rasterize_parcels, zonal_inundation
from floodnmt.pipeline import analyze
from floodnmt.viz import _hillshade

DATA = ROOT / "data" / "nysa_klodzka"
DEMO_DEM = DATA / "nmt_1m_klodzko.tif"
DEMO_PARCELS = DATA / "dzialki_uldk.geojson"

st.set_page_config(
    page_title="FalaNMT — Nysa Kłodzka",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');

:root {
  --ink: #14212b;
  --muted: #5a6b78;
  --paper: #eef3f6;
  --card: #ffffff;
  --line: #c9d6df;
  --water: #0b6e99;
  --water-deep: #084c6b;
  --sand: #d9e7ef;
  --warn: #9a3412;
  --warn-bg: #fff4e8;
  --ok: #0f766e;
}

html, body, [class*="css"] {
  font-family: "DM Sans", "Segoe UI", sans-serif;
  color: var(--ink);
}

.stApp {
  background:
    radial-gradient(1200px 500px at 10% -10%, #cfe4ef 0%, transparent 55%),
    linear-gradient(180deg, #e7eef3 0%, #f4f7f9 40%, #eef3f6 100%);
  color: var(--ink);
}

.block-container {
  padding-top: 1.2rem;
  padding-bottom: 2.5rem;
  max-width: 1280px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0f3a4f 0%, #0b2c3d 55%, #0a2433 100%);
  border-right: 1px solid #0a2030;
}
section[data-testid="stSidebar"] * {
  color: #e8f1f6 !important;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span {
  color: #d7e6ef !important;
}
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] [data-testid="stCaption"] {
  color: #9fbecf !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea {
  background: rgba(255,255,255,0.08) !important;
  color: #f4fafc !important;
  border-color: rgba(255,255,255,0.18) !important;
}

h1, h2, h3, h4 {
  font-family: "Fraunces", Georgia, serif !important;
  color: var(--ink) !important;
  letter-spacing: -0.02em;
}

.hero {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 1.2rem;
  align-items: end;
  margin-bottom: 1rem;
}
.brand {
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(2.1rem, 3.5vw, 3rem);
  font-weight: 700;
  color: var(--water-deep);
  line-height: 1.05;
  margin: 0;
}
.brand span {
  color: var(--water);
}
.lede {
  color: var(--muted);
  font-size: 1.05rem;
  max-width: 42rem;
  margin: 0.55rem 0 0;
  line-height: 1.45;
}
.pill-row { display:flex; flex-wrap:wrap; gap:0.45rem; margin-top:0.85rem; }
.pill {
  background: var(--sand);
  color: var(--water-deep);
  border: 1px solid #b7cedb;
  border-radius: 999px;
  padding: 0.28rem 0.7rem;
  font-size: 0.82rem;
  font-weight: 500;
}
.disclaimer {
  background: var(--warn-bg);
  border: 1px solid #f0c9a8;
  border-left: 5px solid var(--warn);
  padding: 0.85rem 1rem;
  border-radius: 0 10px 10px 0;
  color: #7c2d12;
  margin: 0.8rem 0 1.1rem;
  line-height: 1.4;
}
.help-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.9rem 1rem;
  box-shadow: 0 1px 0 rgba(20,33,43,0.04);
}
.help-card h4 {
  margin: 0 0 0.35rem;
  font-size: 1rem;
  color: var(--water-deep) !important;
}
.help-card p { margin: 0; color: var(--muted); font-size: 0.92rem; line-height: 1.4; }
.metric-strip {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.7rem;
  margin: 0.4rem 0 1rem;
}
.metric {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.85rem 0.95rem;
  min-height: 88px;
}
.metric .k {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
  margin-bottom: 0.25rem;
}
.metric .v {
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.55rem;
  color: var(--water-deep);
  line-height: 1.1;
}
.metric .h { font-size: 0.78rem; color: var(--muted); margin-top: 0.25rem; }
.legend {
  display: flex; flex-wrap: wrap; gap: 0.6rem 1rem;
  font-size: 0.85rem; color: var(--muted); margin: 0.4rem 0 0.8rem;
}
.legend i {
  display:inline-block; width:12px; height:12px; border-radius:3px;
  margin-right:0.35rem; vertical-align: -1px;
}
div[data-testid="stTabs"] button {
  font-family: "DM Sans", sans-serif;
  font-weight: 600;
  color: var(--ink) !important;
}
div[data-testid="stExpander"] {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
}
.stButton > button[kind="primary"],
.stButton > button {
  background: linear-gradient(180deg, #0d7eae, #0b6e99) !important;
  color: white !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  padding: 0.55rem 1rem !important;
}
iframe { border-radius: 14px; border: 1px solid var(--line) !important; }
@media (max-width: 900px) {
  .hero { grid-template-columns: 1fr; }
  .metric-strip { grid-template-columns: 1fr 1fr; }
}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Liczenie HAND i sieci drenażu…")
def _hydrology(path: str, stream_km2: float):
    terrain = load_dem(path)
    hydro = derive_hydrology(terrain, stream_km2=stream_km2)
    return terrain, hydro


@st.cache_data(show_spinner=False)
def _parcels(path: str, dem_path: str, stream_km2: float):
    terrain, _ = _hydrology(dem_path, stream_km2)
    if not path:
        return None, None
    gdf = load_parcels(path, terrain)
    pid = rasterize_parcels(gdf, terrain)
    return gdf, pid


def _bounds_latlon(terrain):
    west, south, east, north = terrain.bounds
    tr = Transformer.from_crs(terrain.crs, 4326, always_xy=True)
    lon0, lat0 = tr.transform(west, south)
    lon1, lat1 = tr.transform(east, north)
    return [[lat0, lon0], [lat1, lon1]], [(lat0 + lat1) / 2, (lon0 + lon1) / 2]


def _overlay_rgba(depth: np.ndarray, vmax: float = 4.0) -> np.ndarray:
    finite = np.isfinite(depth) & (depth >= 0)
    t = np.clip(np.where(finite, depth / vmax, 0.0), 0, 1)
    rgba = cm.Blues(t)
    rgba[..., 3] = np.where(finite, 0.55 + 0.35 * t, 0.0)
    return (rgba * 255).astype(np.uint8)


def _depth(method: str, hydro, terrain, stage: float):
    if method == "hand":
        return inundate_hand(hydro.hand, stage), None
    wse = hydro.stream_z_median + stage
    return inundate_connected(terrain.elevation, hydro.streams, wse), wse


def main() -> None:
    st.markdown(
        """
<div class="hero">
  <div>
    <p class="brand">Fala<span>NMT</span></p>
    <p class="lede">
      Wgrywasz model wysokości terenu — dostajesz mapę, gdzie woda może wejść
      przy zadanym poziomie w korycie, oraz liczby dla konkretnych działek.
    </p>
    <div class="pill-row">
      <span class="pill">Pilotaż: Kłodzko · Nysa Kłodzka</span>
      <span class="pill">NMT 1 m GUGiK</span>
      <span class="pill">61 działek ULDK</span>
    </div>
  </div>
  <div class="help-card">
    <h4>W 10 sekund</h4>
    <p>
      Suwak po lewej = ile metrów wody ponad rzekę.<br/>
      Niebieskie na mapie = zalane.<br/>
      Tabela „Działki” = ile % działki jest mokre.
    </p>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="disclaimer"><strong>Ważne:</strong> {DISCLAIMER_PL}</div>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### Dane")
        source = st.radio(
            "Skąd wziąć teren?",
            ("Pilotaż: Kłodzko / Nysa Kłodzka", "Wgraj własny GeoTIFF/ASC"),
            help="Pilotaż = gotowy wycinek Kłodzka. Albo wgraj własny plik wysokości.",
        )
        uploaded = None
        parcels_upload = None
        dem_path = DEMO_DEM
        par_path: Path | None = DEMO_PARCELS
        if source.startswith("Wgraj"):
            uploaded = st.file_uploader("Plik wysokości NMT", type=["tif", "tiff", "asc"])
            parcels_upload = st.file_uploader(
                "Opcjonalnie: działki (GeoJSON / GPKG)",
                type=["geojson", "json", "gpkg"],
            )
            if uploaded is None:
                st.info("Najpierw wgraj plik NMT albo wróć do pilotażu.")
                st.stop()
            tmp = Path("/tmp/floodnmt_upload")
            tmp.mkdir(exist_ok=True)
            dem_path = tmp / uploaded.name
            dem_path.write_bytes(uploaded.getbuffer())
            if parcels_upload is not None:
                par_path = tmp / parcels_upload.name
                par_path.write_bytes(parcels_upload.getbuffer())
            else:
                par_path = None
        elif not DEMO_DEM.exists():
            st.error("Brak danych pilotażowych w data/nysa_klodzka/.")
            st.stop()

        st.markdown("### Model — co tu ruszać")
        method = st.selectbox(
            "Jak liczyć zalew?",
            ("hand", "connected"),
            format_func=lambda m: (
                "HAND — wysokość nad rzeką (zalecane)"
                if m == "hand"
                else "Wanna połączona — woda nie przechodzi przez wzgórze"
            ),
            help=(
                "HAND: komórka jest zalana, jeśli jest nisko względem najbliższego cieku. "
                "Wanna: woda rozlewa się tylko tam, dokąd da się dojść od rzeki bez wchodzenia na garb."
            ),
        )
        stream_km2 = st.slider(
            "Jak „gruba” ma być rzeka na mapie? [km²]",
            0.05,
            1.50,
            0.30,
            0.05,
            help=(
                "Mniejsza wartość = więcej drobnych rowów uznanych za ciek. "
                "Większa = tylko główna dolina. Na wycinku Kłodzka dobry start to ~0,3."
            ),
        )
        stage = st.slider(
            "Ile metrów wody ponad koryto?",
            0.0,
            6.0,
            2.0,
            0.1,
            help=(
                "To NIE jest „powódź stuletnia”. To po prostu: +1 m, +2 m, +3 m "
                "względem cieku odczytanego z modelu terenu."
            ),
        )
        st.caption("Tip: zacznij od 0,5 m, potem podnieś do 2–3 m i patrz, jak rośnie niebieski.")
        stages_report = st.multiselect(
            "Jakie poziomy zapisać w raporcie?",
            [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0],
            default=[0.5, 1.0, 2.0, 3.0],
            help="Używane dopiero gdy klikniesz przycisk generowania raportu na dole.",
        )
        with st.expander("Słowniczek (kliknij)"):
            st.markdown(
                """
**NMT** — mapa wysokości gruntu (jak szachownica z liczbami metrów n.p.m.).

**HAND** — ile metrów w górę jest dana działka względem najbliższego cieku.

**Stan w korycie** — o ile metrów „podnosisz wodę” w tej symulacji.

**Próg cieku** — od jakiej wielkości drenażu komórka jest uznana za rzekę/rów.
"""
            )

    terrain, hydro = _hydrology(str(dem_path), float(stream_km2))
    parcels, pid = _parcels(
        str(par_path) if par_path and par_path.exists() else "",
        str(dem_path),
        float(stream_km2),
    )

    depth, wse = _depth(method, hydro, terrain, float(stage))
    summary = depth_summary(depth, terrain.cell_area_m2)
    stats = terrain.stats()

    st.markdown(
        f"""
<div class="metric-strip">
  <div class="metric"><div class="k">Zalane teraz</div><div class="v">{summary['area_km2']:.3f} km²</div><div class="h">powierzchnia niebieskiego</div></div>
  <div class="metric"><div class="k">Głębokość średnia</div><div class="v">{summary['depth_mean_m']:.2f} m</div><div class="h">typowy słup wody</div></div>
  <div class="metric"><div class="k">Głębokość max</div><div class="v">{summary['depth_max_m']:.2f} m</div><div class="h">najgłębszy punkt</div></div>
  <div class="metric"><div class="k">Objętość</div><div class="v">{summary['volume_m3']/1e6:.2f} mln m³</div><div class="h">ile wody „w wannie”</div></div>
  <div class="metric"><div class="k">Rzędna cieku</div><div class="v">{hydro.stream_z_median:.0f} m</div><div class="h">mediana dna z NMT</div></div>
</div>
""",
        unsafe_allow_html=True,
    )

    if terrain.warnings:
        with st.expander("Ostrzeżenia walidacji NMT", expanded=True):
            for w in terrain.warnings:
                st.warning(w)

    tabs = st.tabs(["Mapa", "Działki", "Jak to działa", "Metodyka (krótko)"])

    with tabs[0]:
        st.markdown(
            """
<div class="legend">
  <span><i style="background:#2171b5"></i>niebieski = woda (ciemniej = głębiej)</span>
  <span><i style="background:#dc2626"></i>działka ≥50% zalana</span>
  <span><i style="background:#f59e0b"></i>działka 10–50%</span>
  <span><i style="background:#84cc16"></i>działka 1–10%</span>
  <span><i style="background:#64748b"></i>działka sucha</span>
</div>
""",
            unsafe_allow_html=True,
        )
        bounds, center = _bounds_latlon(terrain)
        m = folium.Map(location=center, zoom_start=15, tiles=None, control_scale=True)
        folium.TileLayer(
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr="© OpenStreetMap",
            name="OpenStreetMap",
        ).add_to(m)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="Ortofoto (Esri)",
            show=False,
        ).add_to(m)
        folium.raster_layers.ImageOverlay(
            image=_overlay_rgba(depth, vmax=max(3.0, summary["depth_max_m"] or 3)),
            bounds=bounds,
            opacity=0.9,
            name=f"Zalew {method} +{stage:g} m",
        ).add_to(m)
        if parcels is not None:
            zg = zonal_inundation(parcels, depth, terrain, parcel_id_raster=pid)

            def style(feat):
                pct = feat["properties"].get("flooded_pct") or 0
                if pct <= 0:
                    return {"fillOpacity": 0.04, "color": "#64748b", "weight": 1}
                return {
                    "fillColor": "#dc2626" if pct >= 50 else "#f59e0b" if pct >= 10 else "#84cc16",
                    "fillOpacity": 0.35,
                    "color": "#1f2937",
                    "weight": 1,
                }

            gj = zg.to_crs(4326)
            folium.GeoJson(
                gj.__geo_interface__,
                name="Działki",
                style_function=style,
                tooltip=folium.GeoJsonTooltip(
                    fields=[c for c in ["obreb", "numer", "flooded_pct", "depth_max_m"] if c in gj.columns],
                    aliases=["Obręb", "Nr", "Zalane %", "Gł. max m"],
                ),
            ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, height=620, use_container_width=True, returned_objects=[])
        if wse is not None:
            st.caption(
                f"Wanna połączona: woda stoi równo na wysokości **{wse:.2f} m n.p.m.** "
                f"(rzędna cieku + {stage:g} m) i nie przechodzi przez wzgórza."
            )
        else:
            st.caption(
                f"HAND: zalane jest wszystko, co leży nie wyżej niż **{stage:g} m** "
                "nad najbliższym ciekiem."
            )

    with tabs[1]:
        if parcels is None:
            st.info("Brak warstwy działek. W pilotażu są prawdziwe działki z Kłodzka.")
        else:
            zg = zonal_inundation(parcels, depth, terrain, parcel_id_raster=pid)
            view_cols = [
                c
                for c in [
                    "teryt_dzialki",
                    "obreb",
                    "numer",
                    "powierzchnia_m2",
                    "flooded_pct",
                    "flooded_m2",
                    "depth_mean_m",
                    "depth_max_m",
                    "z_min_m",
                ]
                if c in zg.columns
            ]
            table = pd.DataFrame(zg.drop(columns="geometry")[view_cols]).sort_values(
                "flooded_pct", ascending=False
            )
            rename = {
                "teryt_dzialki": "TERYT",
                "obreb": "Obręb",
                "numer": "Nr działki",
                "powierzchnia_m2": "Pole [m²]",
                "flooded_pct": "Zalane [%]",
                "flooded_m2": "Zalane [m²]",
                "depth_mean_m": "Gł. śr. [m]",
                "depth_max_m": "Gł. max [m]",
                "z_min_m": "Najniższy punkt [m n.p.m.]",
            }
            show = table.rename(columns={k: v for k, v in rename.items() if k in table.columns})
            st.dataframe(show, use_container_width=True, hide_index=True)
            n_hit = int((table["flooded_pct"] > 1).sum())
            st.success(
                f"Przy stanie **+{stage:g} m** zalanych w >1% jest **{n_hit} z {len(table)}** działek. "
                "Im wyżej w tabeli, tym bardziej narażona."
            )
            st.caption(
                "Procent liczymy z pikseli NMT na działce. Pole ewidencyjne to geometria ULDK. "
                f"Klasy głębokości jak na mapach ISOK (ale to nie ISOK): {' · '.join(ISOK_DEPTH_LABELS)}."
            )

    with tabs[2]:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Model terenu (NMT)")
            hs = _hillshade(terrain.elevation, terrain.cellsize_m)
            st.image(
                hs,
                caption=(
                    f"{Path(str(dem_path)).name} · komórka {stats['cellsize_m']:.1f} m · "
                    f"{stats['extent_km2']:.2f} km²"
                ),
                use_container_width=True,
            )
            st.markdown(
                """
**Co widzisz?** Ciemniej/jaśniej = cień na reliefie.  
To mapa wysokości gruntu — bez budynków i drzew.
"""
            )
        with col_b:
            st.subheader("HAND — „ile metrów nad rzeką”")
            hand_show = np.clip(np.nan_to_num(hydro.hand, nan=0), 0, 40)
            st.image(
                hand_show / 40.0,
                caption=(
                    f"Próg cieku {hydro.stream_threshold_km2:.2f} km² · "
                    f"{hydro.n_stream_cells} komórek sieci"
                ),
                use_container_width=True,
            )
            st.markdown(
                """
**Co widzisz?** Jaśniej = bliżej dna doliny / rzeki.  
Ciemniej = wysoko na stoku (bezpieczniej w tej metodzie).
"""
            )

        st.markdown(
            f"""
#### Prosty przepis

1. Bierzemy **NMT** (wysokość każdego metra kwadratowego).
2. Szukamy, gdzie spływa woda → rysujemy **ciek**.
3. Dla każdego punktu liczymy: *ile metrów wyżej jestem od cieku?* → to jest **HAND**.
4. Ty ustawiasz suwak **+h metrów**. Wszystko z HAND ≤ h malujemy na niebiesko.
5. Na działkach liczymy procent niebieskich pikseli.

**Aktualne ustawienia:** próg cieku **{hydro.stream_threshold_km2:.2f} km²**,  
rzędna cieku min {hydro.stream_z_min:.1f} / mediana {hydro.stream_z_median:.1f} m n.p.m.,  
NMT {stats['z_min']:.1f}–{stats['z_max']:.1f} m.
"""
        )
        d_hand, _ = _depth("hand", hydro, terrain, float(stage))
        d_con, _ = _depth("connected", hydro, terrain, float(stage))
        s_h = depth_summary(d_hand, terrain.cell_area_m2)
        s_c = depth_summary(d_con, terrain.cell_area_m2)
        st.info(
            f"Przy +{stage:g} m: **HAND = {s_h['area_km2']:.3f} km²**, "
            f"**wanna połączona = {s_c['area_km2']:.3f} km²**. "
            "Różnica = zagłębienia odcięte garbem albo inaczej podłączone do cieku."
        )

    with tabs[3]:
        st.markdown(
            """
### Po ludzku

To narzędzie odpowiada na pytanie:

> *Jeśli woda w rzece podniesie się o 1, 2 albo 3 metry względem terenu z NMT — które działki są nisko i mogą być mokre?*

Nie odpowiada na:

> *Czy to powódź stuletnia? Jak szybko woda dojdzie? Ile będzie ofiar?*

Na to są oficjalne mapy ISOK / Hydroportal i modele hydrauliczne.

### Co program robi krok po kroku

1. Sprawdza plik wysokości (czy to na pewno grunt, czy nie ma dziwnych dziur).
2. „Wyrównuje” małe zagłębienia, żeby woda miała dokąd spłynąć.
3. Rysuje sieć drenażu (ciek).
4. Liczy HAND albo wannę połączoną.
5. Maluje głębokość i liczy % na działkach.
6. W raporcie pokazuje też niepewność ±20 cm (błąd typowy NMT 1 m).

### Pilotaż

Kłodzko, Nysa Kłodzka. NMT 1 m z GUGiK. Działki z ULDK.  
Powodzie 1997 i 2024 są kontekstem historycznym — ten model ich nie odtwarza 1:1.

Więcej: pliki `README_PROSTY.md` i `docs/metodyka.md`.
"""
        )

    st.divider()
    out_dir = ROOT / "outputs" / "app_run"
    col_btn, col_tip = st.columns([1.2, 1])
    with col_btn:
        if st.button("Wygeneruj pełny raport (HTML + mapy + GeoJSON)", type="primary"):
            if not stages_report:
                st.error("Wybierz co najmniej jeden poziom do raportu (lewy panel).")
            else:
                with st.spinner("Zapisuję raport i pliki…"):
                    result = analyze(
                        dem_path,
                        out_dir,
                        method=method,
                        stages=tuple(float(s) for s in stages_report),
                        stream_km2=float(stream_km2),
                        parcels_path=par_path if par_path and par_path.exists() else None,
                        title="FalaNMT — raport z aplikacji",
                    )
                st.success(f"Gotowe: `{result.report_html}`")
                st.json(
                    {
                        "method": result.method,
                        "scenarios": [
                            {
                                "stage_m": s.stage_m,
                                "area_km2": round(s.summary["area_km2"], 3),
                                "depth_max_m": round(s.summary["depth_max_m"], 2),
                            }
                            for s in result.scenarios
                        ],
                    }
                )
    with col_tip:
        st.markdown(
            """
<div class="help-card">
  <h4>Na prezentację</h4>
  <p>
    Pokaż mapę przy 0,5 m i 3 m. Potem zakładkę „Działki”.
    Na koniec powiedz głośno: <em>to screening z NMT, nie mapa ISOK</em>.
  </p>
</div>
""",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
