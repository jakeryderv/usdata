import pytest

from usdata.models import BBox, Query
from usdata.providers import Provider, load_adapter
from usdata.providers.base import NotImplementedProvider
from usdata.registry import DatasetNotFound, Registry, default_registry


@pytest.fixture(scope="module")
def registry() -> Registry:
    return default_registry()


def test_bundled_registry_loads(registry: Registry) -> None:
    assert len(registry) >= 3
    assert "noaa:nexrad-level2" in registry
    assert registry.providers() == {"noaa"}


def test_get_unknown_raises(registry: Registry) -> None:
    with pytest.raises(DatasetNotFound):
        registry.get("nope:nothing")


def test_search_ranks_by_keyword(registry: Registry) -> None:
    results = registry.search(Query(text="tornado radar"))
    assert results[0].dataset.id == "noaa:nexrad-level2"


def test_search_empty_text_returns_everything(registry: Registry) -> None:
    assert len(registry.search(Query())) == len(registry)


def test_search_filters_by_provider_and_bbox(registry: Registry) -> None:
    assert registry.search(Query(provider="usgs")) == []
    # NEXRAD extent excludes the eastern hemisphere; global datasets remain.
    eastern = BBox(west=100, south=0, east=110, north=10)
    ids = {r.dataset.id for r in registry.search(Query(bbox=eastern))}
    assert "noaa:nexrad-level2" not in ids
    assert "noaa:ghcn-daily" in ids


def test_every_adapter_resolves_to_a_provider(registry: Registry) -> None:
    for ds in registry:
        adapter = load_adapter(ds)
        assert isinstance(adapter, Provider)
        with pytest.raises(NotImplementedProvider):
            adapter.list_assets(Query())


def test_duplicate_ids_rejected(registry: Registry) -> None:
    ds = registry.get("noaa:ghcn-daily")
    with pytest.raises(ValueError, match="duplicate"):
        Registry([ds, ds])
