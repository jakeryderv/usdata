"""Generate state/county boxes from Census 2025 cartographic boundaries (1:500,000 KML).

Run `just places`, or pass --source-dir with the two downloaded ZIP files to
rebuild offline. KML parsing uses only the standard library; the shared HTTP
helper downloads inputs. Geometry is reduced to conservative bounding boxes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from usdata._files import atomic_write_text
from usdata.protocols import http

ROOT = Path(__file__).resolve().parents[1]
VINTAGE = "2025"
SCALE = "500k"
BASE = f"https://www2.census.gov/geo/tiger/GENZ{VINTAGE}/kml"
FILES = {kind: f"cb_{VINTAGE}_us_{kind}_{SCALE}.zip" for kind in ("state", "county")}
NS = "{http://www.opengis.net/kml/2.2}"
FIELDS = [
    "kind",
    "geoid",
    "name",
    "qualified_name",
    "state",
    "state_name",
    "west",
    "south",
    "east",
    "north",
]


def parse_kml(data: bytes, kind: str) -> list[dict[str, str]]:
    rows = []
    seen = set()
    for _, mark in ET.iterparse(io.BytesIO(data), events=("end",)):
        if mark.tag != NS + "Placemark":
            continue
        attrs = {e.attrib["name"]: e.text or "" for e in mark.iter(NS + "SimpleData")}
        geoid = attrs["GEOID"]
        if (
            not geoid.isascii()
            or not geoid.isdigit()
            or len(geoid) != (2 if kind == "state" else 5)
        ):
            raise ValueError(f"invalid {kind} GEOID: {geoid!r}")
        if geoid in seen:
            raise ValueError(f"duplicate GEOID: {geoid}")
        seen.add(geoid)
        points = [
            tuple(float(v) for v in point.split(",")[:2])
            for coords in mark.iter(NS + "coordinates")
            for point in (coords.text or "").split()
        ]
        if not points or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in points):
            raise ValueError(f"missing or invalid coordinates for {geoid}")
        west, east = min(p[0] for p in points), max(p[0] for p in points)
        south, north = min(p[1] for p in points), max(p[1] for p in points)
        if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
            raise ValueError(f"coordinates outside WGS84 bounds for {geoid}")
        rows.append(
            dict(
                zip(
                    FIELDS,
                    [
                        kind,
                        geoid,
                        attrs["NAME"],
                        attrs.get("NAMELSAD", attrs["NAME"]),
                        attrs["STUSPS"],
                        attrs.get("STATE_NAME", attrs["NAME"]),
                        *(f"{v:.6f}" for v in (west, south, east, north)),
                    ],
                    strict=True,
                )
            )
        )
        mark.clear()
    if not rows:
        raise ValueError("no KML placemarks")
    return rows


def render(source_dir: Path) -> tuple[str, dict]:
    rows = []
    sources = []
    for kind, filename in FILES.items():
        raw = (source_dir / filename).read_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            kml = [n for n in archive.namelist() if n.endswith(".kml")]
            if len(kml) != 1:
                raise ValueError(f"expected one KML file in {filename}")
            parsed = parse_kml(archive.read(kml[0]), kind)
        rows.extend(parsed)
        sources.append(
            {
                "url": f"{BASE}/{filename}",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "records": len(parsed),
            }
        )
    states = {r["geoid"]: r for r in rows if r["kind"] == "state"}
    if len(states) != 56 or sum(r["kind"] == "county" for r in rows) != 3235:
        raise ValueError("unexpected coverage for the pinned 2025 vintage")
    for row in rows:
        parent = states[row["geoid"][:2]]
        if parent["state"] != row["state"] or parent["name"] != row["state_name"]:
            raise ValueError(f"inconsistent state for {row['geoid']}")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(sorted(rows, key=lambda row: (len(row["geoid"]), row["geoid"])))
    text = output.getvalue()
    metadata = {
        "vintage": VINTAGE,
        "scale": "1:500,000",
        "coordinate_system": "WGS84 longitude/latitude",
        "generator": "scripts/build_places.py",
        "sources": sources,
        "csv_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "antimeridian": (
            "Conservative min/max envelopes; Alaska and Aleutians West span most longitudes."
        ),
    }
    return text, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir", type=Path, help="directory containing the Census ZIP inputs"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "src/usdata/data/places.csv")
    parser.add_argument(
        "--check", action="store_true", help="compare generated outputs without writing"
    )
    args = parser.parse_args()
    with TemporaryDirectory(prefix="usdata-places-") as temporary:
        source_dir = args.source_dir or Path(temporary)
        if args.source_dir is None:
            with http.client() as client:
                for filename in FILES.values():
                    http.download(f"{BASE}/{filename}", source_dir / filename, client)
        text, metadata = render(source_dir)
    outputs = {
        args.output: text,
        args.output.with_suffix(".sources.json"): json.dumps(metadata, indent=2) + "\n",
    }
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_bytes() != content.encode("utf-8"):
                raise SystemExit(f"stale generated file: {path}")
        else:
            atomic_write_text(path, content)
    print("2025 Census places: 56 states/territories and 3235 counties/equivalents")


if __name__ == "__main__":
    main()
