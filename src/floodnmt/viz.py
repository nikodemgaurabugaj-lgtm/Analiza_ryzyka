"""Kartografia: hillshade, zasięg, HAND, klasy głębokości."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from matplotlib.colors import LightSource
from matplotlib.patches import Patch

from floodnmt.constants import ISOK_DEPTH_COLORS, ISOK_DEPTH_LABELS
from floodnmt.dem import Terrain
from floodnmt.hydrology import Hydrology
from floodnmt.inundation import classify_depth

plt.rcParams.update(
    {
        "font.size": 9,
        "axes.titlesize": 11,
        "figure.dpi": 120,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "axes.grid": False,
        "figure.facecolor": "white",
    }
)


def _extent(terrain: Terrain) -> tuple[float, float, float, float]:
    west, south, east, north = terrain.bounds
    return west, east, south, north


def _hillshade(z: np.ndarray, cellsize: float) -> np.ndarray:
    ls = LightSource(azdeg=315, altdeg=42)
    filled = np.where(np.isfinite(z), z, np.nanmean(z))
    return ls.hillshade(filled, vert_exag=1.8, dx=cellsize, dy=cellsize)


def save_overview(
    path: Path,
    terrain: Terrain,
    hydro: Hydrology,
    depths: dict[str, np.ndarray],
    method: str,
) -> Path:
    path = Path(path)
    n = len(depths)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 4.6), squeeze=False)
    hs = _hillshade(terrain.elevation, terrain.cellsize_m)
    ext = _extent(terrain)
    for ax, (label, depth) in zip(axes[0], depths.items()):
        ax.imshow(hs, cmap="gray", extent=ext, origin="upper")
        wet = np.ma.masked_invalid(depth)
        im = ax.imshow(
            wet,
            cmap="Blues",
            extent=ext,
            origin="upper",
            alpha=0.78,
            vmin=0,
            vmax=max(3.0, float(np.nanmax(depth)) if np.isfinite(depth).any() else 3.0),
        )
        streams = np.ma.masked_where(~hydro.streams, hydro.streams)
        ax.imshow(streams, cmap="autumn", extent=ext, origin="upper", alpha=0.9, vmin=0, vmax=1)
        ax.set_title(label)
        ax.set_xlabel("X PL-1992 [m]")
        ax.set_ylabel("Y PL-1992 [m]")
        ax.ticklabel_format(style="plain")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Głębokość [m]")
    fig.suptitle(
        f"Zasięg zalewu — {method.upper()}  |  ciek (żółty) z akumulacji NMT",
        fontsize=12,
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def save_classified(path: Path, terrain: Terrain, depth: np.ndarray, title: str) -> Path:
    path = Path(path)
    hs = _hillshade(terrain.elevation, terrain.cellsize_m)
    ext = _extent(terrain)
    cls = classify_depth(depth)
    cmap = colors.ListedColormap(["#00000000", *ISOK_DEPTH_COLORS])
    bounds = [0, 1, 2, 3, 4, 5]
    norm = colors.BoundaryNorm(bounds, cmap.N)
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.imshow(hs, cmap="gray", extent=ext, origin="upper")
    ax.imshow(np.ma.masked_equal(cls, 0), cmap=cmap, norm=norm, extent=ext, origin="upper", alpha=0.85)
    ax.set_title(title)
    ax.set_xlabel("X PL-1992 [m]")
    ax.set_ylabel("Y PL-1992 [m]")
    handles = [Patch(facecolor=c, edgecolor="none", label=lab) for c, lab in zip(ISOK_DEPTH_COLORS, ISOK_DEPTH_LABELS)]
    ax.legend(handles=handles, loc="lower right", framealpha=0.92, title="Głębokość (klasy MZP)")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def save_hand(path: Path, terrain: Terrain, hydro: Hydrology) -> Path:
    path = Path(path)
    ext = _extent(terrain)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8))
    hs = _hillshade(terrain.elevation, terrain.cellsize_m)
    axes[0].imshow(hs, cmap="gray", extent=ext, origin="upper")
    im0 = axes[0].imshow(terrain.elevation, cmap="terrain", extent=ext, origin="upper", alpha=0.55)
    axes[0].set_title("NMT + hillshade")
    fig.colorbar(im0, ax=axes[0], fraction=0.046, label="Wysokość [m n.p.m.]")

    hand = np.ma.masked_invalid(hydro.hand)
    im1 = axes[1].imshow(hand, cmap="YlGnBu", extent=ext, origin="upper", vmin=0, vmax=25)
    streams = np.ma.masked_where(~hydro.streams, hydro.streams)
    axes[1].imshow(streams, cmap="autumn", extent=ext, origin="upper", alpha=0.95)
    axes[1].set_title(f"HAND  |  próg cieku {hydro.stream_threshold_km2:.2f} km²")
    fig.colorbar(im1, ax=axes[1], fraction=0.046, label="HAND [m]")
    for ax in axes:
        ax.set_xlabel("X PL-1992 [m]")
        ax.set_ylabel("Y PL-1992 [m]")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def save_uncertainty(path: Path, terrain: Terrain, agreement: np.ndarray, rmse: float, stage: float) -> Path:
    path = Path(path)
    ext = _extent(terrain)
    hs = _hillshade(terrain.elevation, terrain.cellsize_m)
    cmap = colors.ListedColormap(["#00000000", "#fdd0a2", "#fdae6b", "#08519c"])
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.imshow(hs, cmap="gray", extent=ext, origin="upper")
    ax.imshow(agreement, cmap=cmap, extent=ext, origin="upper", alpha=0.85, vmin=0, vmax=3)
    ax.set_title(f"Niepewność zasięgu przy stanie {stage:g} m  (±{rmse:g} m RMSE NMT)")
    handles = [
        Patch(facecolor="#fdd0a2", label="tylko H+RMSE (pesymistyczny brzeg)"),
        Patch(facecolor="#fdae6b", label="większość realizacji"),
        Patch(facecolor="#08519c", label="zgodność wszystkich trzech"),
    ]
    ax.legend(handles=handles, loc="lower right", framealpha=0.92)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def save_parcel_bars(path: Path, table, stage_label: str, top_n: int = 18) -> Path:
    path = Path(path)
    df = table.copy()
    if "flooded_pct" not in df.columns or df.empty:
        return path
    df = df.sort_values("flooded_pct", ascending=False).head(top_n)
    labels = []
    for _, r in df.iterrows():
        nr = r.get("numer", r.get("id", r.get("teryt_dzialki", "")))
        ob = r.get("obreb", "")
        labels.append(f"{ob} {nr}".strip()[:28])
    fig, ax = plt.subplots(figsize=(8.0, max(3.5, 0.32 * len(df) + 1.5)))
    ax.barh(range(len(df)), df["flooded_pct"], color="#2171b5")
    ax.set_yticks(range(len(df)), labels)
    ax.invert_yaxis()
    ax.set_xlabel("Udział zalanej powierzchni działki [%]")
    ax.set_title(f"Działki najbardziej narażone — {stage_label}")
    ax.set_xlim(0, 100)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
