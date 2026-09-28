"""Comparing a lockfile with today's listings: would a re-resolve pin the same files? (#332)"""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from usdata.cache import sha256_file
from usdata.cli import app
from usdata.manifest import Lockfile, lockfile_path
from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.providers.base import Provider
from usdata.pull import ManifestChanged, compare_listing, pull
from usdata.registry import Registry, default_registry

cli_module = importlib.import_module("usdata.cli.app")
START = datetime(2024, 5, 7, 4, 30, tzinfo=UTC)
LISTED: dict[str, tuple[int | None, str]] = {}
"""What the fake source lists today: each asset id's size and href."""

MANIFEST = """name: listing-check
sources:
  - name: radar
    dataset: noaa:ghcn-daily
    start: 2024-05-07T04:00Z
    end: 2024-05-07T05:00Z
"""


class Listing(Provider):
    """Lists whatever ``LISTED`` holds, as an archive whose contents can change does."""

    def list_assets(self, query: Query) -> list[Asset]:
        return [
            Asset(
                id=asset_id,
                dataset_id="noaa:ghcn-daily",
                href=href,
                protocol=Protocol.HTTP,
                size=size,
                time=TimeRange(start=START, end=START),
            )
            for asset_id, (size, href) in sorted(LISTED.items())
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        dest.write_bytes(asset.id.encode())
        return dest


@pytest.fixture
def registry() -> Registry:
    LISTED.clear()
    LISTED.update(
        {
            "scan-a": (100, "https://example.test/scan-a"),
            "scan-b": (200, "https://example.test/scan-b"),
            "scan-c": (None, "https://example.test/scan-c"),
        }
    )
    reg = default_registry()
    dataset = reg.get("noaa:ghcn-daily").model_copy(update={"adapter": f"{__name__}:Listing"})
    return Registry(
        [dataset if d.id == dataset.id else d for d in reg],
        providers=[reg.provider(provider_id) for provider_id in sorted(reg.providers())],
        domains=reg.domains(),
        systems=reg.systems(),
    )


@pytest.fixture
def manifest(tmp_path: Path, registry: Registry) -> Path:
    path = tmp_path / "dataset.yaml"
    path.write_text(MANIFEST)
    pull(path, root=tmp_path / "cache", registry=registry)
    return path


def test_an_unchanged_listing_matches_the_lockfile(manifest: Path, registry: Registry) -> None:
    comparison = compare_listing(manifest, registry=registry)
    (radar,) = comparison.sources
    assert (radar.source, radar.dataset_id) == ("radar", "noaa:ghcn-daily")
    assert radar.unchanged == 3 and not (radar.added or radar.removed or radar.changed)
    assert radar.matches and comparison.matches
    assert comparison.manifest == "listing-check"
    assert comparison.lockfile == lockfile_path(manifest)


def test_added_removed_and_resized_assets_are_each_reported(
    manifest: Path, registry: Registry, tmp_path: Path
) -> None:
    del LISTED["scan-a"]
    LISTED["scan-b"] = (250, "https://example.test/scan-b")
    LISTED["scan-d"] = (400, "https://example.test/scan-d")
    before = sorted(path for path in tmp_path.rglob("*") if path.is_file())
    (radar,) = compare_listing(manifest, registry=registry).sources
    assert [asset.id for asset in radar.added] == ["scan-d"]
    assert [asset.id for asset in radar.removed] == ["scan-a"]
    (change,) = radar.changed
    assert (change.asset_id, change.locked_size, change.listed_size) == ("scan-b", 200, 250)
    assert radar.unchanged == 1 and not radar.matches
    # Nothing is downloaded, and the lockfile and cache are left as they were.
    assert sorted(path for path in tmp_path.rglob("*") if path.is_file()) == before


def test_a_size_only_one_side_reports_is_no_change(manifest: Path, registry: Registry) -> None:
    LISTED["scan-c"] = (300, "https://example.test/scan-c")
    LISTED["scan-a"] = (None, "https://example.test/scan-a")
    assert compare_listing(manifest, registry=registry).matches


def test_a_moved_href_is_a_change(manifest: Path, registry: Registry) -> None:
    LISTED["scan-c"] = (None, "https://mirror.example.test/scan-c")
    (radar,) = compare_listing(manifest, registry=registry).sources
    (change,) = radar.changed
    assert change.locked_href == "https://example.test/scan-c"
    assert change.listed_href == "https://mirror.example.test/scan-c"


def test_a_lockfile_without_source_keys_is_matched_by_dataset_position(
    manifest: Path, registry: Registry
) -> None:
    path = lockfile_path(manifest)
    lock = Lockfile.load(path)
    lock.model_copy(
        update={"assets": [e.model_copy(update={"source": None}) for e in lock.assets]}
    ).save(path)
    # An old lockfile implies the key an unnamed source gets: its position, 1.
    manifest.write_text(MANIFEST.replace("  - name: radar\n    dataset", "  - dataset"))
    Lockfile.load(path).model_copy(update={"manifest_checksum": sha256_file(manifest)}).save(path)
    comparison = compare_listing(manifest, registry=registry)
    assert [s.source for s in comparison.sources] == ["1"] and comparison.matches


def test_no_lockfile_or_a_changed_manifest_is_refused(
    tmp_path: Path, manifest: Path, registry: Registry
) -> None:
    fresh = tmp_path / "other.yaml"
    fresh.write_text(MANIFEST)
    with pytest.raises(FileNotFoundError, match=r"no lockfile at .*other\.lock\.json; run pull"):
        compare_listing(fresh, registry=registry)
    manifest.write_text(MANIFEST.replace("05:00Z", "05:30Z"))
    with pytest.raises(ManifestChanged):
        compare_listing(manifest, registry=registry)


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch, registry: Registry) -> CliRunner:
    """The CLI, comparing through the test registry."""
    monkeypatch.setattr(
        cli_module,
        "compare_manifest_listing",
        lambda path: compare_listing(path, registry=registry),
    )
    return CliRunner()


