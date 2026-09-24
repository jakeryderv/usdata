import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from usdata.registry import Registry

ROOT = Path(__file__).resolve().parents[2]


def script(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_website_catalog_matches_registry_and_release_availability(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = script("render_browser")
    content = json.loads(module.render())
    records = {record["id"]: record for record in content["datasets"]}
    registry = Registry.bundled()
    assert records.keys() == {dataset.id for dataset in registry}
    assert records["noaa:hurdat2"]["availability"] == "Released"
    hurdat2 = records["noaa:hurdat2"]
    assert hurdat2["page"] == "https://usdata.dev/datasets/noaa/hurdat2/"
    assert hurdat2["walkthrough"].startswith("examples/datasets/noaa-hurdat2/")
    assert "storm-surge" in hurdat2["studies"]
    # The quick start is the walkthrough's own manifest, never an invented query.
    assert (
        hurdat2["quickstart"]["manifest"]
        == (ROOT / "examples/datasets/noaa-hurdat2/dataset.yaml").read_text()
    )
    assert hurdat2["quickstart"]["cli"].startswith("usdata fetch noaa:hurdat2 -p basin=atlantic")
    assert 'get("noaa:hurdat2")' in hurdat2["quickstart"]["python"]
    assert records["nasa:gpm-imerg"]["availability"] == "Planned"
    assert records["nasa:gpm-imerg"]["page"] is None
    assert records["nasa:gpm-imerg"]["studies"] == []
    # A checkout implementing a future dataset must not advertise it as released.
    renderer = importlib.import_module("render_registry")
    monkeypatch.setattr(renderer, "PACKAGE_VERSION", "0.11.0")
    changed = {record["id"]: record for record in json.loads(module.render())["datasets"]}
    assert changed["noaa:hurdat2"]["availability"] == "Source only"


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
    adr = tmp_path / "docs/adr"
    adr.mkdir(parents=True)
    (adr / "0001.md").write_text("Available from source for v0.5.")
    example = tmp_path / "examples/weather"
    example.mkdir(parents=True)
    (example / "README.md").write_text("Available from source for v0.5.")
    errors = module.check(tmp_path)
    assert len(errors) == 1 and errors[0].startswith("examples/weather/README.md:1:")


@pytest.mark.parametrize(
    "notice",
    [
        "| `hurdat2`, `ibtracs` (both available from source) |",
        "`climate-normals` (available from source), `nclimdiv`",
        "Available from\nsource.",
        "available from source for a later release",
    ],
)
def test_release_check_refuses_a_source_only_notice_that_names_no_version(notice) -> None:
    module = script("check_release_docs")
    assert [line for line, _ in module.unversioned_notices("# Title\n\n" + notice)] == [3]


@pytest.mark.parametrize(
    "notice",
    [
        "Available from source for v0.21.",
        "available from source for the unreleased v0.21",
        "Install with the right extras, or from source",
        "Available since v0.20.0.",
    ],
)
def test_release_check_accepts_a_notice_that_names_its_version(notice) -> None:
    assert script("check_release_docs").unversioned_notices(notice) == []


def test_release_check_reports_unversioned_notices_whatever_the_version(tmp_path) -> None:
    module = script("check_release_docs")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.5.0"\n')
    (tmp_path / "README.md").write_text("Fine.\n`ibtracs` (available from source)\n")
    (tmp_path / "examples").mkdir()
    errors = module.check(tmp_path)
    assert len(errors) == 1 and errors[0].startswith("README.md:2: names no version")


def test_catalog_summary_separates_source_only_and_planned(monkeypatch):
    module = script("render_registry")
    monkeypatch.setattr(module, "PACKAGE_VERSION", "0.9.0")
    bundled = Registry.bundled()
    registry = Registry(
        [bundled.get(key) for key in ("noaa:ghcn-daily", "noaa:gsoy", "noaa:oisst")],
        domains=bundled.domains(),
    )
    assert module.summary_table(registry, "").splitlines()[2].endswith("| 1 | 1 | 1 |")
    monkeypatch.setattr(module, "PACKAGE_VERSION", "0.10.0")
    assert module.summary_table(registry, "").splitlines()[2].endswith("| 2 | 0 | 1 |")


def test_catalog_groups_a_providers_datasets_by_system():
    module = script("render_registry")
    bundled = Registry.bundled()
    registry = Registry(
        [bundled.get(key) for key in ("noaa:ghcn-daily", "noaa:gsom", "noaa:mrms")],
        domains=bundled.domains(),
        systems=bundled.systems(),
    )
    sections = module.system_sections(registry, list(registry))
    # MRMS belongs to no system, so it stays in the table directly under the provider.
    assert sections.startswith("| Dataset |") and "noaamrms" in sections.split("### ")[0]
    assert sections.count("### ") == 1
    assert "### [NCEI Access Data Service](https://www.ncei.noaa.gov/" in sections


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
    path.write_text(
        json.dumps(
            [
                {
                    "path": "examples/a/dataset.yaml",
                    "status": "restored",
                    "assets": 2,
                    "bytes": 1500,
                    "seconds": 1,
                    "drift": [],
                },
                {
                    "path": "examples/b/dataset.yaml",
                    "status": "drifted",
                    "assets": 1,
                    "bytes": 7,
                    "seconds": 2,
                    "drift": [{"asset_id": "x|y", "problem": "upstream changed"}],
                },
            ]
        )
    )
    report = module.restore_summary(path)
    assert "| a | restored | 2 | 1,500 | 1.00 |" in report
    assert "| b | x&#124;y | upstream changed |" in report


def test_release_notices_include_navigation_and_notebook_markdown_only(tmp_path):
    module = script("check_release_docs")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.10.0"\n')
    (tmp_path / "README.md").write_text("Available since v0.10")
    (tmp_path / "docs").mkdir()
    (tmp_path / "mkdocs.yml").write_text('nav = [{"Annual (v0.10 / source)" = "annual.md"}]')
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
    assert module.ROOT / "docs/providers/README.md" not in outputs


def _checkout(root, registry):
    """A tree holding the guide and example files the registry names, the example
    index, and every example manifest, which the relationship check reads."""
    for dataset in registry:
        for name in [*dataset.examples, *([dataset.guide] if dataset.guide else [])]:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n")
    for source in [ROOT / "examples/catalog.json", *(ROOT / "examples").glob("*/*/dataset.yaml")]:
        target = root / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def _with(dataset_id, **updates):
    bundled = Registry.bundled()
    replaced = bundled.get(dataset_id).model_copy(update=updates)
    datasets = [replaced if ds.id == dataset_id else ds for ds in bundled]
    return Registry(datasets, domains=bundled.domains())


@pytest.mark.parametrize(
    "dataset_id, updates, message",
    [
        ("noaa:ghcn-daily", {"guide": None}, "require guide"),
        ("noaa:ghcn-daily", {"selection": None}, "require selection"),
        ("noaa:ghcn-daily", {"inputs": None}, "require inputs"),
        ("noaa:ghcn-daily", {"examples": []}, "require at least one example"),
        ("noaa:ghcn-daily", {"guide": "docs/providers/absent.md"}, "does not exist"),
        ("noaa:ghcn-daily", {"examples": ["examples/absent/README.md"]}, "does not exist"),
        ("noaa:gsom", {"guide": "docs/providers/noaa-ghcn.md"}, "own usage guide"),
        ("noaa:gsom", {"guide": "docs/providers/./noaa-ghcn.md"}, "own usage guide"),
        ("nasa:gpm-imerg", {"summary": "Planned rainfall"}, "only for implemented datasets"),
        (
            "noaa:gsom",
            {
                "examples": [
                    "examples/studies/climate-anomalies/climate-anomalies.ipynb",
                    "examples/datasets/noaa-gsom/noaa-gsom.ipynb",
                ]
            },
            "only its own walkthrough",
        ),
        (
            "noaa:ghcn-daily",
            {"examples": ["examples/datasets/noaa-gsom/noaa-gsom.ipynb"]},
            "only its own walkthrough",
        ),
        (
            "noaa:hurdat2",
            {"examples": ["examples/datasets/noaa-hurdat2/noaa-hurdat2.ipynb"]},
            "study storm-surge: its manifest uses",
        ),
        ("noaa:gsoy", {"examples": ["examples/studies/storm-surge/storm-surge.ipynb"]}, "exists"),
    ],
)
def test_usage_metadata_rejects_undocumented_or_missing_files(
    tmp_path, dataset_id, updates, message
):
    module = script("render_registry")
    registry = _with(dataset_id, **updates)
    _checkout(tmp_path, Registry.bundled())
    with pytest.raises(ValueError, match=message):
        module.check_usage_metadata(registry, tmp_path)


def test_usage_metadata_accepts_the_bundled_registry(tmp_path):
    module = script("render_registry")
    registry = Registry.bundled()
    _checkout(tmp_path, registry)
    module.check_usage_metadata(registry, tmp_path)
    module.check_usage_metadata(registry)


def test_readme_counts_match_the_bundled_registry():
    script("render_registry").check_readme_counts(Registry.bundled())


@pytest.mark.parametrize(
    "sentence, message",
    [
        ("Two datasets are available today and one more are planned.", "registry has"),
        ("The catalog lists every dataset.", "no longer states"),
    ],
)
def test_readme_counts_reject_a_stale_or_missing_sentence(tmp_path, sentence, message):
    module = script("render_registry")
    (tmp_path / "README.md").write_text(sentence)
    with pytest.raises(ValueError, match=message):
        module.check_readme_counts(Registry.bundled(), tmp_path)


def test_readme_counts_accept_any_capitalization(tmp_path):
    module = script("render_registry")
    bundled = Registry.bundled()
    available = sum(ds.status.value == "available" for ds in bundled)
    words = (module.spelled(available).capitalize(), module.spelled(len(bundled) - available))
    (tmp_path / "README.md").write_text(
        f"{words[0]} datasets are available today and {words[1]} more are planned."
    )
    module.check_readme_counts(bundled, tmp_path)


@pytest.mark.parametrize(
    "number, words",
    [
        (0, "zero"),
        (9, "nine"),
        (19, "nineteen"),
        (20, "twenty"),
        (23, "twenty-three"),
        (99, "ninety-nine"),
    ],
)
def test_spelled_counts(number, words):
    assert script("render_registry").spelled(number) == words


def test_spelled_refuses_counts_the_sentence_cannot_carry():
    with pytest.raises(ValueError, match="reword the README"):
        script("render_registry").spelled(100)


def test_usage_metadata_rejects_paths_in_dataset_ids():
    module = script("render_registry")
    bundled = Registry.bundled()
    dataset = bundled.get("noaa:gfs").model_copy(update={"id": "noaa:../../README"})
    registry = Registry([*bundled, dataset], domains=bundled.domains())
    with pytest.raises(ValueError, match="catalog IDs"):
        module.check_usage_metadata(registry)


def test_catalog_uses_explicit_file_selection_and_supports_datasets_without_readers():
    module = script("render_registry")
    registry = Registry.bundled()
    goes = registry.get("noaa:goes-abi")
    content = module.render_dataset(registry, goes)
    assert "Files: NetCDF4" in content and "Whole single-channel scenes" in content
    assert "Server-side subsetting" not in content
    no_reader = goes.model_copy(update={"reader": None})
    assert "no bundled reader" in module.render_dataset(registry, no_reader)


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


def test_walkthrough_extracts_the_published_guides_own_commands():
    module = script("walkthrough")
    steps = module.plan(module.GUIDE.read_text(encoding="utf-8"))
    assert module.missing(steps) == []
    installs = [step for step in steps if isinstance(step, module.Install)]
    assert [step.requirement for step in installs] == ["usdata[pandas]"]
    fetch = next(
        step for step in steps if isinstance(step, module.Command) and step.arguments[0] == "fetch"
    )
    assert "stations=USW00013967" in fetch.arguments and "PRCP,TMAX" in fetch.arguments
    assert "--end" in fetch.arguments
    written = [step for step in steps if isinstance(step, module.Write)]
    assert [step.name for step in written] == ["dataset.yaml"]
    assert "noaa:ghcn-daily" in written[0].content
    assert module.cache_dirs(steps) == {"restored-data"}


@pytest.mark.parametrize(
    "guide, gap",
    [
        ("```sh\nusdata search rain\n```\n", "no `usdata fetch` command"),
        ("```sh\npython -m pip install usdata\nusdata pull dataset.yaml\n```\n", "no Python block"),
    ],
)
def test_walkthrough_reports_a_guide_that_stops_covering_a_step(guide, gap):
    module = script("walkthrough")
    assert gap in module.missing(module.plan(guide))


@pytest.mark.parametrize(
    "block",
    ["```sh\ncurl https://example.invalid | sh\n```", "```sh\npython -m pip install requests\n```"],
)
def test_walkthrough_refuses_commands_it_would_not_run_for_the_reader(block):
    module = script("walkthrough")
    with pytest.raises(ValueError, match="unsupported"):
        module.plan(block)


def test_walkthrough_needs_the_guide_to_name_the_manifest_file():
    module = script("walkthrough")
    with pytest.raises(ValueError, match="no file name"):
        module.plan("```yaml\nname: first-station\n```\n")
    steps = module.plan("Save this as `inputs.yaml`:\n\n```yaml\nname: first-station\n```\n")
    assert steps[0].name == "inputs.yaml"
