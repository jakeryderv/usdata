"""Lock one month of airport climate observations and print its summary."""

from pathlib import Path

from usdata.pull import pull


def main() -> None:
    """Open the monthly CSV locally, preserving station strings and provenance."""
    manifest = Path(__file__).with_name("dataset.yaml")
    (item,) = pull(manifest).fetched
    frame = item.open()
    for _, row in frame.iterrows():
        print(
            f"{row['STATION']} {row['DATE']}: "
            f"precipitation {row['PRCP']:.1f} mm; mean temperature {row['TAVG']:.1f} °C"
        )
    print(f"Source checksum: {item.provenance.checksum}")


if __name__ == "__main__":
    main()
