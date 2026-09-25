import httpx
import pytest
import respx

from usdata.protocols import http
from usdata.protocols.erddap import GridSlice, axis, griddap_url


def test_griddap_builder_rejects_url_injection() -> None:
    for dataset in ("../other", "sst?secret", "sst#part"):
        with pytest.raises(ValueError):
            griddap_url("https://example.test/erddap", dataset, ["sst"], [GridSlice(1, 2)])
    with pytest.raises(ValueError):
        griddap_url("https://example.test/erddap", "sst", ["sst&evil"], [GridSlice(1, 2)])
    with pytest.raises(ValueError):
        griddap_url("https://example.test/erddap", "sst", ["sst"], [GridSlice(float("nan"), 2)])


@pytest.mark.parametrize(
    ("body", "units"), [("zlev\nm\n0.0\n", "m"), ("zlev\n\n0.0\n", ""), ('zlev\n""\n0.0\n', "")]
)
def test_an_axis_reads_with_or_without_units(body: str, units: str) -> None:
    with respx.mock() as mock, http.client() as client:
        mock.get(url__startswith="https://example.test/erddap/griddap/sst.csv").respond(
            200, text=body
        )
        assert axis("https://example.test/erddap", "sst", "zlev", client) == (units, ["0.0"])


def test_an_axis_without_values_is_still_invalid() -> None:
    with respx.mock() as mock, http.client() as client:
        mock.get(url__startswith="https://example.test/erddap/griddap/sst.csv").respond(
            200, text="zlev\n\n"
        )
        with pytest.raises(httpx.DecodingError):
            axis("https://example.test/erddap", "sst", "zlev", client)
