from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, ClassVar

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from usdata.models import Asset, Dataset, Protocol, Query, Status
from usdata.providers.base import Provider, QueryError, described_params, params_error
from usdata.providers.params import (
    OptionalUpperStrList,
    StrList,
    UpperStrList,
    choice,
    int_list,
    int_range,
)


class Sample(BaseModel):
    """Stands in for an adapter's parameter model, exercising each shared coercion."""

    model_config = ConfigDict(extra="forbid")

    cycle: Annotated[int, int_range(0, 23)] = Field(
        description="Required UTC initialization hour of the run, 0 to 23."
    )
    hours: Annotated[list[int], int_list(0, 48)] = Field(
        description="Required forecast hour(s): an integer, list, or comma-separated string."
    )
    stations: StrList = Field(default_factory=list, description="Station ids to keep.")
    codes: UpperStrList = Field(
        default_factory=list, description="Product codes to keep, upper-cased."
    )
    site: OptionalUpperStrList = Field(default=None, description="One site id, or nothing at all.")
    file: Annotated[str, choice("sfc", "prs", "nat")] = Field(
        default="sfc", description="File variant: sfc (default), prs, or nat."
    )

    @model_validator(mode="after")
    def _one_station_per_hour(self) -> "Sample":
        if len(self.stations) > len(self.hours):
            raise ValueError("stations must name at most one station per forecast hour")
        return self


DATASET = Dataset(
    id="test:params",
    provider="test",
    title="Parameter declaration",
    protocol=Protocol.HTTP,
    domain="test",
    status=Status.AVAILABLE,
    since="0.1",
    adapter="test:Sampler",
)


class Sampler(Provider):
    """A migrated adapter: it declares a model and parses through it."""

    params_model = Sample

    def list_assets(self, query: Query) -> list[Asset]:
        self.parse_params(query, Sample)
        return []

    def fetch(self, asset: Asset, dest: Path) -> Path:
        return dest


class Handwritten(Provider):
    """An adapter that has not migrated: it keeps its own mapping and unknown-key check."""

    accepted_params: ClassVar[Mapping[str, str]] = {"station": "Station id."}

    def list_assets(self, query: Query) -> list[Asset]:
        self.check_params(query)
        return []

    def fetch(self, asset: Asset, dest: Path) -> Path:
        return dest


def parse(**params: Any) -> Sample:
    return Sampler(DATASET).parse_params(Query(params=params), Sample)


def error(**params: Any) -> str:
    with pytest.raises(QueryError) as raised:
        parse(**params)
    return str(raised.value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0, 0), (23, 23), ("07", 7), (" 12 ", 12)],
)
def test_int_fields_accept_the_shapes_the_cli_and_manifests_send(raw, expected) -> None:
    assert parse(cycle=raw, hours=1).cycle == expected


@pytest.mark.parametrize("raw", [True, False, 24, -1, 2.0, "2\uff10", "12.0", "", "x", None, [12]])
def test_int_fields_reject_lax_coercions_including_booleans(raw) -> None:
    assert error(cycle=raw, hours=1) == "cycle must be an integer from 0 to 23"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (3, [3]),
        ("3", [3]),
        ([0, "18"], [0, 18]),
        ((0, 1), [0, 1]),
        ("1, 2 ,3", [1, 2, 3]),
        ("1,,2", [1, 2]),
        ("2,02, 1,2", [2, 1]),
        ([5, 5, 4], [5, 4]),
    ],
)
def test_int_list_splits_dedupes_and_keeps_request_order(raw, expected) -> None:
    assert parse(cycle=0, hours=raw).hours == expected


@pytest.mark.parametrize("raw", ["", " ", [], (), ",,"])
def test_int_list_rejects_an_empty_selection(raw) -> None:
    assert error(cycle=0, hours=raw) == "hours must not be empty"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("KTLX", ["KTLX"]),
        (" KTLX , KOUN ", ["KTLX", "KOUN"]),
        (["KTLX", "KTLX", "KOUN"], ["KTLX", "KOUN"]),
        ("KTLX,,KOUN", ["KTLX", "KOUN"]),
    ],
)
def test_string_list_splits_strips_and_dedupes(raw, expected) -> None:
    assert parse(cycle=0, hours=[1, 2], stations=raw).stations == expected


