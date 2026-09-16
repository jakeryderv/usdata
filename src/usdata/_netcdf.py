"""Local, eagerly loaded NetCDF4 reading behind the netcdf extra."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

from usdata.inspect import NetcdfVariable
from usdata.readers import MissingReaderDependency, fill_registry_attrs

if TYPE_CHECKING:
    from usdata._fetch import FetchedAsset

PIP_HINT = 'NetCDF4 reading requires xarray and h5netcdf; install: pip install "usdata[netcdf]"'


def _xarray() -> Any:
    """The xarray module once h5netcdf can back it, or a hint naming the extra."""
    try:
        xarray = import_module("xarray")
        import_module("h5netcdf")
        import_module("h5py")
    except ModuleNotFoundError as error:
        if error.name not in {"xarray", "h5netcdf", "h5py"}:
            raise
        raise MissingReaderDependency(PIP_HINT) from error
    return xarray


def _text(value: Any) -> str | None:
    """One attribute as a single string, or None where the file states nothing."""
    return None if value is None else str(value)


def open_netcdf(fetched: FetchedAsset) -> Any:
    """Load a NetCDF4 root Dataset, then close every source file handle."""
    xarray = _xarray()
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
    fill_registry_attrs(fetched, dataset)
    return dataset


def variables(path: Path) -> list[NetcdfVariable]:
    """Describe a local NetCDF4 file's data variables without loading their values."""
    xarray = _xarray()
    with (
        path.open("rb") as stream,
        xarray.open_dataset(stream, engine="h5netcdf", chunks=None) as dataset,
    ):
        return [
            NetcdfVariable(
                name=str(name),
                dims=[str(dim) for dim in array.dims],
                shape=[int(size) for size in array.shape],
                units=_text(array.attrs.get("units")),
                long_name=_text(array.attrs.get("long_name")),
            )
            for name, array in dataset.data_vars.items()
        ]