def test_cli_verify_listing_exits_0_when_everything_matches(cli, manifest: Path) -> None:
    result = cli.invoke(app, ["verify", str(manifest), "--listing"])
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert result.stderr == "every source lists what dataset.lock.json pins\n"


def test_cli_verify_listing_prints_each_difference_and_exits_1(cli, manifest: Path) -> None:
    del LISTED["scan-a"]
    LISTED["scan-b"] = (250, "https://example.test/scan-b")
    LISTED["scan-d"] = (None, "https://example.test/scan-d")
    result = cli.invoke(app, ["verify", str(manifest), "--listing"])
    assert result.exit_code == 1
    assert result.stdout.splitlines() == [
        "radar\tadded\tscan-d\thttps://example.test/scan-d",
        "radar\tremoved\tscan-a\thttps://example.test/scan-a",
        "radar\tchanged\tscan-b\t200 -> 250 bytes",
    ]
    assert "1 source(s) list something other than dataset.lock.json pins: radar" in result.stderr


def test_cli_verify_listing_json_is_the_whole_comparison(cli, manifest: Path) -> None:
    LISTED["scan-d"] = (400, "https://example.test/scan-d")
    result = cli.invoke(app, ["verify", str(manifest), "--listing", "--json"])
    assert result.exit_code == 1
    body = json.loads(result.stdout)
    assert body["matches"] is False and body["sources"][0]["matches"] is False
    assert [a["id"] for a in body["sources"][0]["added"]] == ["scan-d"]


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (["--json"], "--json applies to --listing only"),
        (["--listing", "--cache-dir", "x"], "--listing reads no cache; drop --cache-dir"),
    ],
)
def test_cli_verify_listing_rejects_incompatible_flags(
    cli, manifest: Path, flags: list[str], message: str
) -> None:
    result = cli.invoke(app, ["verify", str(manifest), *flags])
    assert result.exit_code == 2 and message in result.stderr


def test_cli_verify_listing_without_a_lockfile_exits_2(cli, tmp_path: Path) -> None:
    path = tmp_path / "fresh.yaml"
    path.write_text(MANIFEST)
    result = cli.invoke(app, ["verify", str(path), "--listing"])
    assert result.exit_code == 2 and "run pull first" in result.stderr
