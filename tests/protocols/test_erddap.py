import pytest

from usdata.protocols.erddap import GridSlice, griddap_url


def test_griddap_builder_rejects_url_injection() -> None:
    for dataset in ("../other", "sst?secret", "sst#part"):
        with pytest.raises(ValueError):
            griddap_url("https://example.test/erddap", dataset, ["sst"], [GridSlice(1, 2)])
    with pytest.raises(ValueError):
        griddap_url("https://example.test/erddap", "sst", ["sst&evil"], [GridSlice(1, 2)])
    with pytest.raises(ValueError):
        griddap_url("https://example.test/erddap", "sst", ["sst"], [GridSlice(float("nan"), 2)])
