"""Local, eagerly loaded NetCDF reading behind the netcdf extra.

NetCDF4 files are HDF5 and open through h5netcdf. NetCDF3 classic and 64-bit
offset files, which HDF5 cannot read, open through scipy; the file's first four
bytes decide which, so neither the name nor the media type has to say.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from usdata.inspect import NetcdfVariable
from usdata.readers import MissingReaderDependency, fill_registry_attrs, source_attrs

if TYPE_CHECKING:
    from usdata._fetch import FetchedAsset

PIP_HINT = (
    "NetCDF reading requires xarray, with h5netcdf for NetCDF4 and scipy for NetCDF3; "
    'install: pip install "usdata[netcdf]"'
)
CLASSIC = (b"CDF\x01", b"CDF\x02")
"""The magic numbers of NetCDF3 classic and 64-bit offset files."""
BACKENDS = {"h5netcdf": ("h5netcdf", "h5py"), "scipy": ("scipy",)}
"""The modules each xarray engine needs beyond xarray itself."""


def _engine(stream: BinaryIO) -> str:
    """The xarray engine that reads this file: scipy for NetCDF3, h5netcdf otherwise."""
    head = stream.read(4)
    stream.seek(0)
    return "scipy" if head in CLASSIC else "h5netcdf"


def _xarray(engine: str) -> Any:
    """The xarray module once ``engine`` can back it, or a hint naming the extra."""
    names = {"xarray", *BACKENDS[engine]}
    try:
        xarray = import_module("xarray")
        for name in BACKENDS[engine]:
            import_module(name)
    except ModuleNotFoundError as error:
        if error.name not in names:
            raise
        raise MissingReaderDependency(PIP_HINT) from error
    return xarray


def _text(value: Any) -> str | None:
    """One attribute as a single string, or None where the file states nothing."""
    return None if value is None else str(value)


def open_netcdf(fetched: FetchedAsset) -> Any:
    """Load a NetCDF root Dataset, then close every source file handle."""
    # A local file object and fixed engine prevent interpretation as an OPeNDAP URL.
    with fetched.path.open("rb") as stream:
        engine = _engine(stream)
        with _xarray(engine).open_dataset(stream, engine=engine, chunks=None) as dataset:
            dataset.load()
    dataset.attrs["usdata"] = source_attrs(fetched)
    fill_registry_attrs(fetched, dataset)
    return dataset


def variables(path: Path) -> list[NetcdfVariable]:
    """Describe a local NetCDF file's data variables without loading their values."""
    with path.open("rb") as stream:
        engine = _engine(stream)
        with _xarray(engine).open_dataset(stream, engine=engine, chunks=None) as dataset:
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
