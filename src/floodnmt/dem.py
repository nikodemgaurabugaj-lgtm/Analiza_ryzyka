"""Wczytywanie, walidacja i metadane numerycznego modelu terenu."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject
from scipy import ndimage

from floodnmt.constants import EPSG_PL1992, MAX_CELLS, NMT_RMSE_1M_M, NMT_RMSE_5M_M


@dataclass
class Terrain:
    elevation: np.ndarray
    transform: Affine
    crs: CRS
    source_path: Path | None = None
    tags: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def shape(self) -> tuple[int, int]:
        return self.elevation.shape

    @property
    def cellsize_m(self) -> float:
        return float(abs(self.transform.a))

    @property
    def cell_area_m2(self) -> float:
        return float(abs(self.transform.a * self.transform.e))

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        r, c = self.shape
        left, top = self.transform * (0, 0)
        right, bottom = self.transform * (c, r)
        return (min(left, right), min(bottom, top), max(left, right), max(bottom, top))

    @property
    def valid_mask(self) -> np.ndarray:
        return np.isfinite(self.elevation)

    def stats(self) -> dict[str, float]:
        z = self.elevation[self.valid_mask]
        return {
            "rows": float(self.shape[0]),
            "cols": float(self.shape[1]),
            "cellsize_m": self.cellsize_m,
            "n_valid": float(z.size),
            "z_min": float(z.min()) if z.size else float("nan"),
            "z_max": float(z.max()) if z.size else float("nan"),
            "z_mean": float(z.mean()) if z.size else float("nan"),
            "extent_km2": float(self.valid_mask.sum() * self.cell_area_m2 / 1e6),
        }

    def suggested_rmse_m(self) -> float:
        return NMT_RMSE_1M_M if self.cellsize_m <= 1.5 else NMT_RMSE_5M_M


def _as_nodata_array(data: np.ndarray, nodata) -> np.ndarray:
    z = data.astype(np.float32, copy=True)
    if nodata is not None and not (isinstance(nodata, float) and np.isnan(nodata)):
        z[z == nodata] = np.nan
    z[~np.isfinite(z)] = np.nan
    # Częsty błąd eksportu: NoData zapisane jako ekstremum.
    z[(z < -500) | (z > 9000)] = np.nan
    return z


def _roughness_nmpt_warning(z: np.ndarray) -> str | None:
    """NMPT (budynki, drzewa) ma dużo lokalnej chropowatości względem NMT."""
    valid = np.isfinite(z)
    if valid.mean() < 0.5:
        return None
    filled = np.where(valid, z, np.nanmean(z))
    local_std = ndimage.generic_filter(filled, np.nanstd, size=5, mode="nearest")
    share = float((local_std[valid] > 2.5).mean())
    if share > 0.12:
        return (
            f"Wysoka chropowatość lokalna ({share:.0%} komórek z σ₅ₓ₅ > 2,5 m). "
            "Raster wygląda na NMPT (budynki/drzewa), nie NMT. Zalewanie po NMPT "
            "zostawia fałszywe bariery."
        )
    return None


def load_dem(path: str | Path, *, to_epsg: int | None = EPSG_PL1992) -> Terrain:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Nie znaleziono NMT: {path}")

    warnings: list[str] = []
    with rasterio.open(path) as src:
        if src.count < 1:
            raise ValueError("Plik nie zawiera pasma wysokości.")
        tags = {k: str(v) for k, v in src.tags().items()}
        crs = src.crs
        if crs is None:
            warnings.append("Brak CRS w pliku — przyjęto EPSG:2180 (PL-1992).")
            crs = CRS.from_epsg(EPSG_PL1992)

        data = src.read(1)
        z = _as_nodata_array(data, src.nodata)
        transform = src.transform
        n_cells = int(z.size)
        if n_cells > MAX_CELLS:
            raise ValueError(
                f"Raster ma {n_cells:,} komórek (limit {MAX_CELLS:,}). "
                "Wytnij mniejszy obszar wokół działki (bufor 1–3 km)."
            )
        if not np.isfinite(z).any():
            raise ValueError("Wszystkie komórki to NoData — sprawdź format i nodata.")

        if crs.is_geographic:
            warnings.append(
                "CRS geograficzny (stopnie). Do metryk powierzchni i HAND raster "
                f"zostanie przeliczony do EPSG:{to_epsg}."
            )
            if to_epsg:
                z, transform, crs = _reproject_to(z, transform, crs, to_epsg)

        elif to_epsg and crs.to_epsg() not in (to_epsg, None) and crs.to_epsg() != to_epsg:
            # Pozostawiamy natywny układ metryczny, tylko ostrzeżenie.
            if crs.to_epsg() != to_epsg:
                warnings.append(
                    f"CRS rastra to {crs.to_string()}, oczekiwany EPSG:{to_epsg}. "
                    "Działki zostaną zreprojektowane do CRS rastra."
                )

        if abs(transform.a) > 2.5:
            warnings.append(
                f"Rozdzielczość {abs(transform.a):.1f} m — do oceny działki lepiej użyć NMT 1 m."
            )

        nmpt = _roughness_nmpt_warning(z)
        if nmpt:
            warnings.append(nmpt)

        z_valid = z[np.isfinite(z)]
        if z_valid.size and (z_valid.max() - z_valid.min()) < 0.05:
            warnings.append("Prawie płaski raster — zasięg zalewu będzie niestabilny numerycznie.")

    return Terrain(
        elevation=z,
        transform=transform,
        crs=crs,
        source_path=path,
        tags=tags,
        warnings=warnings,
    )


def _reproject_to(
    z: np.ndarray, transform: Affine, crs: CRS, dst_epsg: int
) -> tuple[np.ndarray, Affine, CRS]:
    dst_crs = CRS.from_epsg(dst_epsg)
    h, w = z.shape
    dst_transform, dw, dh = calculate_default_transform(crs, dst_crs, w, h, *rasterio.transform.array_bounds(h, w, transform))
    dst = np.full((dh, dw), np.nan, dtype=np.float32)
    reproject(
        source=z,
        destination=dst,
        src_transform=transform,
        src_crs=crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    return dst, dst_transform, dst_crs


def write_geotiff(
    path: str | Path,
    array: np.ndarray,
    transform: Affine,
    crs: CRS,
    *,
    nodata: float = -9999.0,
    dtype: str = "float32",
    tags: dict[str, str] | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.array(array, dtype=dtype, copy=True)
    data[~np.isfinite(data)] = nodata
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
        if tags:
            dst.update_tags(**tags)
