import pytest

from usdata.models import BBox, Query, Status
from usdata.providers import Provider, load_adapter
from usdata.providers.base import NotImplementedProvider
from usdata.registry import DatasetNotFound, Registry, default_registry


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
    results = registry.search(Query(text="tornado radar"))
    assert results[0].dataset.id == "noaa:nexrad-level2"


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
