"""Discover independent live test and notebook jobs from the repository."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_notebooks import ROOT, notebook_paths, pinned_manifests

# Live modules whose reader step needs an optional extra installed; others run core-only.
LIVE_EXTRAS = {
    "test_goes_live": "netcdf",
    "test_glm_live": "netcdf",
    "test_ibtracs_live": "netcdf",
    "test_mrms_live": "grib",
    "test_hrrr_live": "grib",
    "test_gfs_live": "grib",
    "test_rap_live": "grib",
    "test_nbm_live": "grib",
    # Their reader step ends in importorskip("pandas"), which core-only would turn into a skip.
    "test_aqs_daily_live": "pandas",
    "test_disaster_declarations_live": "pandas",
    "test_earthquakes_live": "pandas",
    "test_hurdat2_live": "pandas",
    "test_nws_vtec_live": "pandas",
}


def inventory(root: Path = ROOT) -> dict[str, list[dict[str, str]]]:
    live = [
        {
            "id": path.stem,
            "path": path.relative_to(root).as_posix(),
            "extra": LIVE_EXTRAS.get(path.stem, "core"),
        }
        for path in sorted((root / "tests/live").glob("test_*_live.py"))
    ]
    notebooks = [
        {"id": f"example-{index}", "path": path.relative_to(root).as_posix()}
        for index, path in enumerate(notebook_paths(root))
    ]
    restores = [
        {"id": manifest.parent.name, "path": manifest.relative_to(root).as_posix()}
        for manifest in pinned_manifests(root)
    ]
    if not live or not notebooks:
        raise ValueError("live tests and notebooks must both be present")
    return {"live": live, "notebooks": notebooks, "restores": restores}


def select_inventory(
    data: dict[str, list[dict[str, str]]], scope: str, target: str = ""
) -> dict[str, list[dict[str, str]]]:
    if scope not in {"all", "live", "notebooks", "restores", "minimum"}:
        raise ValueError(f"unknown scope: {scope}")
    if target and scope not in {"live", "notebooks", "restores"}:
        raise ValueError("target requires scope live, notebooks, or restores")
    selected = {name: entries if scope in ("all", name) else [] for name, entries in data.items()}
    if target:

        def matches(entry: dict[str, str]) -> bool:
            short = (
                entry["id"].removeprefix("test_").removesuffix("_live")
                if scope == "live"
                else Path(entry["path"]).parent.name  # the example folder, for both others
            )
            return target in {entry["id"], entry["path"], short}

        selected[scope] = [entry for entry in selected[scope] if matches(entry)]
        if len(selected[scope]) != 1:
            choices = ", ".join(entry["path"] for entry in data[scope])
            raise ValueError(
                f"target must select exactly one {scope} entry; choose from: {choices}"
            )
    return selected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope", choices=["all", "live", "notebooks", "restores", "minimum"], default="all"
    )
    parser.add_argument("--target", default="")
    args = parser.parse_args()
    try:
        selected = select_inventory(inventory(), args.scope, args.target)
    except ValueError as exc:
        parser.error(str(exc))
    for name, entries in selected.items():
        print(f"{name}={json.dumps(entries)}")
    print(f"minimum={str(args.scope in ('all', 'minimum')).lower()}")
