import pkgutil
import tomllib
from datetime import timedelta
from importlib import import_module
from pathlib import Path

import pytest

import usdata
from usdata import providers
from usdata.models import READER_EXTRAS, BBox, Query, Status
from usdata.providers import Provider, load_adapter
from usdata.providers.base import NotImplementedProvider
from usdata.registry import DatasetNotFound, Registry, default_registry

ROOT = Path(__file__).resolve().parents[2]

# The window each adapter enforces, named where the adapter defines or imports it. Reading
# the constants is why this module may import provider packages, as tests/adapters do.
WINDOW_CONSTANTS = {
    "noaa:nexrad-level2": ("usdata.providers.noaa.nexrad", "MAX_WINDOW"),
    "noaa:nexrad-level3": ("usdata.providers.noaa.nexrad_level3", "MAX_WINDOW"),
    "noaa:goes-abi": ("usdata.providers.noaa.goes", "MAX_WINDOW"),
    "noaa:goes-glm": ("usdata.providers.noaa.glm", "MAX_WINDOW"),
    "noaa:mrms": ("usdata.providers.noaa.mrms", "MAX_WINDOW"),
    "noaa:hrrr": ("usdata.providers.noaa.hrrr", "MAX_WINDOW"),
    # GFS inherits its window from the shared ModelRuns base in the HRRR module.
    "noaa:gfs": ("usdata.providers.noaa.hrrr", "MAX_WINDOW"),
    "noaa:coops-water-levels": ("usdata.providers.noaa.coops", "MAX_INTERVAL"),
    "noaa:coops-tide-predictions": ("usdata.providers.noaa.coops", "MAX_PREDICTION_INTERVAL"),
}


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


def test_systems_group_datasets_under_one_provider(registry: Registry) -> None:
    noaa = registry.systems("noaa")
    assert registry.systems() == noaa  # every declared system is NOAA's for now
    assert registry.system("noaa:ncei-access").name == "NCEI Access Data Service"
    assert {ds.system for ds in registry.list(provider="noaa")} > {None}
    assert registry.systems("usgs") == []


def test_every_declared_system_has_a_dataset(registry: Registry) -> None:
    named = {ds.system for ds in registry if ds.system}
    assert {system.id for system in registry.systems()} == named


def test_unknown_or_foreign_systems_are_rejected(registry: Registry) -> None:
    ds = registry.get("noaa:ghcn-daily")
    systems = registry.systems()
    with pytest.raises(ValueError, match="unknown system 'noaa:nope'"):
        Registry([ds.model_copy(update={"system": "noaa:nope"})], systems=systems)
    usgs = registry.get("usgs:water-daily").model_copy(update={"system": "noaa:ncei-access"})
    with pytest.raises(ValueError, match="belongs to provider 'noaa'"):
        Registry([usgs], systems=systems)


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


def test_every_available_dataset_can_be_cited(registry: Registry) -> None:
    for ds in registry:
        if ds.status is not Status.AVAILABLE:
            continue
        assert ds.citation, f"{ds.id} says nothing about how to cite it"
        assert ds.terms and ds.terms.startswith("https://"), f"{ds.id} has no terms URL"


def test_declared_windows_equal_the_windows_the_adapters_enforce(registry: Registry) -> None:
    for dataset_id, (module_name, constant) in WINDOW_CONSTANTS.items():
        limits = registry.get(dataset_id).limits
        assert limits is not None and limits.max_window is not None, dataset_id
        assert limits.max_window == getattr(import_module(module_name), constant), dataset_id


def test_every_adapter_window_constant_is_declared_in_the_registry() -> None:
    """A window a new adapter enforces has to reach the registry, not only the module."""
    found: set[tuple[str, str]] = set()
    for info in pkgutil.walk_packages(providers.__path__, f"{providers.__name__}."):
        module = import_module(info.name)
        found |= {
            (info.name, name)
            for name, value in vars(module).items()
            if name.startswith("MAX_") and isinstance(value, timedelta)
        }
    assert found == set(WINDOW_CONSTANTS.values())


def test_reader_extras_are_packaged_optional_dependencies() -> None:
    extras = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    assert set(READER_EXTRAS) <= set(extras)


def test_list_defaults_to_available_datasets_in_registry_order(registry: Registry) -> None:
    listed = registry.list()
    assert [ds.id for ds in listed] == [ds.id for ds in registry if ds.status is Status.AVAILABLE]


def test_list_filters_by_provider_domain_and_status(registry: Registry) -> None:
    assert {ds.provider for ds in registry.list(provider="usgs", status="all")} == {"usgs"}
    assert "noaa:nexrad-level2" in {ds.id for ds in registry.list(domain="weather-radar")}
    planned = registry.list(status="planned")
    assert planned and all(ds.status is Status.PLANNED for ds in planned)
    assert len(registry.list(status="all")) == len(registry)


def test_list_matches_a_format_case_insensitively(registry: Registry) -> None:
    ids = {ds.id for ds in registry.list(format="csv")}
    assert {"noaa:ghcn-daily", "noaa:storm-events"} <= ids  # declared 'CSV' and 'gzip CSV'
    assert "noaa:nexrad-level2" not in ids
    assert registry.list(format="CSV") == registry.list(format="csv")


def test_list_filters_by_reader_extra_or_bytes_only(registry: Registry) -> None:
    assert all(ds.reader == "pandas" for ds in registry.list(reader="pandas"))
    bytes_only = registry.list(reader="none")
    assert [ds.id for ds in bytes_only] == ["noaa:nexrad-level3"]
    assert all(ds.reader is None for ds in bytes_only)


def test_list_filters_by_declared_capability(registry: Registry) -> None:
    subsetting = registry.list(capability="temporal_subset")
    assert subsetting and all(ds.capabilities.temporal_subset for ds in subsetting)
    assert len(subsetting) < len(registry.list())


def test_list_combines_filters(registry: Registry) -> None:
    combined = registry.list(provider="noaa", domain="weather-radar", reader="grib")
    assert [ds.id for ds in combined] == ["noaa:mrms"]
    assert registry.list(provider="noaa", domain="air-quality", status="all") == []


def test_list_rejects_an_unknown_capability_or_status(registry: Registry) -> None:
    with pytest.raises(ValueError, match="unknown capability 'subset'; choose one of"):
        registry.list(capability="subset")
    with pytest.raises(ValueError, match="unknown status 'retired'; choose one of"):
        registry.list(status="retired")


def test_search_applies_the_listing_filters_before_scoring(registry: Registry) -> None:
    assert [r.dataset.id for r in registry.search(Query(text="radar"), reader="grib")] == [
        "noaa:mrms"
    ]
    assert registry.search(Query(text="radar"), domain="air-quality") == []
    assert registry.search(Query(text="radar"), capability="spatial_subset") == []


def test_package_level_datasets_delegates_to_the_default_registry(registry: Registry) -> None:
    assert usdata.datasets(domain="weather-radar") == registry.list(domain="weather-radar")
    assert usdata.datasets(status="all") == registry.list(status="all")
    assert usdata.search("radar", reader="grib") == registry.search(
        Query(text="radar"), reader="grib"
    )


def test_search_status_supersedes_include_planned(registry: Registry) -> None:
    planned = registry.search(Query(), include_planned=False, status="planned")
    assert planned and all(r.dataset.status is Status.PLANNED for r in planned)
    assert len(registry.search(Query(), include_planned=True, status="available")) == len(
        registry.list()
    )
