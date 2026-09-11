"""Testy algorytmów na syntetycznym NMT — regressja metody, nie „czy biblioteka działa”."""

from __future__ import annotations

import numpy as np

from floodnmt.hydrology import derive_hydrology
from floodnmt.inundation import classify_depth, inundate_connected, inundate_hand
from floodnmt.synthetic import make_valley_dem


def test_isolated_pit_stays_dry_when_saddle_holds():
    t = make_valley_dem()
    hydro = derive_hydrology(t, stream_km2=0.01)
    depth = inundate_connected(t.elevation, hydro.streams, water_surface_m=14.0)
    pit = t.pit_mask
    assert pit.any()
    assert not np.isfinite(depth[pit]).any(), "Wanna połączona nie może zalać misy za garbem."
    rr = t.shape[0] // 2
    assert np.isfinite(depth[rr - 1 : rr + 2]).mean() > 0.5


def test_pit_floods_after_saddle_overtopped():
    t = make_valley_dem()
    hydro = derive_hydrology(t, stream_km2=0.01)
    depth = inundate_connected(t.elevation, hydro.streams, water_surface_m=17.0)
    pit = t.pit_mask
    assert np.isfinite(depth[pit]).mean() > 0.9
    assert np.nanmin(depth[pit]) > 5.0


def test_hand_is_zero_on_streams_and_positive_on_slopes():
    t = make_valley_dem()
    hydro = derive_hydrology(t, stream_km2=0.01)
    assert hydro.n_stream_cells > 10
    assert float(np.nanmax(np.abs(hydro.hand[hydro.streams]))) < 0.25
    slopes = ~hydro.streams & np.isfinite(hydro.hand)
    assert float(np.nanmedian(hydro.hand[slopes])) > 0.3


def test_hand_stage_grows_inundation_monotonically():
    t = make_valley_dem()
    hydro = derive_hydrology(t, stream_km2=0.01)
    a1 = np.isfinite(inundate_hand(hydro.hand, 1.0)).sum()
    a2 = np.isfinite(inundate_hand(hydro.hand, 2.0)).sum()
    a4 = np.isfinite(inundate_hand(hydro.hand, 4.0)).sum()
    assert a1 < a2 < a4


def test_isok_depth_classes():
    d = np.array([[np.nan, 0.2, 0.5, 1.9, 2.0, 3.9, 4.0, 8.0]], dtype=np.float32)
    c = classify_depth(d)
    assert c[0, 0] == 0
    assert c[0, 1] == 1
    assert c[0, 2] == 2  # 0.5 należy do 0.5–2
    assert c[0, 4] == 3
    assert c[0, 6] == 4


def test_naive_bathtub_would_flood_pit_but_connected_does_not():
    t = make_valley_dem()
    hydro = derive_hydrology(t, stream_km2=0.01)
    h = 14.0
    naive = np.isfinite(t.elevation) & (t.elevation <= h)
    pit = t.pit_mask
    assert naive[pit].all(), "Kontrola: płaska wanna *powinna* zalać misę."
    connected = inundate_connected(t.elevation, hydro.streams, h)
    assert not np.isfinite(connected[pit]).any()
