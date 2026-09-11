"""Hydrologia terenu: wypełnienie depresji, akumulacja, sieć drenażu, HAND."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyflwdir
from affine import Affine

from floodnmt.constants import DEFAULT_STREAM_KM2
from floodnmt.dem import Terrain


@dataclass
class Hydrology:
    filled: np.ndarray
    flowdir: np.ndarray
    upstream_km2: np.ndarray
    streams: np.ndarray
    hand: np.ndarray
    stream_threshold_km2: float
    stream_z_median: float
    stream_z_min: float
    n_stream_cells: int


def derive_hydrology(
    terrain: Terrain,
    *,
    stream_km2: float = DEFAULT_STREAM_KM2,
    nodata: float = -9999.0,
) -> Hydrology:
    """Policz HAND (Nobre et al. 2011/2016) na uwarunkowanym hydrologicznie NMT.

    `from_dem` wypełnia depresje do najniższego punktu przelewu (Wang & Liu 2006)
    i wyznacza kierunek spływu D8. Na małym wycinku próg cieku dotyczy
    *lokalnej* akumulacji, nie rzeczywistej powierzchni zlewni Nysy.
    """
    z = terrain.elevation
    work = np.where(np.isfinite(z), z, nodata).astype(np.float32)
    transform: Affine = terrain.transform
    latlon = bool(terrain.crs.is_geographic)

    flw = pyflwdir.from_dem(
        work,
        nodata=nodata,
        transform=transform,
        latlon=latlon,
        outlets="edge",
    )
    filled, _d8 = pyflwdir.fill_depressions(work, nodata=nodata, outlets="edge")
    filled = np.where(np.isfinite(z), filled.astype(np.float32), np.nan)

    up = flw.upstream_area(unit="km2").astype(np.float32)
    up = np.where(np.isfinite(z), up, np.nan)

    max_up = float(np.nanmax(up)) if np.isfinite(up).any() else 0.0
    thr = float(stream_km2)
    if max_up <= 0:
        raise ValueError("Nie udało się policzyć akumulacji — sprawdź NMT i NoData.")
    if thr >= max_up:
        thr = max(0.02, 0.12 * max_up)

    streams = np.isfinite(up) & (up >= thr)
    if int(streams.sum()) < 20:
        # awaryjnie: 0.5% komórek o największej akumulacji
        q = float(np.nanquantile(up, 0.995))
        streams = np.isfinite(up) & (up >= q)
        thr = q

    hand = flw.hand(drain=streams, elevtn=work).astype(np.float32)
    hand = np.where(np.isfinite(z), hand, np.nan)
    hand[hand < 0] = 0.0

    z_stream = z[streams]
    stream_z_median = float(np.nanmedian(z_stream)) if z_stream.size else float("nan")
    stream_z_min = float(np.nanmin(z_stream)) if z_stream.size else float("nan")

    return Hydrology(
        filled=filled,
        flowdir=flw.to_array().astype(np.uint8),
        upstream_km2=up,
        streams=streams,
        hand=hand,
        stream_threshold_km2=thr,
        stream_z_median=stream_z_median,
        stream_z_min=stream_z_min,
        n_stream_cells=int(streams.sum()),
    )


def auto_stream_threshold_km2(upstream_km2: np.ndarray) -> float:
    max_up = float(np.nanmax(upstream_km2))
    return float(max(0.05, min(0.5, 0.12 * max_up)))
