"""Pas niepewności wynikający z błędu wysokości NMT."""

from __future__ import annotations

import numpy as np

from floodnmt.hydrology import Hydrology
from floodnmt.inundation import inundate_connected, inundate_hand


def uncertainty_envelope(
    method: str,
    hydro: Hydrology,
    elevation: np.ndarray,
    stage_m: float,
    rmse_m: float,
) -> dict[str, np.ndarray]:
    """Trzy realizacje: H−RMSE, H, H+RMSE.

    Na płaskiej terasie 0,2 m błędu wysokości przesuwa brzeg zalewu
    o dziesiątki metrów — to trzeba pokazać, nie ukrywać.
    """
    stages = (max(0.0, stage_m - rmse_m), stage_m, stage_m + rmse_m)
    depths = []
    for s in stages:
        if method == "hand":
            depths.append(inundate_hand(hydro.hand, s))
        else:
            wse = hydro.stream_z_median + s
            depths.append(inundate_connected(elevation, hydro.streams, wse))

    wet = [np.isfinite(d) & (d >= 0) for d in depths]
    n_agree = wet[0].astype(np.uint8) + wet[1].astype(np.uint8) + wet[2].astype(np.uint8)
    # 0 sucho we wszystkich, 1 tylko pesymistyczny, 2 większość, 3 wszystkie
    return {
        "depth_low": depths[0],
        "depth_mid": depths[1],
        "depth_high": depths[2],
        "agreement": n_agree,
        "core": n_agree == 3,
        "fringe": (n_agree > 0) & (n_agree < 3),
    }
