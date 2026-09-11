"""Modele zasięgu: HAND oraz wanna połączona hydrologicznie."""

from __future__ import annotations

from collections import deque

import numpy as np

from floodnmt.constants import ISOK_DEPTH_EDGES_M, ISOK_DEPTH_LABELS

# D8: N, NE, E, SE, S, SW, W, NW
_D8 = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))


def inundate_hand(hand: np.ndarray, stage_m: float) -> np.ndarray:
    """Głębokość [m] tam, gdzie HAND ≤ stan w korycie.

    cell zalany ⇔ wysokość nad najbliższym drenażem nie przekracza `stage_m`.
    Głębokość ≈ stage − HAND (Nobre et al. 2016). To nie jest zwierciadło 2D.
    """
    if stage_m < 0:
        raise ValueError("Stan w korycie nie może być ujemny.")
    depth = np.full(hand.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(hand)
    wet = valid & (hand <= stage_m)
    depth[wet] = (stage_m - hand[wet]).astype(np.float32)
    return depth


def inundate_connected(
    elevation: np.ndarray,
    seeds: np.ndarray,
    water_surface_m: float,
) -> np.ndarray:
    """Wanna połączona: zalane tylko komórki osiągalne ze źródła przy z ≤ H.

    Prosty próg `z < H` (bathtub) zalewa odłączone misy za wzgórzem.
    Tutaj BFS 8-sąsiedztwa startuje z maski `seeds` (cik / punkt / krawędź)
    i nie przechodzi przez komórki wyższe niż zadane zwierciadło H.
    Złożoność O(n).
    """
    z = elevation
    rows, cols = z.shape
    wet = np.zeros(z.shape, dtype=bool)
    q: deque[tuple[int, int]] = deque()

    seed_idx = np.argwhere(seeds & np.isfinite(z) & (z <= water_surface_m))
    for i, j in seed_idx:
        wet[i, j] = True
        q.append((int(i), int(j)))

    while q:
        i, j = q.popleft()
        for di, dj in _D8:
            ni, nj = i + di, j + dj
            if ni < 0 or nj < 0 or ni >= rows or nj >= cols:
                continue
            if wet[ni, nj]:
                continue
            zij = z[ni, nj]
            if not np.isfinite(zij) or zij > water_surface_m:
                continue
            wet[ni, nj] = True
            q.append((ni, nj))

    depth = np.full(z.shape, np.nan, dtype=np.float32)
    depth[wet] = (water_surface_m - z[wet]).astype(np.float32)
    return depth


def classify_depth(depth: np.ndarray) -> np.ndarray:
    """Klasy ISOK: 1=<0.5, 2=0.5–2, 3=2–4, 4=>4, 0=sucho/NoData."""
    out = np.zeros(depth.shape, dtype=np.uint8)
    wet = np.isfinite(depth) & (depth >= 0)
    edges = ISOK_DEPTH_EDGES_M
    for k, (lo, hi) in enumerate(zip(edges[:-1], edges[1:]), start=1):
        sel = wet & (depth >= lo) & (depth < hi)
        out[sel] = k
    return out


def depth_summary(depth: np.ndarray, cell_area_m2: float) -> dict[str, float]:
    wet = np.isfinite(depth) & (depth >= 0)
    n = int(wet.sum())
    vals = depth[wet]
    classes = classify_depth(depth)
    summary = {
        "n_wet": float(n),
        "area_km2": float(n * cell_area_m2 / 1e6),
        "share": float(n / depth.size) if depth.size else 0.0,
        "depth_mean_m": float(vals.mean()) if n else 0.0,
        "depth_max_m": float(vals.max()) if n else 0.0,
        "depth_p90_m": float(np.percentile(vals, 90)) if n else 0.0,
        "volume_m3": float(vals.sum() * cell_area_m2) if n else 0.0,
    }
    for k, label in enumerate(ISOK_DEPTH_LABELS, start=1):
        summary[f"class_{k}_km2"] = float((classes == k).sum() * cell_area_m2 / 1e6)
        summary[f"class_{k}_label"] = label  # type: ignore[assignment]
    return summary
