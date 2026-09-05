"""Regenerate src/usdata/data/nexrad_sites.csv from the NCEI HOMR station list.

Usage: uv run python scripts/build_nexrad_sites.py [path-to-nexrad-stations.txt]
Without a path the file is downloaded from NCEI.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import httpx

SOURCE = "https://www.ncei.noaa.gov/access/homr/file/nexrad-stations.txt"
OUT = Path(__file__).resolve().parents[1] / "src/usdata/data/nexrad_sites.csv"
COLUMNS = ["ICAO", "NAME", "ST", "LAT", "LON", "ELEV", "STNTYPE"]
# Test and research radars listed by HOMR as NEXRAD but absent from the Level II archive.
NON_OPERATIONAL = {"KCRI", "KOUN"}


def spans(dash_line: str) -> list[tuple[int, int]]:
    out, start = [], None
    for i, ch in enumerate(dash_line + " "):
        if ch == "-" and start is None:
            start = i
        elif ch != "-" and start is not None:
            out.append((start, i))
            start = None
    return out


def main() -> None:
    text = (
        Path(sys.argv[1]).read_text()
        if len(sys.argv) > 1
        else httpx.get(SOURCE, timeout=60).raise_for_status().text
    )
    header, dashes, *rows = text.splitlines()
    cols = spans(dashes)
    names = [header[a:b].strip() for a, b in cols]
    idx = {n: cols[i] for i, n in enumerate(names)}
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "state", "lat", "lon", "elev_ft", "type"])
        n = 0
        for row in rows:
            if not row.strip():
                continue
            rec = {c: row[idx[c][0] : idx[c][1]].strip() for c in COLUMNS}
            if rec["ICAO"] in NON_OPERATIONAL:
                rec["STNTYPE"] = "TEST"
            w.writerow(
                [
                    rec["ICAO"],
                    rec["NAME"].title(),
                    rec["ST"],
                    rec["LAT"],
                    rec["LON"],
                    rec["ELEV"],
                    rec["STNTYPE"],
                ]
            )
            n += 1
    print(f"wrote {n} sites to {OUT}")


if __name__ == "__main__":
    main()
