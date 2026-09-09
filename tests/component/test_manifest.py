from datetime import UTC, datetime
from pathlib import Path

from usdata.manifest import LockedAsset, Lockfile, Manifest, lockfile_path
from usdata.models import Asset, Protocol, Provenance

EXAMPLE = """
name: tornado-environment
version: "1.0"
sources:
  - dataset: noaa:nexrad-level2
    location: oklahoma
    start: 2024-05-06
    end: 2024-05-07
    params: { site: KTLX }
  - dataset: usgs:structures
    location: oklahoma
"""


def test_manifest_load_and_validate(tmp_path: Path) -> None:
    path = tmp_path / "dataset.yaml"
    path.write_text(EXAMPLE)
    m = Manifest.load(path)
    assert m.name == "tornado-environment"
    assert len(m.sources) == 2
    q = m.sources[0].to_query()
    assert q.bbox is not None and q.params == {"site": "KTLX"}
    assert m.validate_against() == ["usgs:structures"]
    assert lockfile_path(path) == tmp_path / "dataset.lock.json"


def test_lockfile_roundtrip(tmp_path: Path) -> None:
    asset = Asset(
        id="KTLX20240506_200000_V06",
        dataset_id="noaa:nexrad-level2",
        href="s3://noaa-nexrad-level2/2024/05/06/KTLX/KTLX20240506_200000_V06",
        protocol=Protocol.S3,
    )
    prov = Provenance(
        dataset_id=asset.dataset_id,
        provider="noaa",
        source_url=asset.href,
        retrieved_at=datetime(2024, 5, 8, tzinfo=UTC),
        checksum="sha256:" + "0" * 64,
        size=1,
        usdata_version="0.1.0",
    )
    lock = Lockfile(
        manifest="tornado-environment",
        manifest_checksum="sha256:" + "1" * 64,
        generated_at=datetime.now(UTC),
        usdata_version="0.3.0",
        assets=[LockedAsset(asset=asset, provenance=prov)],
    )
    path = tmp_path / "dataset.lock.json"
    lock.save(path)
    assert Lockfile.load(path) == lock
