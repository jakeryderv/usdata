import importlib
import types

import usdata
from usdata.fetch import FetchedAsset, fetch, fetch_asset


def test_fetch_names_are_exported_from_the_package_root() -> None:
    assert usdata.fetch is fetch
    assert usdata.fetch_asset is fetch_asset
    assert usdata.FetchedAsset is FetchedAsset


def test_fetch_names_are_listed_in_all() -> None:
    for name in ("FetchedAsset", "fetch", "fetch_asset"):
        assert name in usdata.__all__
    assert usdata.__all__ == sorted(usdata.__all__)


def test_fetch_submodule_is_still_importable() -> None:
    module = importlib.import_module("usdata.fetch")
    assert isinstance(module, types.ModuleType)
    assert module.__name__ == "usdata.fetch"
