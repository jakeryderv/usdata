"""Credential values stay out of what gets printed, and a missing one is refused (ADR 0039)."""

from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from usdata.models import CredentialSpec, Provenance
from usdata.providers import Credentials, MissingCredentials
from usdata.providers.base import required_credentials
from usdata.providers.credentials import encoded_forms

EMAIL = "me+usdata@example.org"
KEY = "s3cr3t-key"


def test_printing_credentials_shows_names_and_never_values() -> None:
    secrets = Credentials({"USDATA_AQS_EMAIL": EMAIL, "USDATA_AQS_KEY": KEY})
    for text in (repr(secrets), str(secrets), f"{secrets}", repr({"c": secrets})):
        assert text.count("***") >= 2 and EMAIL not in text and KEY not in text
    assert repr(secrets) == "Credentials(USDATA_AQS_EMAIL=***, USDATA_AQS_KEY=***)"
    assert secrets["USDATA_AQS_KEY"] == KEY and len(secrets) == 2


def test_credentials_are_read_only_and_copy_what_they_are_given() -> None:
    given = {"USDATA_AQS_KEY": KEY}
    secrets = Credentials(given)
    given["USDATA_AQS_KEY"] = "changed"
    assert secrets["USDATA_AQS_KEY"] == KEY
    with pytest.raises(TypeError):
        secrets["USDATA_AQS_KEY"] = "x"  # type: ignore[index]


def test_redact_removes_every_form_a_url_or_form_could_carry() -> None:
    secrets = Credentials({"USDATA_AQS_EMAIL": EMAIL, "USDATA_AQS_KEY": KEY})
    url = httpx.URL("https://aqs.example.test/data", params={"email": EMAIL, "key": KEY})
    text = f"{url} | {EMAIL} | {'me%2Busdata%40example.org'} | me%2Busdata%40example.org"
    redacted = secrets.redact(text)
    assert redacted == ("https://aqs.example.test/data?email=***&key=*** | *** | *** | ***"), (
        redacted
    )
    assert encoded_forms(EMAIL) >= {EMAIL, "me%2Busdata%40example.org"}


def test_redact_replaces_a_value_containing_another_whole() -> None:
    secrets = Credentials({"USDATA_A_KEY": "abc", "USDATA_B_KEY": "abcdef"})
    assert secrets.redact("x=abcdef y=abc") == "x=*** y=***"


def test_from_environment_keeps_set_values_stripped_and_drops_blank_ones() -> None:
    env = {"USDATA_AQS_EMAIL": f"  {EMAIL}\n", "USDATA_AQS_KEY": "   ", "OTHER": "x"}
    secrets = Credentials.from_environment(["USDATA_AQS_EMAIL", "USDATA_AQS_KEY"], env)
    assert dict(secrets) == {"USDATA_AQS_EMAIL": EMAIL}


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ({"variables": [], "signup": "https://x.test"}, "at least 1"),
        ({"variables": ["AQS_KEY"], "signup": "https://x.test"}, "USDATA_<SYSTEM>_<FIELD>"),
        ({"variables": ["USDATA_KEY"], "signup": "https://x.test"}, "USDATA_<SYSTEM>_<FIELD>"),
        ({"variables": ["usdata_aqs_key"], "signup": "https://x.test"}, "USDATA_<SYSTEM>"),
        ({"variables": ["USDATA_A_KEY", "USDATA_A_KEY"], "signup": "https://x"}, "distinct"),
        ({"variables": ["USDATA_A_KEY"], "signup": "http://x.test"}, "https URL"),
    ],
)
def test_a_credential_spec_names_variables_by_convention(spec: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        CredentialSpec.model_validate(spec)


def test_missing_credentials_name_the_variables_and_where_to_get_a_key(keyed) -> None:
    with pytest.raises(MissingCredentials) as caught:
        required_credentials(keyed.dataset, Credentials({"USDATA_TEST_EMAIL": EMAIL}))
    assert caught.value.missing == ["USDATA_TEST_KEY"]
    assert str(caught.value) == (
        "test:keyed needs USDATA_TEST_KEY set in the environment; "
        "request a key at https://keyed.example.test/signup"
    )
    blank = Credentials({"USDATA_TEST_EMAIL": EMAIL, "USDATA_TEST_KEY": ""})
    with pytest.raises(MissingCredentials, match="needs USDATA_TEST_KEY set"):
        required_credentials(keyed.dataset, blank)
    assert isinstance(caught.value, ValueError)  # A QueryError: the CLI exits 2.


def test_an_anonymous_dataset_needs_nothing_and_keeps_what_it_is_given(keyed) -> None:
    anonymous = keyed.dataset.model_copy(update={"credentials": None})
    assert dict(required_credentials(anonymous, None)) == {}
    assert dict(required_credentials(anonymous, Credentials({"USDATA_X_KEY": "v"}))) == {
        "USDATA_X_KEY": "v"
    }


def test_provenance_written_before_credentials_existed_still_reads() -> None:
    record = {
        "dataset_id": "noaa:x",
        "provider": "noaa",
        "source_url": "https://example.test/x",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "checksum": "sha256:" + "0" * 64,
        "size": 1,
        "usdata_version": "0.25.0",
    }
    assert Provenance.model_validate(record).credentials == []
