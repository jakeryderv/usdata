import subprocess
import sys

from usdata import __version__


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "usdata", *args], capture_output=True, text=True, check=False
    )


def test_python_m_usdata_reports_the_version() -> None:
    result = run("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == f"usdata {__version__}"


def test_python_m_usdata_runs_a_command() -> None:
    result = run("cite", "noaa:ghcn-daily")
    assert result.returncode == 0
    assert result.stdout.startswith("noaa:ghcn-daily\n  Menne, M.J.,")
