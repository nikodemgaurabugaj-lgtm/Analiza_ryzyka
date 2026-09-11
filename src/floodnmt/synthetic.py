"""Syntetyczny NMT doliny — testy regresji i demonstracja pułapki wanny."""

from __future__ import annotations

import numpy as np
from affine import Affine
from rasterio.crs import CRS

from floodnmt.dem import Terrain


def make_valley_dem(
    rows: int = 80,
    cols: int = 120,
    cellsize: float = 5.0,
) -> Terrain:
    """Paraboliczna dolina z korytem, odłączoną misą i siodłem.

    - koryto wzdłuż osi X, dno z = 10 + 0.02·kolumna,
    - stoki paraboliczne,
    - misa w górnym stoku (dno 11 m) otoczona ścianą 20 m,
    - jedyne siodło 16,5 m od strony doliny — wanna płaska zaleje misę
      przy H=14, połączona nie; przy H=17 woda przelewa siodło.
    """
    yy, xx = np.mgrid[0:rows, 0:cols]
    river_row = rows // 2
    dist = (yy - river_row).astype(np.float64)
    thalweg = 10.0 + 0.02 * xx
    z = thalweg + 0.08 * (dist**2) / (rows / 8.0)
    z[np.abs(dist) <= 1] = thalweg[np.abs(dist) <= 1]

    # Misa: ściany 20 m, dno 11 m, siodło 16.5 m w południowej ścianie (od rzeki).
    wall = (yy >= 5) & (yy <= 16) & (xx >= 8) & (xx <= 22)
    z[wall] = 20.0
    interior = (yy >= 6) & (yy <= 14) & (xx >= 10) & (xx <= 20)
    z[interior] = 11.0
    # Przełęcz: jeden rząd w ścianie od strony doliny, ciągły z wnętrzem.
    saddle = (yy == 16) & (xx >= 12) & (xx <= 18)
    z[saddle] = 16.5
    # Komórki tuż wewnątrz siodła też 16.5, żeby BFS wszedł do misy po przelewie.
    z[(yy == 15) & (xx >= 12) & (xx <= 18)] = 16.5

    transform = Affine(cellsize, 0, 500_000.0, 0, -cellsize, 300_000.0)
    terrain = Terrain(
        elevation=z.astype(np.float32),
        transform=transform,
        crs=CRS.from_epsg(2180),
        source_path=None,
        tags={"SYNTHETIC": "valley"},
        warnings=[],
    )
    terrain.pit_mask = interior  # type: ignore[attr-defined]
    return terrain
