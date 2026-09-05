"""Install the built wheel in a temporary environment and exercise it outside the checkout."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory

from check_dist import check_dist

ROOT = Path(__file__).resolve().parents[1]
SMOKE = '''
import os
from importlib import resources
from pathlib import Path
from unittest.mock import patch
import httpx
import usdata
from usdata.manifest import Manifest
from usdata.providers.noaa.sites import get_site
from usdata.query import resolve_place

assert usdata.__version__ == os.environ["USDATA_EXPECTED_VERSION"]
assert Path(usdata.__file__).resolve().is_relative_to(Path.cwd().resolve())
assert (resources.files("usdata") / "py.typed").is_file()
assert usdata.get("noaa:ghcn-daily").id == "noaa:ghcn-daily"
assert usdata.search("radar")
assert resolve_place("OK").contains_point(35.39, -97.60)
assert resolve_place("Cleveland County, OK") == resolve_place("40027")
assert usdata.get("noaa:coastwatch-sst").status.value == "available"
assert get_site("KTLX").state == "OK"
manifest = Path("dataset.yaml")
manifest.write_text("""name: wheel-smoke
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params: {stations: USW00013967}
""")
assert not Manifest.load(manifest).validate_against()
transport = httpx.MockTransport(
    lambda request: httpx.Response(200, content=b"DATE,PRCP\\n2024-05-06,1\\n")
)
with patch("usdata.protocols.http.client", lambda: httpx.Client(transport=transport)):
    first = usdata.pull(manifest, root=Path("cache"))
    assert len(first.fetched) == 1
    assert usdata.pull(manifest, root=Path("cache")).fetched[0].from_cache
    assert usdata.verify(manifest, root=Path("cache")) == []
    first.fetched[0].path.unlink()
    assert not usdata.pull(manifest, root=Path("cache")).fetched[0].from_cache
print("installed-wheel smoke passed")
'''


def main() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    wheel = check_dist(ROOT / "dist", version).resolve()
    with TemporaryDirectory(prefix="usdata-wheel-") as directory:
        work = Path(directory)
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("VIRTUAL_ENV", None)
        env["USDATA_EXPECTED_VERSION"] = version
        subprocess.run(
            ["uv", "venv", "--python", sys.executable, str(work / "env")],
            check=True,
            env=env,
            cwd=work,
        )
        bindir = work / "env" / ("Scripts" if os.name == "nt" else "bin")
        python = bindir / ("python.exe" if os.name == "nt" else "python")
        cli = bindir / ("usdata.exe" if os.name == "nt" else "usdata")
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheel)],
            check=True,
            env=env,
            cwd=work,
        )
        subprocess.run([str(python), "-I", "-c", SMOKE], check=True, cwd=work, env=env)
        subprocess.run([str(cli), "--version"], check=True, cwd=work, env=env)
        subprocess.run([str(cli), "search", "radar"], check=True, cwd=work, env=env)
        subprocess.run(
            [str(cli), "verify", "dataset.yaml", "--cache-dir", "cache"],
            check=True,
            cwd=work,
            env=env,
        )


if __name__ == "__main__":
    main()
