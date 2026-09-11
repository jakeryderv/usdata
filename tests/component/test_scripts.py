import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest
import yaml

from usdata.registry import Registry

ROOT = Path(__file__).resolve().parents[2]


def script(name):
    path = ROOT / "docs/build.py" if name == "docs_site" else ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("fault", [None, "cleared", "error", "order", "large", "malformed"])
def test_notebook_saved_execution_checks(tmp_path, fault) -> None:
    module = script("check_notebooks")
    output = {"output_type": "stream", "name": "stdout", "text": ["Small saved result\n"]}
    cell = {
        "cell_type": "code",
        "metadata": {},
        "source": ["print('Small saved result')"],
        "execution_count": 1,
        "outputs": [output],
    }
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [cell]}
    if fault == "cleared":
        cell.update(execution_count=None, outputs=[])
    elif fault == "error":
        cell["outputs"] = [{"output_type": "error", "ename": "RuntimeError"}]
    elif fault == "order":
        cell["execution_count"] = 3
    elif fault == "large":
        output["text"] = ["x" * (module.MAX_OUTPUT_BYTES + 1)]
    path = tmp_path / "example.ipynb"
    path.write_text("{" if fault == "malformed" else json.dumps(notebook), encoding="utf-8")
    errors = module.check_notebook(path)
    assert bool(errors) == (fault is not None)


CHANGELOG = """# Changelog

## [Unreleased]

### Breaking

- Reject incomplete inputs.

## [0.4.0] - 2026-09-05

- Previous release.

[Unreleased]: https://example.test/old
[0.4.0]: https://example.test/old-release
"""


def test_changelog_reads_old_and_towncrier_headings(tmp_path, monkeypatch, capsys):
    module = script("changelog")
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        CHANGELOG + "\n## [0.5.0](https://example.test/release) - 2026-09-09\n\n- New note.\n"
    )
    monkeypatch.setattr(module, "PATH", path)
    module.notes("0.4.0")
    assert capsys.readouterr().out.strip() == "- Previous release."
    module.notes("0.5.0")
    assert capsys.readouterr().out.strip() == "- New note."


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
    assert module.implementation_version(water) == "Source only · intended for 0.5"
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


@pytest.mark.parametrize(
    "notice",
    [
        "Available from source for v0.5.",
        "Requires a source installation until v0.5 is published.",
        "# v0.5 / source",
        "The v0.5 features are implemented in source and await release.",
        "**Now (v0.5)**: feature work.",
        "Available from\nsource for v0.5.0.",
    ],
)
def test_release_check_catches_shipped_source_only_notices(notice) -> None:
    module = script("check_release_docs")
    assert module.stale_notices("# Title\n\n" + notice, "0.5.0")[0][0] == 3
    assert module.stale_notices(notice, "0.4.0") == []


def test_release_check_keeps_future_plans_and_excludes_history(tmp_path) -> None:
    module = script("check_release_docs")
    assert not module.stale_notices("Available since v0.5. **Shipped (v0.5)**", "0.5.0")
    assert not module.stale_notices("Available from source for v0.10.", "0.9.0")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.5.0"\n')
    (tmp_path / "README.md").write_text("Available since v0.5.")
    adr = tmp_path / "docs/content/adr"
    adr.mkdir(parents=True)
    (adr / "0001.md").write_text("Available from source for v0.5.")
    example = tmp_path / "examples/weather"
    example.mkdir(parents=True)
    (example / "README.md").write_text("Available from source for v0.5.")
    errors = module.check(tmp_path)
    assert len(errors) == 1 and errors[0].startswith("examples/weather/README.md:1:")


def test_catalog_summary_separates_source_only_and_planned(monkeypatch):
    module = script("render_registry")
    monkeypatch.setattr(module, "PACKAGE_VERSION", "0.9.0")
    bundled = Registry.bundled()
    registry = Registry(
        [bundled.get(key) for key in ("noaa:ghcn-daily", "noaa:gsoy", "noaa:gfs")],
        domains=bundled.domains(),
    )
    assert module.summary_table(registry, "").splitlines()[2].endswith("| 1 | 1 | 1 |")
    monkeypatch.setattr(module, "PACKAGE_VERSION", "0.10.0")
    assert module.summary_table(registry, "").splitlines()[2].endswith("| 2 | 0 | 1 |")


def test_radar_generator_writes_lf(tmp_path, monkeypatch):
    module = script("build_nexrad_sites")
    source = tmp_path / "stations.txt"
    columns = module.COLUMNS
    values = ["KOUN", "NORMAN", "OK", "35.2", "-97.4", "1200", "NEXRAD"]
    source.write_text(
        " ".join(f"{value:<10}" for value in columns)
        + "\n"
        + " ".join("-" * 10 for _ in columns)
        + "\n"
        + " ".join(f"{value:<10}" for value in values)
        + "\n"
    )
    output = tmp_path / "sites.csv"
    monkeypatch.setattr(module, "OUT", output)
    monkeypatch.setattr(module.sys, "argv", ["build_nexrad_sites.py", str(source)])
    module.main()
    assert output.read_bytes() == (
        b"id,name,state,lat,lon,elev_ft,type\nKOUN,Norman,OK,35.2,-97.4,1200,TEST\n"
    )


