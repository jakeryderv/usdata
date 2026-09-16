import tomllib
from pathlib import Path

import pytest

from usdata.models import READER_EXTRAS, BBox, Query, Status
from usdata.providers import Provider, load_adapter
from usdata.providers.base import NotImplementedProvider
from usdata.registry import DatasetNotFound, Registry, default_registry

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def registry() -> Registry:
    return default_registry()


def test_bundled_registry_loads(registry: Registry) -> None:
    assert len(registry) >= 3
    assert "noaa:nexrad-level2" in registry
    assert {"noaa", "usgs", "nasa"} <= registry.providers()
    assert registry.provider("census").name == "Census Bureau"
    assert registry.get("noaa:ghcn-daily").status is Status.AVAILABLE


def test_get_unknown_raises(registry: Registry) -> None:
    with pytest.raises(DatasetNotFound):
        registry.get("nope:nothing")


def test_search_ranks_by_keyword(registry: Registry) -> None:
    results = registry.search(Query(text="nexrad radar scans"))
    assert results[0].dataset.id == "noaa:nexrad-level2"
    assert registry.search(Query(text="tornado"))[0].dataset.id == "noaa:spc-tornado-reports"


def test_search_hides_planned_unless_asked(registry: Registry) -> None:
    default = registry.search(Query())
    assert default and all(r.dataset.status is not Status.PLANNED for r in default)
    everything = registry.search(Query(), include_planned=True)
    assert len(everything) == len(registry) > len(default)


def test_domains_declared_and_next_target(registry: Registry) -> None:
    assert registry.domain("weather-radar").name == "Weather radar"
    assert {ds.domain for ds in registry} <= {d.id for d in registry.domains()}
    assert registry.next_target() is None
    ds = registry.get("noaa:ghcn-daily")
    with pytest.raises(ValueError, match="unknown domain"):
        Registry([ds.model_copy(update={"domain": "nope"})], domains=registry.domains())


def test_search_filters_by_provider_and_bbox(registry: Registry) -> None:
    assert registry.search(Query(provider="nope")) == []
    usgs = registry.search(Query(provider="usgs"), include_planned=True)
    assert {r.dataset.provider for r in usgs} == {"usgs"}
    # NEXRAD extent excludes the eastern hemisphere; global datasets remain.
    eastern = BBox(west=100, south=0, east=110, north=10)
    ids = {r.dataset.id for r in registry.search(Query(bbox=eastern))}
    assert "noaa:nexrad-level2" not in ids
    assert "noaa:ghcn-daily" in ids


def test_every_adapter_resolves_to_a_provider(registry: Registry) -> None:
    for ds in registry:
        if ds.status is Status.PLANNED:
            with pytest.raises(NotImplementedProvider, match="planned"):
                load_adapter(ds)
        else:
            assert isinstance(load_adapter(ds), Provider)


def test_duplicate_ids_rejected(registry: Registry) -> None:
    ds = registry.get("noaa:ghcn-daily")
    with pytest.raises(ValueError, match="duplicate"):
        Registry([ds, ds])


def test_from_yaml_rejects_a_leftover_catalog_block(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text("datasets: []\ncatalog:\n  noaa:thing:\n    summary: Old shape\n")
    with pytest.raises(ValueError, match="'catalog' block is gone"):
        Registry.from_yaml(path)


def test_every_available_dataset_documents_itself(registry: Registry) -> None:
    for ds in registry:
        if ds.status is not Status.AVAILABLE:
            continue
        assert ds.summary and ds.formats, f"{ds.id} does not say what it delivers"
        assert ds.guide and (ROOT / ds.guide).is_file(), f"{ds.id} has no usage guide on disk"
        assert ds.examples, f"{ds.id} lists no examples"
        for example in ds.examples:
            assert (ROOT / example).is_file(), f"{ds.id} lists a missing example {example}"


def test_reader_extras_are_packaged_optional_dependencies() -> None:
    extras = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    assert set(READER_EXTRAS) <= set(extras)
