"""Interfejs wiersza poleceń."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from floodnmt.constants import DEFAULT_STAGES_M, DEFAULT_STREAM_KM2, DISCLAIMER_PL
from floodnmt.dem import write_geotiff
from floodnmt.pipeline import analyze
from floodnmt.synthetic import make_valley_dem

app = typer.Typer(
    help="FalaNMT — zasięg zalewu z numerycznego modelu terenu (HAND / wanna połączona).",
    no_args_is_help=True,
)
console = Console()


def _parse_stages(text: str) -> tuple[float, ...]:
    parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    stages = tuple(float(p.replace(",", ".")) for p in parts)
    if not stages:
        raise typer.BadParameter("Podaj co najmniej jeden stan, np. 0.5,1,2,3")
    if any(s < 0 for s in stages):
        raise typer.BadParameter("Stany nie mogą być ujemne.")
    return stages


def _repo_data() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "nysa_klodzka"
        if candidate.exists():
            return candidate
    return Path.cwd() / "data" / "nysa_klodzka"


@app.command("analyze")
def analyze_cmd(
    dem: Path = typer.Argument(..., exists=True, readable=True, help="GeoTIFF / ASC z NMT"),
    out: Path = typer.Option(Path("outputs/run"), "--out", "-o", help="Katalog wyników"),
    method: str = typer.Option("hand", "--method", "-m", help="hand | connected"),
    stages: str = typer.Option("0.5,1,2,3", "--stages", "-s", help="Stany w korycie [m], po przecinku"),
    stream_km2: float = typer.Option(DEFAULT_STREAM_KM2, "--stream-km2", help="Próg akumulacji cieku [km²]"),
    parcels: Optional[Path] = typer.Option(None, "--parcels", "-p", help="GeoJSON/SHP działek"),
    rmse: Optional[float] = typer.Option(None, "--rmse", help="RMSE wysokości NMT [m]"),
    title: Optional[str] = typer.Option(None, "--title", help="Tytuł raportu"),
) -> None:
    """Policz mapy zalewu, głębokości i metryki działek."""
    console.print(f"[bold]FalaNMT[/bold]  metoda={method}")
    result = analyze(
        dem,
        out,
        method=method,
        stages=_parse_stages(stages),
        stream_km2=stream_km2,
        parcels_path=parcels,
        rmse_m=rmse,
        title=title,
    )
    table = Table(title="Scenariusze")
    table.add_column("Stan [m]")
    table.add_column("Pow. zalewu [km²]", justify="right")
    table.add_column("Gł. śr. [m]", justify="right")
    table.add_column("Gł. max [m]", justify="right")
    table.add_column("Objętość [tys. m³]", justify="right")
    for s in result.scenarios:
        table.add_row(
            f"{s.stage_m:g}",
            f"{s.summary['area_km2']:.3f}",
            f"{s.summary['depth_mean_m']:.2f}",
            f"{s.summary['depth_max_m']:.2f}",
            f"{s.summary['volume_m3']/1000:.1f}",
        )
    console.print(table)
    for w in result.warnings:
        console.print(f"[yellow]⚠ {w}[/yellow]")
    console.print(f"Raport: {result.report_html}")
    console.print(f"[dim]{DISCLAIMER_PL}[/dim]")


@app.command("demo")
def demo_cmd(
    out: Path = typer.Option(Path("outputs/nysa_klodzka"), "--out", "-o"),
    method: str = typer.Option("hand", "--method", "-m"),
    stages: str = typer.Option("0.5,1,2,3", "--stages", "-s"),
    stream_km2: float = typer.Option(0.30, "--stream-km2"),
) -> None:
    """Pilotaż: Nysa Kłodzka w Kłodzku (NMT 1 m GUGiK + działki ULDK)."""
    data = _repo_data()
    dem = data / "nmt_1m_klodzko.tif"
    parcels = data / "dzialki_uldk.geojson"
    if not dem.exists():
        raise typer.Exit(f"Brak NMT pilotażowego: {dem}")
    analyze_cmd(
        dem=dem,
        out=out,
        method=method,
        stages=stages,
        stream_km2=stream_km2,
        parcels=parcels if parcels.exists() else None,
        rmse=0.20,
        title="Nysa Kłodzka — Kłodzko (NMT 1 m GUGiK)",
    )


@app.command("synthetic")
def synthetic_cmd(
    out: Path = typer.Option(Path("outputs/synthetic"), "--out", "-o"),
) -> None:
    """Zapisz syntetyczną dolinę (test wanny vs HAND) i uruchom obie metody."""
    terrain = make_valley_dem()
    dem_path = out / "valley.tif"
    write_geotiff(dem_path, terrain.elevation, terrain.transform, terrain.crs, tags={"SYNTHETIC": "1"})
    console.print(f"Zapisano {dem_path}")
    for method in ("connected", "hand"):
        analyze(
            dem_path,
            out / method,
            method=method,
            stages=(1.0, 2.0, 7.0),
            stream_km2=0.01,
            title=f"Dolina syntetyczna — {method}",
        )
        console.print(f"OK {method} → {out / method / 'raport.html'}")


if __name__ == "__main__":
    app()
