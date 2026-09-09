from usdata import get
from usdata.registry import Registry


def test_registry_infers_multiple_domains() -> None:
    datasets = [get("noaa:ghcn-daily"), get("noaa:nexrad-level2")]
    registry = Registry(datasets)
    assert {domain.id for domain in registry.domains()} == {d.domain for d in datasets}
