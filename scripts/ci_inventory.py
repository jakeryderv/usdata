"""Discover independent live test and notebook jobs from the repository."""

from __future__ import annotations

import json
from pathlib import Path

from check_notebooks import ROOT, notebook_paths


def inventory(root: Path = ROOT) -> dict[str, list[dict[str, str]]]:
    live = [
        {
            "id": path.stem,
            "path": path.relative_to(root).as_posix(),
            "extra": "netcdf" if path.stem == "test_goes_live" else "core",
        }
        for path in sorted((root / "tests/live").glob("test_*_live.py"))
    ]
    notebooks = [
        {"id": f"example-{index}", "path": path.relative_to(root).as_posix()}
        for index, path in enumerate(notebook_paths(root))
    ]
    if not live or not notebooks:
        raise ValueError("live tests and notebooks must both be present")
    return {"live": live, "notebooks": notebooks}


if __name__ == "__main__":
    for name, entries in inventory().items():
        print(f"{name}={json.dumps(entries)}")
