"""Within a source, assets come back by start time then id, and one() names a single asset."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from usdata._fetch import ordered
from usdata.manifest import Lockfile, lockfile_path
from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.providers.base import Provider
from usdata.pull import PullResult, pull
from usdata.registry import Registry, default_registry


def asset(asset_id: str, start: datetime | None) -> Asset:
    return Asset(
        id=asset_id,
        dataset_id="noaa:ghcn-daily",
        href=f"https://example.test/{asset_id}",
        protocol=Protocol.HTTP,
        time=None if start is None else TimeRange(start=start, end=start),
    )


LATER = datetime(2024, 5, 7, 4, tzinfo=UTC)
EARLIER = datetime(2024, 5, 7, 3, tzinfo=UTC)


class Unsorted(Provider):
    """Lists three assets in the wrong order, one without a start time."""

    def list_assets(self, query: Query) -> list[Asset]:
        return [asset("b", LATER), asset("timeless", None), asset("a", LATER), asset("c", EARLIER)]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        dest.write_bytes(asset.id.encode())
        return dest


def test_ordered_puts_start_time_first_then_id_and_timeless_last() -> None:
    listing = Unsorted(default_registry().get("noaa:ghcn-daily")).list_assets(Query())
    assert [a.id for a in ordered(listing)] == ["c", "a", "b", "timeless"]
    assert ordered([]) == []


@pytest.fixture
def registry() -> Registry:
    reg = default_registry()
    dataset = reg.get("noaa:ghcn-daily").model_copy(update={"adapter": f"{__name__}:Unsorted"})
    return Registry(
        [dataset if d.id == dataset.id else d for d in reg],
        providers=[reg.provider(provider_id) for provider_id in sorted(reg.providers())],
        domains=reg.domains(),
        systems=reg.systems(),
    )


def test_pull_orders_each_source_and_the_lockfile_the_same_way(
    tmp_path: Path, registry: Registry
) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(
        "name: order\nsources:\n"
        "  - name: obs\n    dataset: noaa:ghcn-daily\n    start: 2024-05-07\n    end: 2024-05-07\n"
    )
    result = pull(manifest, root=tmp_path / "cache", registry=registry)
    expected = ["c", "a", "b", "timeless"]
    assert [item.asset.id for item in result.fetched] == expected
    assert [item.asset.id for item in result.by_source["obs"]] == expected
    lock = Lockfile.load(lockfile_path(manifest))
    assert [entry.asset.id for entry in lock.assets] == expected

    # A lockfile written before the core ordered listings still groups in order on restore.
    raw = json.loads(lockfile_path(manifest).read_text())
    raw["assets"].reverse()
    lockfile_path(manifest).write_text(json.dumps(raw))
    restored = pull(manifest, root=tmp_path / "cache", registry=registry)
    assert restored.from_lockfile
    assert [item.asset.id for item in restored.by_source["obs"]] == expected

    with pytest.raises(ValueError, match="resolved to 4 assets, not one"):
        restored.one("obs")
    with pytest.raises(KeyError, match="no source 'nope'; sources are obs"):
        restored.one("nope")


def test_one_returns_the_single_asset_of_a_source(tmp_path: Path) -> None:
    from usdata.pull import Lockfile as _Lockfile  # noqa: F401  (schema is the public one)

    item = pull_result_with_one_asset(tmp_path)
    assert item.one("only").asset.id == "solo"
    with pytest.raises(ValueError, match="resolved to 0 assets"):
        item.one("empty")


def pull_result_with_one_asset(tmp_path: Path) -> PullResult:
    from usdata._fetch import FetchedAsset
    from usdata.models import Provenance

    solo = asset("solo", EARLIER)
    prov = Provenance(
        dataset_id=solo.dataset_id,
        provider="noaa",
        source_url=solo.href,
        retrieved_at=EARLIER,
        checksum="sha256:" + "0" * 64,
        size=0,
        usdata_version="0",
    )
    fetched = FetchedAsset(asset=solo, path=tmp_path / "solo", provenance=prov, from_cache=True)
    lock = Lockfile(
        manifest="m", manifest_checksum="sha256:0", generated_at=EARLIER, usdata_version="0"
    )
    return PullResult(
        lockfile=lock,
        lockfile_path=tmp_path / "m.lock.json",
        fetched=[fetched],
        from_lockfile=False,
        by_source={"only": [fetched], "empty": []},
    )
