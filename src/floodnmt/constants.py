"""Stałe inżynierskie i kartograficzne."""

from __future__ import annotations

import numpy as np

EPSG_PL1992 = 2180
VERTICAL_DATUM_KRON86 = "PL-KRON86-NH"
VERTICAL_DATUM_EVRF2007 = "PL-EVRF2007-NH"

# Średni błąd wysokości NMT 1 m ALS (GUGiK / ISOK): rząd 0,1–0,2 m.
NMT_RMSE_1M_M = 0.20
NMT_RMSE_5M_M = 0.50

# Klasy głębokości jak na mapach zagrożenia powodziowego (ISOK / Wody Polskie).
ISOK_DEPTH_EDGES_M = (0.0, 0.5, 2.0, 4.0, np.inf)
ISOK_DEPTH_LABELS = ("< 0,5 m", "0,5–2 m", "2–4 m", "> 4 m")
ISOK_DEPTH_COLORS = ("#c6dbef", "#6baed6", "#2171b5", "#08306b")

DEPTH_CMAP = "Blues"
HAND_CMAP = "YlGnBu"

MAX_CELLS = 80_000_000  # ~80 mln komórek; powyżej wymagany wycinek
DEFAULT_STREAM_KM2 = 0.30
DEFAULT_STAGES_M = (0.5, 1.0, 2.0, 3.0)

DISCLAIMER_PL = (
    "Wynik jest modelem topograficznym (HAND / wanna połączona), nie mapą zagrożenia "
    "powodziowego ISOK i nie zastępuje modelowania hydraulicznego 1D/2D. Nie służy "
    "do decyzji administracyjnych, MPZP ani wyceny ubezpieczeniowej. Oficjalne MZP/MRP: "
    "https://isok.gov.pl/hydroportal.html"
)
