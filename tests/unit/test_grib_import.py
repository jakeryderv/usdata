"""ecCodes is imported after pyproj, whose PROJ copy must load first (see import_eccodes)."""

from __future__ import annotations

from types import ModuleType

import pytest

from usdata import _grib


def _record(monkeypatch: pytest.MonkeyPatch, *, installed: bool, broken: bool = False) -> list[str]:
    imported: list[str] = []

    def fake_import(name: str) -> ModuleType:
        imported.append(name)
        if broken and name == "pyproj":
            raise ImportError("libproj could not be loaded")
        return ModuleType(name)

    monkeypatch.setattr(_grib, "import_module", fake_import)
    monkeypatch.setattr(_grib, "find_spec", lambda name: object() if installed else None)
    return imported


def test_pyproj_is_imported_before_eccodes_when_installed(monkeypatch) -> None:
    imported = _record(monkeypatch, installed=True)
    assert _grib.import_eccodes().__name__ == "eccodes"
    assert imported == ["pyproj", "eccodes"]


def test_without_pyproj_only_eccodes_is_imported(monkeypatch) -> None:
    imported = _record(monkeypatch, installed=False)
    _grib.import_eccodes()
    assert imported == ["eccodes"]


def test_a_broken_pyproj_does_not_stop_the_grib_reader(monkeypatch) -> None:
    imported = _record(monkeypatch, installed=True, broken=True)
    assert _grib.import_eccodes().__name__ == "eccodes"
    assert imported == ["pyproj", "eccodes"]