@pytest.mark.parametrize(
    "title", ["feat: add dataset", "fix(csv)!: preserve bytes", "docs: explain"]
)
def test_conventional_pr_titles(title):
    assert script("check_pr_title").valid_title(title)


@pytest.mark.parametrize("title", ["", "Add dataset", "fix:", "feat: \nrun", "fix: x\nci: y"])
def test_invalid_pr_titles(title):
    assert not script("check_pr_title").valid_title(title)


def test_site_links_follow_home_project_and_notebook_paths(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = script("docs_site")
    assert (
        module.page_links(
            "[setup](../../README.md#development) [reader](reference/readers.md)",
            Path("docs/content/index.md"),
        )
        == "[setup](project.md#development) [reader](docs/reference/readers.md)"
    )
    assert (
        module.page_links(
            "[start](../index.md) [book](../../../examples/sst-analysis/example.ipynb#plot)",
            Path("docs/content/guides/example.md"),
        )
        == "[start](../../index.md) [book](../../examples/sst-analysis/example.md#plot)"
    )
    assert (
        module.page_links(
            "[anchor](#install) [web](https://example.org/README.md)", Path("docs/content/index.md")
        )
        == "[anchor](#install) [web](https://example.org/README.md)"
    )


def test_ci_summary_reports_failures_skips_and_timings(tmp_path):
    module = script("ci_summary")
    path = tmp_path / "junit.xml"
    path.write_text("""<testsuites><testsuite>
      <testcase name="ok" time="1.25"/>
      <testcase name="failed" time="0.5"><failure message="bad | &lt;data&gt;"/></testcase>
      <testcase name="setup" time="0"><error message="setup failed"/></testcase>
      <testcase name="skip" time="0"><skipped message="optional dependency"/></testcase>
    </testsuite></testsuites>""")
    report = module.junit_summary(path)
    assert "| 4 | 1 | 2 | 1 | 1.75 |" in report
    assert "bad &#124; &lt;data&gt;" in report
    assert "optional dependency" in report and "setup failed" in report
    path.write_text(
        json.dumps([{"path": "examples/a/example.ipynb", "status": "failed", "seconds": 2}])
    )
    assert "a/example.ipynb | failed | 2.00" in module.notebook_summary(path)


def test_release_notices_include_navigation_and_notebook_markdown_only(tmp_path):
    module = script("check_release_docs")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.10.0"\n')
    (tmp_path / "README.md").write_text("Available since v0.10")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/mkdocs.yml").write_text('nav = [{"Annual (v0.10 / source)" = "annual.md"}]')
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "example.ipynb").write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "source": ["Available from source for the unreleased v0.10."],
                    },
                    {
                        "cell_type": "code",
                        "source": "# v0.10 / source",
                        "outputs": [{"text": "v0.10 / source"}],
                    },
                ]
            }
        )
    )
    errors = module.check(tmp_path)
    assert len(errors) == 2
    assert any("mkdocs.yml:1" in error for error in errors)
    assert any("example.ipynb:cell 1:1" in error for error in errors)


def test_catalog_generator_owns_only_generated_directory():
    module = script("render_registry")
    outputs = module.render_all(Registry.bundled())
    assert outputs and all(path.is_relative_to(module.CATALOG_DIR) for path in outputs)
    assert module.ROOT / "README.md" not in outputs
    assert module.ROOT / "docs/content/providers/README.md" not in outputs


