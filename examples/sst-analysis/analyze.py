"""Fetch four ocean grid cells, open their CSV, and summarize SST in source units."""

from usdata import build_query, get
from usdata.fetch import fetch


def main() -> None:
    """Print a mean over four nearby grid centers at one analysis timestamp."""
    (item,) = fetch(
        get("noaa:coastwatch-sst"),
        build_query(
            bbox=(-80.08, 30.02, -80.02, 30.08),
            start="2024-05-06T12:00Z",
            end="2024-05-06T12:00Z",
        ),
    )
    frame = item.open(parse_dates=["time"])
    units = frame.attrs["units"]["analysed_sst"]
    print(f"{len(frame)} cells; mean SST: {frame['analysed_sst'].mean():.2f} {units}")
    print(f"Source checksum: {item.provenance.checksum}")


if __name__ == "__main__":
    main()
