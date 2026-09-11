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
  .stApp { background: #f3efe6; }
  h1, h2, h3 { font-family: "IBM Plex Sans", "Source Sans 3", sans-serif; color: #1f4e79; }
  .disclaimer { background:#fff7ed; border-left:4px solid #c2410c; padding:0.7rem 0.9rem; }
  div[data-testid="stMetric"] { background:white; border:1px solid #d7dee6; padding:0.6rem; }
  .block-container { padding-top: 1.1rem; }
</style>
""",
    unsafe_allow_html=True,
)


def _data_dir() -> Path:
    return DATA


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
    st.title("FalaNMT")
    st.caption(
        "Automatyczna ocena zasięgu wody z numerycznego modelu terenu. "
        "Pilotaż: Nysa Kłodzka w Kłodzku — NMT 1 m GUGiK, działki ULDK."
    )
    st.markdown(f'<div class="disclaimer">{DISCLAIMER_PL}</div>', unsafe_allow_html=True)

    with st.sidebar:
        st.header("Dane")
        source = st.radio(
            "Źródło NMT",
            ("Pilotaż: Kłodzko / Nysa Kłodzka", "Wgraj własny GeoTIFF/ASC"),
        )
        uploaded = None
        parcels_upload = None
        dem_path = DEMO_DEM
        par_path: Path | None = DEMO_PARCELS
        if source.startswith("Wgraj"):
            uploaded = st.file_uploader("NMT (GeoTIFF, ASC)", type=["tif", "tiff", "asc"])
            parcels_upload = st.file_uploader("Działki (GeoJSON, GPKG, SHP w ZIP nieobsługiwany)", type=["geojson", "json", "gpkg"])
            if uploaded is None:
                st.info("Wgraj raster NMT albo wróć do pilotażu Kłodzka.")
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

        st.header("Model")
        method = st.selectbox(
            "Metoda zasięgu",
            ("hand", "connected"),
            format_func=lambda m: "HAND — wysokość nad drenażem" if m == "hand" else "Wanna połączona hydrologicznie",
        )
        stream_km2 = st.slider("Próg cieku (akumulacja lokalna) [km²]", 0.05, 1.50, 0.30, 0.05)
        stage = st.slider("Stan w korycie ponad dno/HAND [m]", 0.0, 6.0, 2.0, 0.1)
        st.caption("To nie jest woda stuletnia. To metrów słupa wody względem cieku z NMT.")
        stages_report = st.multiselect(
            "Stany do raportu",
            [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0],
            default=[0.5, 1.0, 2.0, 3.0],
        )

    terrain, hydro = _hydrology(str(dem_path), float(stream_km2))
    parcels, pid = _parcels(str(par_path) if par_path and par_path.exists() else "", str(dem_path), float(stream_km2))

    depth, wse = _depth(method, hydro, terrain, float(stage))
    summary = depth_summary(depth, terrain.cell_area_m2)
    stats = terrain.stats()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Zalew", f"{summary['area_km2']:.3f} km²")
    c2.metric("Głębokość śr.", f"{summary['depth_mean_m']:.2f} m")
    c3.metric("Głębokość max", f"{summary['depth_max_m']:.2f} m")
    c4.metric("Objętość", f"{summary['volume_m3']/1e6:.2f} mln m³")
    c5.metric("Mediana cieku", f"{hydro.stream_z_median:.1f} m n.p.m.")

    if terrain.warnings:
        with st.expander("Ostrzeżenia walidacji NMT", expanded=True):
            for w in terrain.warnings:
                st.warning(w)

    tabs = st.tabs(["Mapa", "Działki", "HAND i metoda", "Metodyka"])

    with tabs[0]:
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
            gj = zg.to_crs(4326)
            def style(feat):
                pct = feat["properties"].get("flooded_pct") or 0
                if pct <= 0:
                    return {"fillOpacity": 0.05, "color": "#64748b", "weight": 1}
                return {
                    "fillColor": "#dc2626" if pct >= 50 else "#f59e0b" if pct >= 10 else "#84cc16",
                    "fillOpacity": 0.35,
                    "color": "#1f2937",
                    "weight": 1,
                }
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
        st_folium(m, height=560, use_container_width=True, returned_objects=[])
        if wse is not None:
            st.caption(f"Wanna połączona: płaskie zwierciadło H = {wse:.2f} m n.p.m. (mediana cieku + stan).")
        else:
            st.caption("HAND: zalane komórki z wysokością nad najbliższym ciekiem ≤ zadany stan.")

    with tabs[1]:
        if parcels is None:
            st.info("Brak warstwy działek. W pilotażu są rzeczywiste geometrie ULDK z Kłodzka.")
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
            st.dataframe(table, use_container_width=True, hide_index=True)
            n_hit = int((table["flooded_pct"] > 1).sum())
            st.caption(
                f"{n_hit} z {len(table)} działek ma >1% powierzchni w zalewie przy stanie +{stage:g} m. "
                "Pole ewidencyjne (powierzchnia_m2) pochodzi z geometrii ULDK; procent z pikseli NMT."
            )
            st.write("Klasy głębokości (jak MZP, ale to nie MZP): " + " · ".join(ISOK_DEPTH_LABELS))

    with tabs[2]:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("NMT")
            hs = _hillshade(terrain.elevation, terrain.cellsize_m)
            st.image(hs, caption=f"{Path(str(dem_path)).name}  |  {stats['cellsize_m']:.1f} m  |  {stats['extent_km2']:.2f} km²", use_container_width=True)
        with col_b:
            st.subheader("HAND [m]")
            hand_show = np.clip(np.nan_to_num(hydro.hand, nan=0), 0, 40)
            st.image(hand_show / 40.0, caption=f"Próg cieku {hydro.stream_threshold_km2:.2f} km², {hydro.n_stream_cells} komórek sieci", use_container_width=True)
        st.markdown(
            f"""
**Parametry hydrologii wycinka**

- próg cieku: **{hydro.stream_threshold_km2:.3f} km²** (akumulacja *na rastrze*, nie zlewnia Nysy)
- komórki sieci: **{hydro.n_stream_cells}**
- rzędna cieku: min {hydro.stream_z_min:.2f} m, mediana {hydro.stream_z_median:.2f} m
- NMT: {stats['z_min']:.2f}–{stats['z_max']:.2f} m n.p.m., komórka {stats['cellsize_m']:.2f} m
"""
        )
        d_hand, _ = _depth("hand", hydro, terrain, float(stage))
        d_con, _ = _depth("connected", hydro, terrain, float(stage))
        s_h = depth_summary(d_hand, terrain.cell_area_m2)
        s_c = depth_summary(d_con, terrain.cell_area_m2)
        st.write(
            f"Przy +{stage:g} m HAND zalewa **{s_h['area_km2']:.3f} km²**, wanna połączona **{s_c['area_km2']:.3f} km²**. "
            "Różnica to misy bez połączenia z korytem oraz inna geometria spływu D8."
        )

    with tabs[3]:
        st.markdown(
            """
### Co jest liczone

1. **NMT** jest walidowany (CRS, NoData, chropowatość sugerująca NMPT).
2. Depresje są wypełniane (Wang & Liu 2006), liczony jest spływ D8 i akumulacja.
3. Ciek = komórki o akumulacji ≥ próg. Na wycinku 2×2 km to *lokalny* drenaż, nie zlewnia Nysy Kłodzkiej.
4. **HAND** (Nobre et al. 2011/2016): wysokość komórki nad najbliższym ciekiem wzdłuż ścieżki spływu.
   Zalanie: `HAND ≤ h`. Głębokość: `h − HAND`.
5. **Wanna połączona**: płaskie zwierciadło `H = mediana(z cieku) + h`. BFS z sieci — garb terenu odcina misę.
6. Klasy głębokości jak na MZP ISOK: &lt;0,5 / 0,5–2 / 2–4 / &gt;4 m.
7. Niepewność w raporcie plikowym: `h ± 0,20 m` (RMSE NMT 1 m ALS).

### Pilotaż

Kłodzko, dolina Nysy Kłodzkiej. NMT 1 m z WCS GUGiK (układ PL-1992, wysokości PL-KRON86-NH).
Działki z usługi ULDK. Powodzie 1997 i 2024 są kontekstem, nie kalibracją — ten model nie odtwarza hydrogramu.

Pełna metodyka: plik `docs/metodyka.md` w repozytorium.
"""
        )

    st.divider()
    out_dir = ROOT / "outputs" / "app_run"
    if st.button("Wygeneruj pełny raport inżynierski (HTML + GeoTIFF + GeoJSON)", type="primary"):
        if not stages_report:
            st.error("Wybierz co najmniej jeden stan do raportu.")
        else:
            with st.spinner("Zapis rastra, wektorów, figur i raportu…"):
                result = analyze(
                    dem_path,
                    out_dir,
                    method=method,
                    stages=tuple(float(s) for s in stages_report),
                    stream_km2=float(stream_km2),
                    parcels_path=par_path if par_path and par_path.exists() else None,
                    title="FalaNMT — raport z aplikacji",
                )
            st.success(f"Zapisano {result.report_html}")
            st.write("Otwórz `outputs/app_run/raport.html` albo pobierz JSON:")
            st.json(
                {
                    "method": result.method,
                    "scenarios": [
                        {"stage_m": s.stage_m, "area_km2": s.summary["area_km2"], "depth_max_m": s.summary["depth_max_m"]}
                        for s in result.scenarios
                    ],
                }
            )


if __name__ == "__main__":
    main()
