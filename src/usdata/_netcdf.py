"""Local, eagerly loaded NetCDF4 reading behind the netcdf extra."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from usdata.readers import MissingReaderDependency

if TYPE_CHECKING:
    from usdata.fetch import FetchedAsset


def open_netcdf(fetched: FetchedAsset) -> Any:
    """Load a NetCDF4 root Dataset, then close every source file handle."""
    try:
        xarray = import_module("xarray")
        import_module("h5netcdf")
        import_module("h5py")
    except ModuleNotFoundError as error:
        if error.name not in {"xarray", "h5netcdf", "h5py"}:
            raise
        raise MissingReaderDependency(
            'NetCDF4 reading requires xarray and h5netcdf; install: pip install "usdata[netcdf]"'
        ) from error
    # A local file object and fixed engine prevent interpretation as an OPeNDAP URL.
    with (
        fetched.path.open("rb") as stream,
        xarray.open_dataset(stream, engine="h5netcdf", chunks=None) as dataset,
    ):
        dataset.load()
    dataset.attrs["usdata"] = {
        "asset_id": fetched.asset.id,
        "provenance": fetched.provenance.model_dump(mode="json"),
    }
    return dataset
