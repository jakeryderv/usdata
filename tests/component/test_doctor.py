from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import doctor as doctor_module
from usdata.cli import app
from usdata.doctor import READER_MODULES, CheckStatus, Report, diagnose, probe_hosts
from usdata.models import READER_EXTRAS

runner = CliRunner()


@pytest.fixture(autouse=True)
def temp_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Never report the developer's real cache or environment."""
    root = tmp_path / "cache" / "usdata"
    monkeypatch.setenv("USDATA_CACHE_DIR", str(root))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    return root


def _checks(report: Report, prefix: str) -> dict[str, tuple[CheckStatus, str]]:
    return {
        check.name: (check.status, check.detail)
        for check in report.checks
        if check.name.startswith(prefix)
    }


def test_every_reader_extra_has_modules() -> None:
    assert set(READER_MODULES) == set(READER_EXTRAS)


def test_report_covers_runtime_extras_cache_and_environment() -> None:
    report = diagnose()
    names = [check.name for check in report.checks]
    assert names[:3] == ["python", "platform", "usdata"]
    assert [f"extra:{extra}" for extra in READER_EXTRAS] == names[3:7]
    assert "cache" in names
    assert "env:USDATA_CACHE_DIR" in names
    assert "env:XDG_CACHE_HOME" not in names
    assert not any(name.startswith("host:") for name in names)


def test_missing_extra_warns_and_names_the_install(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = doctor_module.import_module

    def without_pandas(name: str) -> ModuleType:
        if name == "pandas":
            raise ModuleNotFoundError("No module named 'pandas'", name="pandas")
        return real_import(name)

    monkeypatch.setattr(doctor_module, "import_module", without_pandas)
    status, detail = _checks(diagnose(), "extra:pandas")["extra:pandas"]
    assert status is CheckStatus.WARN
    assert 'pip install "usdata[pandas]"' in detail


def test_installed_extra_reports_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("xradar")
    monkeypatch.setitem(sys.modules, "xradar", module)
    monkeypatch.setattr(doctor_module, "_module_version", lambda name: "9.9.9")
    status, detail = _checks(diagnose(), "extra:radar")["extra:radar"]
    assert (status, detail) == (CheckStatus.OK, "xradar 9.9.9")


def test_grib_reports_the_eccodes_library_version(monkeypatch: pytest.MonkeyPatch) -> None:
    eccodes = ModuleType("eccodes")
    monkeypatch.setattr(eccodes, "codes_get_api_version", lambda: "2.48.0", raising=False)
    for name in ("eccodes", "xarray", "numpy"):
        monkeypatch.setitem(sys.modules, name, eccodes if name == "eccodes" else ModuleType(name))
    monkeypatch.setattr(doctor_module, "_module_version", lambda name: "1.0")
    status, detail = _checks(diagnose(), "extra:grib")["extra:grib"]
    assert status is CheckStatus.OK
    assert detail.endswith("ecCodes library 2.48.0")


def test_grib_without_the_library_warns_with_the_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    def unloadable() -> str:
        raise RuntimeError("Could not find the ecCodes library")

    eccodes = ModuleType("eccodes")
    monkeypatch.setattr(eccodes, "codes_get_api_version", unloadable, raising=False)
    for name in ("eccodes", "xarray", "numpy"):
        monkeypatch.setitem(sys.modules, name, eccodes if name == "eccodes" else ModuleType(name))
    monkeypatch.setattr(doctor_module, "_module_version", lambda name: "1.0")
    status, detail = _checks(diagnose(), "extra:grib")["extra:grib"]
    assert status is CheckStatus.WARN
    assert "Could not find the ecCodes library" in detail
    assert "conda install" in detail


def test_missing_cache_is_ok_and_names_free_space(temp_cache: Path) -> None:
    status, detail = _checks(diagnose(), "cache")["cache"]
    assert status is CheckStatus.OK
    assert str(temp_cache) in detail
    assert "not created yet" in detail and "writable" in detail and "GiB free" in detail


def test_existing_cache_is_ok(temp_cache: Path) -> None:
    temp_cache.mkdir(parents=True)
    status, detail = _checks(diagnose(), "cache")["cache"]
    assert status is CheckStatus.OK and "exists, writable" in detail
    assert not diagnose().failed


def test_unwritable_cache_fails(temp_cache: Path) -> None:
    temp_cache.mkdir(parents=True)
    temp_cache.chmod(0o500)
    try:
        status, detail = _checks(diagnose(), "cache")["cache"]
        assert status is CheckStatus.FAIL and "not writable" in detail
        assert diagnose().failed
    finally:
        temp_cache.chmod(0o700)


def test_cache_path_that_is_a_file_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    occupied = tmp_path / "not-a-directory"
    occupied.write_text("")
    monkeypatch.setenv("USDATA_CACHE_DIR", str(occupied))
    status, detail = _checks(diagnose(), "cache")["cache"]
    assert status is CheckStatus.FAIL and "not a directory" in detail


def test_xdg_cache_home_is_reported_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/xdg-example")
    status, detail = _checks(diagnose(), "env:XDG_CACHE_HOME")["env:XDG_CACHE_HOME"]
    assert (status, detail) == (CheckStatus.OK, "/tmp/xdg-example")


def test_probe_hosts_are_a_handful_of_distinct_dataset_homepages() -> None:
    hosts = probe_hosts()
    assert 0 < len(hosts) <= 8
    assert len(set(hosts)) == len(hosts)
    assert "www.ncei.noaa.gov" in hosts


def test_network_probes_each_host_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_module, "probe_hosts", lambda: ["a.example", "b.example"])
    with respx.mock(assert_all_called=True) as mock:
        mock.head("https://a.example/").respond(200)
        mock.head("https://b.example/").mock(side_effect=httpx.ConnectTimeout("timed out"))
        report = diagnose(network=True)
    hosts = _checks(report, "host:")
    assert hosts["host:a.example"][0] is CheckStatus.OK
    assert "HTTP 200" in hosts["host:a.example"][1]
    assert hosts["host:b.example"][0] is CheckStatus.FAIL
    assert "unreachable: ConnectTimeout: timed out" in hosts["host:b.example"][1]
    assert report.failed


def test_network_probe_falls_back_to_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_module, "probe_hosts", lambda: ["a.example"])
    with respx.mock(assert_all_called=True) as mock:
        mock.head("https://a.example/").respond(405)
        mock.get("https://a.example/").respond(200)
        report = diagnose(network=True)
    status, detail = _checks(report, "host:")["host:a.example"]
    assert status is CheckStatus.OK and "HTTP 200" in detail


def test_cli_prints_aligned_lines_and_exits_zero() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    checks = json.loads(runner.invoke(app, ["doctor", "--json"]).stdout)["checks"]
    width = max(len(check["name"]) for check in checks)
    for line, check in zip(lines, checks, strict=True):
        assert line == f"{check['name']:<{width}}  {check['status']:<4}  {check['detail']}"


def test_cli_json_is_the_whole_report() -> None:
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    checks = json.loads(result.stdout)["checks"]
    assert {check["name"] for check in checks} >= {"python", "usdata", "cache"}
    assert all(check["status"] in {"ok", "warn", "fail"} for check in checks)


def test_cli_exits_one_when_a_check_fails(temp_cache: Path) -> None:
    temp_cache.mkdir(parents=True)
    temp_cache.chmod(0o500)
    try:
        assert runner.invoke(app, ["doctor"]).exit_code == 1
    finally:
        temp_cache.chmod(0o700)


def test_cli_without_network_makes_no_requests() -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route()
        assert runner.invoke(app, ["doctor"]).exit_code == 0
    assert not route.calls
