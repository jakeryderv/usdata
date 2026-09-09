from pathlib import Path

from usdata import provenance
from usdata.cache import asset_path, cache_dir, sha256_file
from usdata.models import Asset, Protocol
from usdata.registry import default_registry


def test_cache_dir_honours_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("USDATA_CACHE_DIR", str(tmp_path))
    assert cache_dir() == tmp_path
    asset = Asset(id="a/b", dataset_id="noaa:ghcn-daily", href="x", protocol=Protocol.HTTP)
    assert asset_path(asset) == tmp_path / "noaa" / "ghcn-daily" / "a_b"


def test_record_and_sidecar_roundtrip(tmp_path: Path) -> None:
    f = tmp_path / "obs.csv"
    f.write_bytes(b"station,value\n")
    ds = default_registry().get("noaa:ghcn-daily")
    asset = Asset(
        id="obs.csv", dataset_id=ds.id, href="https://example/obs.csv", protocol=Protocol.HTTP
    )
    prov = provenance.record(ds, asset, f)
    assert prov.checksum == sha256_file(f)
    assert prov.size == f.stat().st_size
    assert prov.license == ds.license
    provenance.write(prov, f)
    assert provenance.read(f) == prov
