"""Validate the release version and bundled files in one wheel and one sdist."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

REQUIRED = {
    "usdata/py.typed",
    "usdata/data/registry.yaml",
    "usdata/data/places.csv",
    "usdata/data/places.sources.json",
    "usdata/data/nexrad_sites.csv",
}


def check_dist(directory: Path, version: str) -> Path:
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    files = [p for p in directory.iterdir() if p.name != ".gitignore"]
    if len(wheels) != 1 or len(sources) != 1 or len(files) != 2:
        raise ValueError("expected exactly one wheel and one sdist")
    wheel = wheels[0]
    if (
        not wheel.name.startswith(f"usdata-{version}-")
        or sources[0].name != f"usdata-{version}.tar.gz"
    ):
        raise ValueError("distribution filenames must match the release version")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        if missing := REQUIRED - names:
            raise ValueError(f"wheel missing bundled files: {sorted(missing)}")
        metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("expected exactly one wheel METADATA file")
        records = [archive.read(metadata[0])]
    with tarfile.open(sources[0], "r:gz") as archive:
        metadata = [
            m
            for m in archive.getmembers()
            if m.name.count("/") == 1 and m.name.endswith("/PKG-INFO")
        ]
        if len(metadata) != 1:
            raise ValueError("expected exactly one top-level sdist PKG-INFO file")
        file = archive.extractfile(metadata[0])
        if file is None:
            raise ValueError("sdist PKG-INFO must be a file")
        records.append(file.read())
    for raw in records:
        info = BytesParser().parsebytes(raw)
        if info["Name"] != "usdata" or info["Version"] != version:
            raise ValueError(f"expected usdata {version}, found {info['Name']} {info['Version']}")
    return wheel


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(check_dist(args.directory, args.version))
