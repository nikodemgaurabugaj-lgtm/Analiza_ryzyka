from floodnmt.dem import load_dem
from floodnmt.synthetic import make_valley_dem
from floodnmt.dem import write_geotiff


def test_load_roundtrip(tmp_path):
    t = make_valley_dem()
    p = tmp_path / "v.tif"
    write_geotiff(p, t.elevation, t.transform, t.crs)
    loaded = load_dem(p)
    assert loaded.shape == t.shape
    assert abs(loaded.cellsize_m - 5.0) < 1e-6
    assert loaded.stats()["z_min"] < 12
