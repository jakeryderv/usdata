import importlib
import types

import pytest

import usdata
from usdata import ChecksumMismatch, FetchedAsset, fetch, fetch_asset


def test_fetch_names_are_exported_from_the_package_root() -> None:
    assert usdata.fetch is fetch
    assert usdata.fetch_asset is fetch_asset
    assert usdata.FetchedAsset is FetchedAsset
    assert usdata.ChecksumMismatch is ChecksumMismatch


def test_fetch_names_are_listed_in_all() -> None:
    for name in ("ChecksumMismatch", "FetchedAsset", "fetch", "fetch_asset"):
        assert name in usdata.__all__
    assert usdata.__all__ == sorted(usdata.__all__)


def test_usdata_fetch_is_the_function_and_never_a_module() -> None:
    assert not isinstance(usdata.fetch, types.ModuleType)
    assert callable(usdata.fetch)


def test_the_fetch_submodule_is_private_with_no_shim() -> None:
    with pytest.raises(ImportError):
        importlib.import_module("usdata.fetch")
