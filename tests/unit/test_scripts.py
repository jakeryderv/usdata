import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHANGELOG = """# Changelog

## [Unreleased]

### Breaking

- Reject incomplete inputs.

## [0.4.0] - 2026-09-05

- Previous release.

[Unreleased]: https://example.test/old
[0.4.0]: https://example.test/old-release
"""


def test_roll_preserves_notes_and_rewrites_version_links(tmp_path, monkeypatch, capsys) -> None:
    module = script("changelog")
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG)
    monkeypatch.setattr(module, "PATH", path)
    module.roll("0.5.0")
    output = path.read_text()
    assert "## [Unreleased]\n\n## [0.5.0] - " in output
    assert "compare/v0.4.0...v0.5.0" in output
    assert "compare/v0.5.0...HEAD" in output
    assert "Previous release." in output
    capsys.readouterr()
    module.notes("0.5.0")
    assert capsys.readouterr().out.strip() == "### Breaking\n\n- Reject incomplete inputs."


@pytest.mark.parametrize(
    "version,body",
    [("0.4.0", CHANGELOG), ("0.5.0", CHANGELOG.replace("- Reject incomplete inputs.", ""))],
)
def test_invalid_release_keeps_changelog_unchanged(tmp_path, monkeypatch, version, body) -> None:
    module = script("changelog")
    path = tmp_path / "CHANGELOG.md"
    path.write_text(body)
    monkeypatch.setattr(module, "PATH", path)
    with pytest.raises(SystemExit):
        module.roll(version)
    assert path.read_text() == body


@pytest.mark.parametrize("fault", [None, "wheel-version", "sdist-version", "missing-data"])
def test_release_distribution_validation(tmp_path, fault) -> None:
    module = script("check_dist")
    wheel = tmp_path / "usdata-0.4.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        version = "0.3.0" if fault == "wheel-version" else "0.4.0"
        archive.writestr("usdata-0.4.0.dist-info/METADATA", f"Name: usdata\nVersion: {version}\n")
        for name in module.REQUIRED:
            if fault != "missing-data" or name != "usdata/py.typed":
                archive.writestr(name, "")
    with tarfile.open(tmp_path / "usdata-0.4.0.tar.gz", "w:gz") as archive:
        version = "0.3.0" if fault == "sdist-version" else "0.4.0"
        body = f"Name: usdata\nVersion: {version}\n".encode()
        info = tarfile.TarInfo("usdata-0.4.0/PKG-INFO")
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))
    if fault:
        with pytest.raises(ValueError):
            module.check_dist(tmp_path, "0.4.0")
    else:
        assert module.check_dist(tmp_path, "0.4.0") == wheel


def test_generated_docs_distinguish_unreleased_implementations(monkeypatch) -> None:
    from usdata.registry import default_registry

    module = script("render_registry")
    monkeypatch.setattr(module, "PACKAGE_VERSION", "0.4.0")
    reg = default_registry()
    water = reg.get("usgs:water-daily")
    assert module.implementation_version(water) == "unreleased; planned 0.5"
    assert "Implemented, unreleased (planned 0.5)" in module.render_roadmap_block(reg)
    monkeypatch.setattr(module, "PACKAGE_VERSION", "0.5.0")
    assert module.implementation_version(water) == "since 0.5"
    assert "Included since 0.5" in module.render_roadmap_block(reg)


def test_census_kml_parser_preserves_geometry_names_and_fips() -> None:
    module = script("build_places")
    kml = b"""<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark>
    <ExtendedData><SchemaData>
    <SimpleData name="GEOID">40027</SimpleData>
    <SimpleData name="NAME">Cleveland</SimpleData>
    <SimpleData name="NAMELSAD">Cleveland County</SimpleData>
    <SimpleData name="STUSPS">OK</SimpleData>
    <SimpleData name="STATE_NAME">Oklahoma</SimpleData>
    </SchemaData></ExtendedData><MultiGeometry><Polygon><outerBoundaryIs><LinearRing>
    <coordinates>-98,34,0 -97,34,0 -97,36,0 -98,34,0</coordinates>
    </LinearRing></outerBoundaryIs></Polygon></MultiGeometry>
    </Placemark></kml>"""
    (row,) = module.parse_kml(kml, "county")
    assert row["geoid"] == "40027" and row["qualified_name"] == "Cleveland County"
    assert (row["west"], row["south"], row["east"], row["north"]) == (
        "-98.000000",
        "34.000000",
        "-97.000000",
        "36.000000",
    )
    with pytest.raises(ValueError, match="outside WGS84"):
        module.parse_kml(kml.replace(b"-98,34,0", b"-198,34,0"), "county")
    with pytest.raises(ValueError, match="no KML"):
        module.parse_kml(b'<kml xmlns="http://www.opengis.net/kml/2.2"/>', "county")
