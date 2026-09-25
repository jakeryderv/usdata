"""Generate state/county boxes from Census 2025 cartographic boundaries (1:500,000 KML).

Run `just places`, or pass --source-dir with the four downloaded source files to
rebuild offline. KML parsing uses only the standard library; the shared HTTP
helper downloads inputs. Geometry is reduced to conservative bounding boxes.

A box cannot wrap across the antimeridian. A place whose polygons lie on both
sides of it, and whose plain envelope would therefore span most longitudes, is
clipped to its western-hemisphere polygons; the dropped eastern polygons are
recorded in places.sources.json. Only the places in CLIPPED may be clipped, so
a new vintage that adds or removes one fails instead of changing silently.

Connecticut replaced its eight counties with nine planning regions as county
equivalents in 2022, and the 2025 files hold only the regions. Several sources
still key Connecticut by the old counties, so those eight are added from the
2021 county file, the last vintage to hold them, as `legacy_county` rows. Each
planning region lists the old counties it overlaps in `legacy_counties`, from
the Census town crosswalk: regions and counties are both made of whole towns,
so a region overlaps a county exactly when they share a town.
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
LEGACY_VINTAGE = "2021"
"""The last vintage holding Connecticut's eight counties rather than its planning regions."""
LEGACY_FILE = f"cb_{LEGACY_VINTAGE}_us_county_{SCALE}.zip"
LEGACY_URL = f"https://www2.census.gov/geo/tiger/GENZ{LEGACY_VINTAGE}/kml/{LEGACY_FILE}"
CROSSWALK_FILE = "ct_cou_to_cousub_crosswalk.txt"
CROSSWALK_URL = f"https://www2.census.gov/geo/docs/reference/ct_change/{CROSSWALK_FILE}"
CONNECTICUT = "09"
LEGACY_COUNTIES = {f"{CONNECTICUT}{code:03d}" for code in range(1, 16, 2)}
PLANNING_REGIONS = {f"{CONNECTICUT}{code}" for code in range(110, 200, 10)}
DOWNLOADS = {
    **{filename: f"{BASE}/{filename}" for filename in FILES.values()},
    LEGACY_FILE: LEGACY_URL,
    CROSSWALK_FILE: CROSSWALK_URL,
}
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
    "legacy_counties",
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


def parse_kml(
    data: bytes, kind: str, clips: list[dict] | None = None, state: str | None = None
) -> list[dict[str, str]]:
    """Parse one Census KML file into CSV rows, appending antimeridian clips to `clips`.

    Every kind but ``state`` expects five-digit county GEOIDs. `state`, a
    two-digit FIPS code, keeps only the placemarks of that state.
    """
    rows = []
    seen = set()
    for _, mark in ET.iterparse(io.BytesIO(data), events=("end",)):
        if mark.tag != NS + "Placemark":
            continue
        attrs = {e.attrib["name"]: e.text or "" for e in mark.iter(NS + "SimpleData")}
        geoid = attrs["GEOID"]
        if state is not None and not geoid.startswith(state):
            mark.clear()
            continue
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
                        "",
                    ],
                    strict=True,
                )
            )
        )
        mark.clear()
    if not rows:
        raise ValueError("no KML placemarks")
    return rows