@pytest.mark.parametrize(
    "fault",
    ["missing", "unknown", "duplicate", "alias", "outside", "typo", "extra", "example", "format"],
)
def test_catalog_rejects_invalid_guide_metadata(tmp_path, fault):
    module = script("render_registry")
    raw = yaml.safe_load((ROOT / "src/usdata/data/registry.yaml").read_text())
    (tmp_path / "pyproject.toml").write_text((ROOT / "pyproject.toml").read_text())
    for entry in raw["catalog"].values():
        for example in entry["examples"]:
            file = tmp_path / example
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("example")
        path = tmp_path / entry["guide"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Usage\n")
    entry = raw["catalog"]["noaa:ghcn-daily"]
    if fault == "missing":
        del raw["catalog"]["noaa:ghcn-daily"]
    elif fault == "unknown":
        raw["catalog"]["noaa:typo"] = entry
    elif fault == "duplicate":
        raw["catalog"]["noaa:gsom"]["guide"] = entry["guide"]
    elif fault == "alias":
        raw["catalog"]["noaa:gsom"]["guide"] = entry["guide"].replace("providers/", "providers/./")
    elif fault == "extra":
        entry["reader_extra"] = "nonexistent"
    elif fault == "example":
        entry["examples"] = ["examples/missing.md"]
    elif fault == "format":
        entry["formats"] = [""]
    elif fault == "outside":
        entry["guide"] = "../outside.md"
    else:
        entry["gudie"] = entry["guide"]
    path = tmp_path / "src/usdata/data/registry.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError):
        module.catalog_entries(Registry.bundled(), tmp_path)


def test_catalog_sync_detects_obsolete_outputs_and_preserves_unrecognized_files(
    tmp_path, monkeypatch
):
    module = script("render_registry")
    monkeypatch.setattr(module, "CATALOG_DIR", tmp_path)
    old = tmp_path / "old.md"
    old.write_text(module.GENERATED_NOTE)
    assert module.sync({}, check=True) == [old]
    assert old.exists()
    module.sync({}, check=False)
    assert not old.exists()
    old.write_text("handwritten content")
    with pytest.raises(ValueError, match="unrecognized"):
        module.sync({}, check=False)
    assert old.read_text() == "handwritten content"
    with pytest.raises(ValueError, match="inside"):
        module.sync({tmp_path / ".." / "README.md": "bad"}, check=False)


def test_composed_guide_links_resolve_from_their_original_directory(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = script("docs_site")
    destination = Path("docs/generated/catalog/noaa/ghcn-daily.md")
    monkeypatch.setattr(
        module, "PAGE_PATHS", {Path("docs/content/providers/noaa-ghcn.md"): destination}
    )
    assert module.page_links(
        "[reader](../reference/readers.md) [NOAA](noaa.md) "
        "[example](../../../examples/weather-and-streamflow/example.ipynb)",
        Path("docs/content/providers/noaa-ghcn.md"),
        destination,
    ) == (
        "[reader](../../../reference/readers.md) [NOAA](../../../providers/noaa.md) "
        "[example](../../../../examples/weather-and-streamflow/example.md)"
    )
    assert module.page_links(
        "[daily](noaa-ghcn.md#dates)", Path("docs/content/providers/noaa.md")
    ) == ("[daily](../generated/catalog/noaa/ghcn-daily.md#dates)")


def test_catalog_rejects_paths_in_dataset_ids():
    module = script("render_registry")
    bundled = Registry.bundled()
    dataset = bundled.get("noaa:gfs").model_copy(update={"id": "noaa:../../README"})
    registry = Registry([*bundled, dataset], domains=bundled.domains())
    with pytest.raises(ValueError, match="catalog IDs"):
        module.catalog_entries(registry)


def test_dataset_navigation_covers_implementations_without_manual_entries(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = script("docs_site")
    renderer = script("render_registry")
    registry = Registry.bundled()
    entries = renderer.catalog_entries(registry)
    navigation = json.dumps(module.dataset_navigation(registry, entries))
    for ds in registry:
        path = module.site_path(renderer.dataset_path(ds)).as_posix()
        assert (path in navigation) == (ds.status.value == "available")


def test_catalog_uses_explicit_file_selection_and_supports_datasets_without_readers():
    module = script("render_registry")
    registry = Registry.bundled()
    entries = module.catalog_entries(registry)
    goes = registry.get("noaa:goes-abi")
    content = module.render_dataset(registry, goes, entries[goes.id])
    assert "Files: NetCDF4" in content and "Whole single-channel CONUS scenes" in content
    assert "Server-side subsetting" not in content
    no_reader = entries[goes.id].model_copy(update={"reader_extra": None})
    assert "no bundled reader" in module.render_dataset(registry, goes, no_reader)


def test_docs_publish_only_owned_content_and_explicit_inputs(tmp_path, monkeypatch):
    module = script("docs_site")
    for name in [
        "docs/content/index.md",
        "docs/content/guides/use.md",
        "docs/hosting/internal.md",
        "web/public/index.html",
        "README.md",
        "examples/selected/README.md",
        "examples/private/README.md",
    ]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Content")
    manifest = tmp_path / "docs/inputs.yml"
    manifest.write_text("files: [examples/selected/README.md]\n")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    assert {p.relative_to(tmp_path).as_posix() for p in module.source_paths()} == {
        "docs/content/index.md",
        "docs/content/guides/use.md",
        "examples/selected/README.md",
    }
    for invalid in ("../outside.md", "web/public/index.html", "examples/missing.md"):
        manifest.write_text(f"files: [{invalid}]\n")
        with pytest.raises(ValueError, match="invalid documentation input"):
            module.source_paths()


def test_docs_links_to_canonical_repository_policies():
    module = script("docs_site")
    assert module.page_links(
        "[contribute](../../CONTRIBUTING.md#workflow)", Path("docs/content/index.md")
    ) == ("[contribute](https://github.com/jakeryderv/usdata/blob/main/CONTRIBUTING.md#workflow)")
