import json
from pathlib import Path

from usdata import provenance
from usdata.cache import asset_path, cache_dir, sha256_file
from usdata.models import Asset, ByteRange, PartialFetch, Protocol, Provenance
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


PARTIAL = PartialFetch(
    object_url="s3://noaa-hrrr-bdp-pds/hrrr.20240506/conus/hrrr.t20z.wrfsfcf00.grib2",
    object_size=150_114_757,
    object_etag="17ef4503533b3bd3b4c6338b7dddcf2c",
    index_url="s3://noaa-hrrr-bdp-pds/hrrr.20240506/conus/hrrr.t20z.wrfsfcf00.grib2.idx",
    index_checksum="sha256:" + "ab" * 32,
    messages=[105, 131],
    ranges=[ByteRange(start=64292396, end=65005961), ByteRange(start=96828629, end=97953522)],
)


def test_a_partial_record_describes_the_ranges_and_the_object_they_came_from(
    tmp_path: Path,
) -> None:
    f = tmp_path / "part.grib2"
    f.write_bytes(b"GRIB2 messages")
    ds = default_registry().get("noaa:hrrr")
    asset = Asset(
        id="part.grib2",
        dataset_id=ds.id,
        href=f"{PARTIAL.object_url}#{PARTIAL.fragment}",
        protocol=Protocol.S3,
    )
    prov = provenance.record(ds, asset, f, PARTIAL)
    # The checksum and size still describe the local file, exactly as for a whole one.
    assert prov.checksum == sha256_file(f) and prov.size == f.stat().st_size
    assert prov.index_url == PARTIAL.index_url
    assert prov.index_checksum == PARTIAL.index_checksum
    assert prov.ranges == PARTIAL.ranges
    assert prov.object_size == 150_114_757
    assert prov.object_etag == "17ef4503533b3bd3b4c6338b7dddcf2c"
    assert prov.transformations == [
        f"grib2 messages 105,131 concatenated from {PARTIAL.object_url}"
    ]
    assert prov.is_partial
    provenance.write(prov, f)
    assert provenance.read(f) == prov
    written = json.loads(provenance.sidecar_path(f).read_text())
    assert written["ranges"][0] == {"start": 64292396, "end": 65005961}


def test_a_sidecar_written_before_partial_fetch_still_parses(tmp_path: Path) -> None:
    f = tmp_path / "whole.csv"
    f.write_bytes(b"station,value\n")
    older = {
        "dataset_id": "noaa:ghcn-daily",
        "provider": "noaa",
        "source_url": "https://example/obs.csv",
        "retrieved_at": "2026-09-11T12:00:00Z",
        "checksum": sha256_file(f),
        "size": f.stat().st_size,
        "license": "US Government Work (public domain)",
        "usdata_version": "0.17.0",
        "transformations": [],
    }
    provenance.sidecar_path(f).write_text(json.dumps(older))
    prov = provenance.read(f)
    assert prov.ranges == [] and prov.index_url is None and prov.object_etag is None
    assert not prov.is_partial
    assert Provenance.model_validate(older) == prov
