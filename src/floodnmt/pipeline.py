"""Pełny przebieg analizy: NMT → hydrologia → scenariusze → działki → raport."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio.features
from shapely.geometry import mapping, shape

from floodnmt.constants import (
    DEFAULT_STAGES_M,
    DEFAULT_STREAM_KM2,
    DISCLAIMER_PL,
    ISOK_DEPTH_LABELS,
)
from floodnmt.dem import Terrain, load_dem, write_geotiff
from floodnmt.hydrology import Hydrology, derive_hydrology
from floodnmt.inundation import depth_summary, inundate_connected, inundate_hand
from floodnmt.parcels import load_parcels, rasterize_parcels, zonal_inundation
from floodnmt.report import write_html, write_json
from floodnmt.uncertainty import uncertainty_envelope
from floodnmt.viz import save_classified, save_hand, save_overview, save_parcel_bars, save_uncertainty


@dataclass
class ScenarioResult:
    stage_m: float
    wse_m: float | None
    method: str
    summary: dict
    depth_path: str
    extent_path: str


@dataclass
class AnalysisResult:
    out_dir: Path
    method: str
    terrain_stats: dict
    hydro_meta: dict
    warnings: list[str]
    scenarios: list[ScenarioResult]
    report_html: Path | None = None
    report_json: Path | None = None
    parcel_tables: dict[str, Path] = field(default_factory=dict)
    disclaimer: str = DISCLAIMER_PL


def _vectorize_extent(depth: np.ndarray, terrain: Terrain, path: Path) -> Path:
    wet = (np.isfinite(depth) & (depth >= 0)).astype(np.uint8)
    if not wet.any():
        path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
        return path
    shapes = list(rasterio.features.shapes(wet, mask=wet.astype(bool), transform=terrain.transform))
    features = []
    for geom, val in shapes:
        if int(val) != 1:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"flooded": 1},
                "geometry": mapping(shape(geom)),
            }
        )
    fc = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": terrain.crs.to_string()}},
        "features": features,
    }
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fc), encoding="utf-8")
    return path


def _depth_for_stage(method: str, hydro: Hydrology, terrain: Terrain, stage_m: float) -> tuple[np.ndarray, float | None]:
    if method == "hand":
        return inundate_hand(hydro.hand, stage_m), None
    wse = hydro.stream_z_median + stage_m
    return inundate_connected(terrain.elevation, hydro.streams, wse), wse


def analyze(
    dem_path: str | Path,
    out_dir: str | Path,
    *,
    method: str = "hand",
    stages: tuple[float, ...] = DEFAULT_STAGES_M,
    stream_km2: float = DEFAULT_STREAM_KM2,
    parcels_path: str | Path | None = None,
    rmse_m: float | None = None,
    title: str | None = None,
) -> AnalysisResult:
    method = method.lower().strip()
    if method not in {"hand", "connected"}:
        raise ValueError("method musi być 'hand' albo 'connected'.")

    out = Path(out_dir)
    rasters = out / "rasters"
    vectors = out / "vectors"
    figures = out / "figures"
    for p in (rasters, vectors, figures):
        p.mkdir(parents=True, exist_ok=True)

    terrain: Terrain = load_dem(dem_path)
    hydro: Hydrology = derive_hydrology(terrain, stream_km2=stream_km2)
    rmse = float(rmse_m if rmse_m is not None else terrain.suggested_rmse_m())

    write_geotiff(rasters / "hand.tif", hydro.hand, terrain.transform, terrain.crs, tags={"LAYER": "HAND_m"})
    write_geotiff(
        rasters / "streams.tif",
        hydro.streams.astype(np.uint8),
        terrain.transform,
        terrain.crs,
        nodata=0,
        dtype="uint8",
        tags={"LAYER": "streams"},
    )

    save_hand(figures / "hand_nmt.png", terrain, hydro)

    depths_for_overview: dict[str, np.ndarray] = {}
    scenarios: list[ScenarioResult] = []
    parcel_gdfs = {}

    parcels = None
    parcel_ids = None
    if parcels_path:
        parcels = load_parcels(parcels_path, terrain)
        parcel_ids = rasterize_parcels(parcels, terrain)

    for stage in stages:
        depth, wse = _depth_for_stage(method, hydro, terrain, stage)
        tag = f"h{stage:g}m".replace(".", "p")
        tif = rasters / f"depth_{method}_{tag}.tif"
        write_geotiff(tif, depth, terrain.transform, terrain.crs, tags={"STAGE_M": str(stage), "METHOD": method})
        geojson = _vectorize_extent(depth, terrain, vectors / f"extent_{method}_{tag}.geojson")
        summary = depth_summary(depth, terrain.cell_area_m2)
        label = f"+{stage:g} m w korycie"
        depths_for_overview[label] = depth
        save_classified(
            figures / f"klasy_{method}_{tag}.png",
            terrain,
            depth,
            title=f"Klasy głębokości ISOK — {method.upper()} {label}",
        )
        env = uncertainty_envelope(method, hydro, terrain.elevation, stage, rmse)
        save_uncertainty(
            figures / f"niepewnosc_{method}_{tag}.png",
            terrain,
            env["agreement"],
            rmse,
            stage,
        )
        if parcels is not None:
            zg = zonal_inundation(parcels, depth, terrain, parcel_id_raster=parcel_ids)
            parcel_gdfs[label] = zg
            out_par = vectors / f"dzialki_{method}_{tag}.geojson"
            keep = [c for c in zg.columns if c != "geometry"]
            zg.to_file(out_par, driver="GeoJSON")
            save_parcel_bars(figures / f"dzialki_{method}_{tag}.png", zg, label)
            parcel_tables_path = out_par
        else:
            parcel_tables_path = None

        scenarios.append(
            ScenarioResult(
                stage_m=float(stage),
                wse_m=wse,
                method=method,
                summary=summary,
                depth_path=str(tif),
                extent_path=str(geojson),
            )
        )
        _ = parcel_tables_path

    save_overview(figures / f"przeglad_{method}.png", terrain, hydro, depths_for_overview, method)

    stats = terrain.stats()
    hydro_meta = {
        "stream_threshold_km2": hydro.stream_threshold_km2,
        "n_stream_cells": hydro.n_stream_cells,
        "stream_z_median_m": hydro.stream_z_median,
        "stream_z_min_m": hydro.stream_z_min,
        "rmse_m": rmse,
    }

    # tabela HTML z ostatniego (najwyższego) scenariusza
    table_html = "<p>Nie wczytano działek.</p>"
    parcel_paths: dict[str, Path] = {}
    if parcel_gdfs:
        last_label = list(parcel_gdfs.keys())[-1]
        df = parcel_gdfs[last_label]
        cols = [
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
            if c in df.columns
        ]
        show = df[cols].copy()
        for c in show.columns:
            if show[c].dtype.kind == "f":
                show[c] = show[c].map(lambda x: f"{x:.2f}")
        table_html = (
            f"<p>Scenariusz {last_label}. Klasy głębokości: "
            + ", ".join(ISOK_DEPTH_LABELS)
            + ".</p>"
            + show.to_html(index=False)
        )
        for lab, g in parcel_gdfs.items():
            parcel_paths[lab] = vectors / f"(patrz geojson {lab})"

    assumptions = [
        "NMT reprezentuje grunt (NMT), nie pokrycie (NMPT).",
        "Ciek wyznaczono z akumulacji spływu na wycinku rastra — to nie jest pełna zlewnia.",
        "HAND: komórka zalana, gdy wysokość nad najbliższym drenażem ≤ zadany stan w korycie.",
        "Wanna połączona: zwierciadło płaskie H = mediana rzędnej cieku + stan; zalew tylko komórek osiągalnych z sieci.",
        f"Niepewność: powtórzenie scenariusza przy H±{rmse:g} m (RMSE NMT).",
        "Mosty, wały i przepusty są takie, jakie zapisano w pikselach NMT (bez hydro-enforcement).",
    ]

    src_name = terrain.source_path.name if terrain.source_path else "pamięć"
    meta = {
        "Plik NMT": src_name,
        "CRS": terrain.crs.to_string(),
        "Komórka": f"{stats['cellsize_m']:.2f} m",
        "Zakres wysokości": f"{stats['z_min']:.2f} – {stats['z_max']:.2f} m",
        "Powierzchnia wycinka": f"{stats['extent_km2']:.2f} km²",
        "Metoda": method.upper(),
        "Próg cieku": f"{hydro.stream_threshold_km2:.3f} km² ({hydro.n_stream_cells} kom.)",
        "Mediana rzędnej cieku": f"{hydro.stream_z_median:.2f} m",
        "Stany w korycie": ", ".join(f"{s:g} m" for s in stages),
        "RMSE NMT": f"{rmse:.2f} m",
    }

    figures_spec = [
        {"src": "figures/hand_nmt.png", "caption": "NMT oraz raster HAND z siecią drenażu."},
        {"src": f"figures/przeglad_{method}.png", "caption": "Zasięg i głębokość dla zadanych stanów w korycie."},
    ]
    # dodaj klasy najwyższego stanu
    last = f"h{stages[-1]:g}m".replace(".", "p")
    figures_spec.append(
        {
            "src": f"figures/klasy_{method}_{last}.png",
            "caption": "Klasy głębokości analogiczne do MZP ISOK (to nie jest MZP).",
        }
    )
    figures_spec.append(
        {
            "src": f"figures/niepewnosc_{method}_{last}.png",
            "caption": "Rdzeń i brzeg niepewności wynikający z błędu wysokości NMT.",
        }
    )

    html_path = write_html(
        out / "raport.html",
        title=title or "Ocena zasięgu zalewu z NMT",
        meta=meta,
        warnings=terrain.warnings,
        assumptions=assumptions,
        figures=figures_spec,
        table_html=table_html,
    )

    payload = {
        "disclaimer": DISCLAIMER_PL,
        "method": method,
        "terrain": stats,
        "hydrology": hydro_meta,
        "warnings": terrain.warnings,
        "scenarios": [
            {
                "stage_m": s.stage_m,
                "wse_m": s.wse_m,
                "summary": {k: v for k, v in s.summary.items() if not str(k).endswith("_label")},
                "depth_tif": s.depth_path,
                "extent_geojson": s.extent_path,
            }
            for s in scenarios
        ],
    }
    json_path = write_json(out / "raport.json", payload)

    return AnalysisResult(
        out_dir=out,
        method=method,
        terrain_stats=stats,
        hydro_meta=hydro_meta,
        warnings=terrain.warnings,
        scenarios=scenarios,
        report_html=html_path,
        report_json=json_path,
        parcel_tables=parcel_paths,
    )