def read_kml(raw: bytes, filename: str) -> bytes:
    """The one KML file inside a Census ZIP archive."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        kml = [n for n in archive.namelist() if n.endswith(".kml")]
        if len(kml) != 1:
            raise ValueError(f"expected one KML file in {filename}")
        return archive.read(kml[0])


def parse_crosswalk(raw: bytes) -> list[dict[str, str]]:
    """Each Connecticut town's old county and new planning region, from the Census crosswalk.

    The file is pipe-delimited, with a header split across lines and a glossary
    after the rows, so only lines of Connecticut data are read.
    """
    names = ("state", "old", "old_name", "new", "new_name", "town")
    rows = []
    for line in raw.decode("utf-8-sig").splitlines():
        if not line.startswith(f"{CONNECTICUT}|"):
            continue
        fields = line.split("|")
        if len(fields) != 13:
            raise ValueError(f"unexpected crosswalk line: {line!r}")
        rows.append(dict(zip(names, fields[: len(names)], strict=True)))
    if not rows:
        raise ValueError("no Connecticut rows in the crosswalk")
    return rows


def link_legacy_counties(rows: list[dict[str, str]], crosswalk: list[dict[str, str]]) -> None:
    """Fill each planning region's `legacy_counties` from the towns it shares with them.

    Every crosswalk code and name must match its row, every region and legacy
    county must appear, and no legacy county may share a name with a region,
    so a lookup by name can never land on the other kind.
    """
    by_geoid = {row["geoid"]: row for row in rows}
    overlaps: dict[str, set[str]] = {}
    for town in crosswalk:
        old, new = CONNECTICUT + town["old"], CONNECTICUT + town["new"]
        if (
            town["state"] != CONNECTICUT
            or old not in LEGACY_COUNTIES
            or new not in PLANNING_REGIONS
        ):
            raise ValueError(f"unexpected crosswalk codes: {old} to {new}")
        for geoid, name in ((old, town["old_name"]), (new, town["new_name"])):
            if by_geoid[geoid]["qualified_name"] != name:
                raise ValueError(f"the crosswalk names {geoid} {name!r}")
        overlaps.setdefault(new, set()).add(old)
    if set(overlaps) != PLANNING_REGIONS or set().union(*overlaps.values()) != LEGACY_COUNTIES:
        raise ValueError("the crosswalk does not cover every planning region and legacy county")
    regions = {
        name.casefold()
        for geoid in PLANNING_REGIONS
        for name in (by_geoid[geoid]["name"], by_geoid[geoid]["qualified_name"])
    }
    for geoid in sorted(LEGACY_COUNTIES):
        row = by_geoid[geoid]
        if {row["name"].casefold(), row["qualified_name"].casefold()} & regions:
            raise ValueError(f"legacy county {geoid} shares a name with a planning region")
    for region, counties in overlaps.items():
        by_geoid[region]["legacy_counties"] = " ".join(sorted(counties))


def render(source_dir: Path) -> tuple[str, dict]:
    rows = []
    sources = []
    clips: list[dict] = []
    for kind, filename in FILES.items():
        raw = (source_dir / filename).read_bytes()
        parsed = parse_kml(read_kml(raw, filename), kind, clips)
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
    current = {row["geoid"] for row in rows if row["geoid"].startswith(CONNECTICUT)}
    if current != PLANNING_REGIONS | {CONNECTICUT}:
        raise ValueError(f"the {VINTAGE} vintage does not hold Connecticut's planning regions")
    legacy_raw = (source_dir / LEGACY_FILE).read_bytes()
    legacy = parse_kml(read_kml(legacy_raw, LEGACY_FILE), "legacy_county", state=CONNECTICUT)
    if {row["geoid"] for row in legacy} != LEGACY_COUNTIES:
        raise ValueError(f"unexpected Connecticut counties in {LEGACY_FILE}")
    rows.extend(legacy)
    crosswalk_raw = (source_dir / CROSSWALK_FILE).read_bytes()
    crosswalk = parse_crosswalk(crosswalk_raw)
    link_legacy_counties(rows, crosswalk)
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
        "connecticut_legacy_counties": {
            "rule": (
                "Connecticut's eight counties before 2022 are kept as legacy_county rows "
                "beside the planning regions that replaced them, for sources still keyed "
                "by the old codes. A planning region's legacy_counties lists the old "
                "counties it shares a town with."
            ),
            "vintage": LEGACY_VINTAGE,
            "sources": [
                {
                    "url": LEGACY_URL,
                    "sha256": hashlib.sha256(legacy_raw).hexdigest(),
                    "records": len(legacy),
                },
                {
                    "url": CROSSWALK_URL,
                    "sha256": hashlib.sha256(crosswalk_raw).hexdigest(),
                    "records": len(crosswalk),
                },
            ],
        },
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
        "--source-dir", type=Path, help="directory containing the downloaded Census inputs"
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
                for filename, url in DOWNLOADS.items():
                    http.download(url, source_dir / filename, client)
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
    print(
        "2025 Census places: 56 states/territories and 3235 counties/equivalents, "
        f"plus Connecticut's 8 counties from {LEGACY_VINTAGE}"
    )


if __name__ == "__main__":
    main()