@pytest.mark.parametrize("raw", [7, ["KTLX", 7], "", [" "]])
def test_string_list_rejects_non_text_and_empty_values(raw) -> None:
    assert error(cycle=0, hours=1, stations=raw).startswith("stations must ")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("n0b", ["N0B"]),
        (" n0b , NMD ", ["N0B", "NMD"]),
        ("n0b,N0B", ["N0B"]),
        (["ktlx", "KTLX", "kvnx"], ["KTLX", "KVNX"]),
    ],
)
def test_upper_string_list_folds_case_before_duplicates_collapse(raw, expected) -> None:
    assert parse(cycle=0, hours=1, codes=raw).codes == expected


@pytest.mark.parametrize("raw", ["", " ", [], ",,"])
def test_upper_string_list_rejects_an_empty_selection(raw) -> None:
    assert error(cycle=0, hours=1, codes=raw) == "codes must not be empty"


@pytest.mark.parametrize("raw", [7, ["KTLX", 7], None])
def test_upper_string_list_rejects_non_text_values(raw) -> None:
    assert error(cycle=0, hours=1, codes=raw) == (
        "codes must be text: one value, a list, or a comma-separated string"
    )


def test_an_optional_upper_string_list_separates_absent_from_empty_or_null() -> None:
    """Leaving the key out is the only way to mean "no value"; null and "" stay errors."""
    assert parse(cycle=0, hours=1).site is None
    assert parse(cycle=0, hours=1, site="ktlx").site == ["KTLX"]
    assert error(cycle=0, hours=1, site=None) == (
        "site must be text: one value, a list, or a comma-separated string"
    )
    assert error(cycle=0, hours=1, site="") == "site must not be empty"


def test_choice_names_the_accepted_values() -> None:
    assert parse(cycle=0, hours=1, file="nat").file == "nat"
    assert error(cycle=0, hours=1, file="wrfsfcf") == "file must be sfc, prs, or nat"
    assert error(cycle=0, hours=1, file=1) == "file must be sfc, prs, or nat"


def test_missing_fields_read_as_requirements_from_their_descriptions() -> None:
    assert error() == (
        "cycle is required: UTC initialization hour of the run, 0 to 23; "
        "hours is required: forecast hour(s): an integer, list, or comma-separated string"
    )


def test_several_problems_are_reported_on_one_line() -> None:
    assert error(cycle=99, hours="x", file="grib") == (
        "cycle must be an integer from 0 to 23; "
        "hours must be an integer from 0 to 48; "
        "file must be sfc, prs, or nat"
    )


def test_a_cross_field_rule_states_its_own_subject() -> None:
    assert error(cycle=0, hours=[1, 2], stations="KTLX,KOUN,KFDR") == (
        "stations must name at most one station per forecast hour"
    )


def test_unknown_keys_are_named_alone_whatever_else_is_wrong() -> None:
    assert error(b=1, a=2, cycle="noon") == "unsupported test:params params: a, b"


def test_a_declared_model_fills_accepted_params_and_forbids_extras() -> None:
    assert dict(Sampler.accepted_params) == {
        name: field.description for name, field in Sample.model_fields.items()
    }
    with pytest.raises(ValidationError):
        Sample(cycle=0, hours=[1], typo=2)  # type: ignore[call-arg]


def test_described_params_requires_a_description_per_field() -> None:
    class Undescribed(BaseModel):
        station: str

    with pytest.raises(ValueError, match=r"Undescribed\.station needs a Field"):
        described_params(Undescribed)


def test_validate_params_covers_both_declaration_forms() -> None:
    Sampler(DATASET).validate_params(Query(params={"cycle": 0, "hours": 1}))
    with pytest.raises(QueryError, match="cycle must be an integer"):
        Sampler(DATASET).validate_params(Query(params={"cycle": 99, "hours": 1}))
    Handwritten(DATASET).validate_params(Query(params={"station": "anything"}))
    with pytest.raises(QueryError, match="unsupported test:params params: typo"):
        Handwritten(DATASET).validate_params(Query(params={"typo": "x"}))


def test_params_error_keeps_a_messages_own_field_name() -> None:
    class Prefixed(BaseModel):
        file: str = Field(description="Variant.")

        @model_validator(mode="after")
        def _reject(self) -> "Prefixed":
            raise ValueError("file=subh (15-minute output) is out of scope")

    with pytest.raises(ValidationError) as raised:
        Prefixed(file="subh")
    assert str(params_error(raised.value, Prefixed)) == (
        "file=subh (15-minute output) is out of scope"
    )
