"""Local reading of AQS daily-summary JSON into a tidy table, behind pandas.

A fetched ``epa:aqs-daily`` file is the canonical form the adapter writes: the
service's JSON with the echoed request left out of its header and the rows in a
fixed order (ADR 0039). Each element of ``Data`` is one monitor's summary for one
local calendar day under one pollutant standard, so the table is one row per
element, with the columns as the service names them.
"""

from __future__ import annotations

import json
from importlib import import_module
from typing import TYPE_CHECKING, Any

from usdata.readers import MissingReaderDependency, source_attrs

if TYPE_CHECKING:
    from usdata._fetch import FetchedAsset

DATE_COLUMNS = ("date_local", "date_of_last_change")
"""Calendar dates as the service writes them, ``YYYY-MM-DD``, parsed without a timezone.

``date_local`` is a day in the monitor's local standard time, not a UTC instant,
so it is left naive rather than given a zone it does not have.
"""


def open_aqs(fetched: FetchedAsset) -> Any:
    """Parse a fetched AQS daily-summary file into a pandas DataFrame, one row per summary."""
    try:
        pandas = import_module("pandas")
    except ModuleNotFoundError as error:
        if error.name != "pandas":
            raise
        raise MissingReaderDependency(
            'AQS reading requires pandas; install it with: pip install "usdata[pandas]" '
            '(or uv add "usdata[pandas]")'
        ) from error
    # Reading a fetched asset is strictly local; the cached file is never rewritten.
    body = json.loads(fetched.path.read_text(encoding="utf-8"))
    frame = pandas.DataFrame(body.get("Data") or [])
    for column in DATE_COLUMNS:
        if column in frame:
            frame[column] = pandas.to_datetime(frame[column], format="%Y-%m-%d")
    frame.attrs["usdata"] = {**source_attrs(fetched), "header": body.get("Header", [])}
    return frame
