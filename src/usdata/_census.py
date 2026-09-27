"""Local reading of Census Data API tables into a pandas DataFrame, behind pandas.

A fetched ``census:acs-5year`` file is the service's response as served: a JSON
array whose first row names the columns and whose other rows are one geography
each, every value a string. The table is those rows under those names, with the
estimate and margin-of-error columns as numbers and everything else, geography
codes and their leading zeros included, as text.

Negative annotation codes such as ``-555555555`` stay the numbers they are.
Each means something different (too few sample cases, not applicable, a
controlled estimate), so they are not turned into missing values (ADR 0045).
"""

from __future__ import annotations

import json
import re
from importlib import import_module
from typing import TYPE_CHECKING, Any

from usdata.readers import MissingReaderDependency, source_attrs

if TYPE_CHECKING:
    from usdata._fetch import FetchedAsset

NUMERIC = re.compile(r"[A-Z]\d{5}[A-Z0-9]*_\d{3}[EM]")
"""An estimate (``...E``) or margin of error (``...M``) variable, such as ``B01003_001E``.

Annotation columns (``...EA``, ``...MA``) and ``NAME`` do not match and stay text.
"""


def open_acs(fetched: FetchedAsset) -> Any:
    """Parse a fetched ACS table into a pandas DataFrame, one row per geography."""
    try:
        pandas = import_module("pandas")
    except ModuleNotFoundError as error:
        if error.name != "pandas":
            raise
        raise MissingReaderDependency(
            'ACS reading requires pandas; install it with: pip install "usdata[pandas]" '
            '(or uv add "usdata[pandas]")'
        ) from error
    # Reading a fetched asset is strictly local; the cached file is never rewritten.
    header, *rows = json.loads(fetched.path.read_text(encoding="utf-8"))
    frame = pandas.DataFrame(rows, columns=header, dtype="string")
    for column in header:
        if NUMERIC.fullmatch(column):
            frame[column] = pandas.to_numeric(frame[column])
    frame.attrs["usdata"] = source_attrs(fetched)
    return frame
