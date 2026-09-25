"""Generate state/county boxes from Census 2025 cartographic boundaries (1:500,000 KML).

Run `just places`, or pass --source-dir with the two downloaded ZIP files to
rebuild offline. KML parsing uses only the standard library; the shared HTTP
helper downloads inputs. Geometry is reduced to conservative bounding boxes.

A box cannot wrap across the antimeridian. A place whose polygons lie on both
sides of it, and whose plain envelope would therefore span most longitudes, is
clipped to its western-hemisphere polygons; the dropped eastern polygons are
recorded in places.sources.json. Only the places in CLIPPED may be clipped, so
a new vintage that adds or removes one fails instead of changing silently.
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
# Alaska and Aleutians West: the Near Islands and part of the Rat Islands lie at 172-180°E.
CLIPPED = {"02", "02016"}
Point = tuple[float, ...]


def envelope(polygons: list[list[Point]], geoid: str) -> tuple[tuple[float, ...], dict | None]:
    """Return (west, south, east, north), and a clip record for a place split by 180 degrees.

    A place whose longitudes span more than 180 degrees keeps only its polygons
    in the western hemisphere. A polygon on both sides of the prime meridian is
    refused, since dropping part of it would leave no correct box.
    """
    points = [p for polygon in polygons for p in polygon]
    if max(p[0] for p in points) - min(p[0] for p in points) <= 180:
        return bounds(points), None
    west = [polygon for polygon in polygons if all(p[0] < 0 for p in polygon)]
    east = [polygon for polygon in polygons if all(p[0] > 0 for p in polygon)]
    if len(west) + len(east) != len(polygons) or not west:
        raise ValueError(f"cannot clip {geoid} at the antimeridian: a polygon straddles it")
    dropped = bounds([p for polygon in east for p in polygon])
    return bounds([p for polygon in west for p in polygon]), {
        "geoid": geoid,
        "dropped_polygons": len(east),
        "dropped_box": [round(v, 6) for v in dropped],
    }


def bounds(points: list[Point]) -> tuple[float, ...]:
    return (
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )


def parse_kml(data: bytes, kind: str, clips: list[dict] | None = None) -> list[dict[str, str]]:
    """Parse one Census KML file into CSV rows, appending antimeridian clips to `clips`."""
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
        polygons = [
            [tuple(float(v) for v in point.split(",")[:2]) for point in (coords.text or "").split()]
            for coords in mark.iter(NS + "coordinates")
        ]
        polygons = [polygon for polygon in polygons if polygon]
        points = [p for polygon in polygons for p in polygon]
        if not points or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in points):
            raise ValueError(f"missing or invalid coordinates for {geoid}")
        if not all(-180 <= p[0] <= 180 and -90 <= p[1] <= 90 for p in points):
            raise ValueError(f"coordinates outside WGS84 bounds for {geoid}")
        (west, south, east, north), clip = envelope(polygons, geoid)
        if clip is not None:
            if clips is None:
                raise ValueError(f"{geoid} spans the antimeridian and would need clipping")
            clips.append(clip)
        if east - west > 180:
            raise ValueError(f"box for {geoid} spans the antimeridian")
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
    clips: list[dict] = []
    for kind, filename in FILES.items():
        raw = (source_dir / filename).read_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            kml = [n for n in archive.namelist() if n.endswith(".kml")]
            if len(kml) != 1:
                raise ValueError(f"expected one KML file in {filename}")
            parsed = parse_kml(archive.read(kml[0]), kind, clips)
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
    if {clip["geoid"] for clip in clips} != CLIPPED:
        raise ValueError(f"unexpected antimeridian clips: {sorted(c['geoid'] for c in clips)}")
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
        "antimeridian": {
            "rule": (
                "A place whose longitudes span more than 180 degrees keeps only its "
                "western-hemisphere polygons; no box crosses the antimeridian."
            ),
            "clipped": clips,
        },
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
