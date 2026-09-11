"""Statystyki zalewu na działkach ewidencyjnych."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from shapely.geometry import mapping

from floodnmt.constants import ISOK_DEPTH_LABELS
from floodnmt.dem import Terrain
from floodnmt.inundation import classify_depth


def load_parcels(path: str | Path, terrain: Terrain) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.empty:
        raise ValueError("Plik działek jest pusty.")
    if gdf.crs is None:
        gdf = gdf.set_crs(terrain.crs)
    elif gdf.crs != terrain.crs:
        gdf = gdf.to_crs(terrain.crs)
    gdf = gdf.reset_index(drop=True)
    if "powierzchnia_m2" not in gdf.columns:
        gdf["powierzchnia_m2"] = gdf.geometry.area
    return gdf


def rasterize_parcels(parcels: gpd.GeoDataFrame, terrain: Terrain) -> np.ndarray:
    """Mapa identyfikatorów działek (1…n); 0 = poza działkami. Rasteryzacja raz na analizę."""
    shapes = []
    for i, geom in enumerate(parcels.geometry, start=1):
        if geom is None or geom.is_empty:
            continue
        shapes.append((mapping(geom), i))
    if not shapes:
        return np.zeros(terrain.shape, dtype=np.int32)
    return rasterize(
        shapes,
        out_shape=terrain.shape,
        transform=terrain.transform,
        fill=0,
        dtype=np.int32,
        all_touched=False,
    )


def zonal_inundation(
    parcels: gpd.GeoDataFrame,
    depth: np.ndarray,
    terrain: Terrain,
    parcel_id_raster: np.ndarray | None = None,
) -> gpd.GeoDataFrame:
    """Dla każdej działki: udział zalania, głębokości, klasy ISOK."""
    pid = parcel_id_raster if parcel_id_raster is not None else rasterize_parcels(parcels, terrain)
    cell_a = terrain.cell_area_m2
    classes = classify_depth(depth)
    n = len(parcels)
    ids = np.arange(1, n + 1)

    on = pid > 0
    n_all = np.bincount(pid[on], minlength=n + 1)[1:]
    z = np.where(np.isfinite(terrain.elevation), terrain.elevation, np.nan)
    # min z per parcel
    zmin = np.full(n, np.nan)
    for i in ids:
        sel = pid == i
        if sel.any():
            zmin[i - 1] = float(np.nanmin(z[sel]))

    wet = on & np.isfinite(depth) & (depth >= 0)
    n_wet = np.bincount(pid[wet], minlength=n + 1)[1:]
    # sum/max depth
    depth_sum = np.bincount(pid[wet], weights=depth[wet], minlength=n + 1)[1:]
    depth_max = np.zeros(n)
    p90 = np.zeros(n)
    class_m2 = np.zeros((n, 4))
    for i in ids:
        sel = (pid == i) & np.isfinite(depth) & (depth >= 0)
        if not sel.any():
            continue
        vals = depth[sel]
        depth_max[i - 1] = float(vals.max())
        p90[i - 1] = float(np.percentile(vals, 90))
        cls = classes[sel]
        for k in range(1, 5):
            class_m2[i - 1, k - 1] = float((cls == k).sum() * cell_a)

    mean = np.divide(depth_sum, n_wet, out=np.zeros(n), where=n_wet > 0)
    recs = {
        "parcel_ix": np.arange(n),
        "n_cells": n_all,
        "area_geom_m2": parcels.geometry.area.values,
        "area_raster_m2": n_all * cell_a,
        "flooded_m2": n_wet * cell_a,
        "flooded_pct": np.divide(100.0 * n_wet, n_all, out=np.zeros(n), where=n_all > 0),
        "depth_mean_m": mean,
        "depth_max_m": depth_max,
        "depth_p90_m": p90,
        "z_min_m": zmin,
    }
    for k, _lab in enumerate(ISOK_DEPTH_LABELS, start=1):
        recs[f"klasa_{k}_m2"] = class_m2[:, k - 1]

    stats = gpd.GeoDataFrame(recs)
    out = parcels.copy()
    for col in stats.columns:
        if col == "parcel_ix":
            continue
        out[col] = stats[col].values
    return out
