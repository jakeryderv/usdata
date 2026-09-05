"""ERDDAP metadata, coordinate axes, and griddap URL construction over HTTP."""

from __future__ import annotations

import csv
import io
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

import httpx

from usdata.protocols import http

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid ERDDAP identifier: {value!r}")
    return value


def _endpoint(base: str, route: str, dataset: str) -> str:
    parts = urlsplit(base)
    if parts.scheme != "https" or not parts.netloc or parts.query or parts.fragment:
        raise ValueError("ERDDAP base must be an HTTPS URL without query or fragment")
    return f"{base.rstrip('/')}/{route}/{_identifier(dataset)}"


@dataclass(frozen=True)
class GridInfo:
    """An ERDDAP info table without dataset-specific interpretation."""

    dimensions: dict[str, int]
    variables: dict[str, tuple[str, ...]]
    attributes: dict[str, dict[str, str]]


def info(base: str, dataset: str, client: httpx.Client) -> GridInfo:
    """Read dimensions, variable layouts, and attributes from an info CSV table."""
    response = http.get(_endpoint(base, "info", dataset) + "/index.csv", client)
    dimensions: dict[str, int] = {}
    variables: dict[str, tuple[str, ...]] = {}
    attributes: dict[str, dict[str, str]] = {}
    try:
        for row in csv.DictReader(io.StringIO(response.text)):
            kind, name, value = row["Row Type"], row["Variable Name"], row["Value"]
            if kind == "dimension":
                match = re.search(r"\bnValues=(\d+)\b", value)
                if match is None or int(match[1]) < 1:
                    raise ValueError("invalid dimension size")
                dimensions[name] = int(match[1])
            elif kind == "variable":
                variables[name] = tuple(v.strip() for v in value.split(","))
            elif kind == "attribute":
                attributes.setdefault(name, {})[row["Attribute Name"]] = value
        if not dimensions or not variables:
            raise ValueError("missing grid dimensions or variables")
    except (KeyError, TypeError, ValueError, csv.Error) as error:
        raise httpx.DecodingError("invalid ERDDAP info table", request=response.request) from error
    return GridInfo(dimensions, variables, attributes)


def axis(base: str, dataset: str, name: str, client: httpx.Client) -> tuple[str, list[str]]:
    """Read one coordinate axis as strings plus its units, without guessing its type."""
    response = http.get(_endpoint(base, "griddap", dataset) + ".csv?" + _identifier(name), client)
    try:
        rows = list(csv.reader(io.StringIO(response.text)))
        if len(rows) < 3 or rows[0] != [name] or any(len(row) != 1 for row in rows):
            raise ValueError("invalid axis CSV")
        return rows[1][0], [row[0] for row in rows[2:]]
    except (ValueError, csv.Error) as error:
        raise httpx.DecodingError(
            "invalid ERDDAP coordinate axis", request=response.request
        ) from error


@dataclass(frozen=True)
class GridSlice:
    """An inclusive coordinate-value slice; stride counts grid indices."""

    start: float | datetime
    stop: float | datetime
    stride: int = 1

    def expression(self) -> str:
        """Render the validated slice in ERDDAP's coordinate-value syntax."""
        if type(self.stride) is not int or self.stride < 1:
            raise ValueError("grid stride must be a positive integer")

        def value(item: float | datetime) -> str:
            if isinstance(item, datetime):
                if item.tzinfo is None:
                    raise ValueError("grid datetimes must have a timezone")
                return item.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if not math.isfinite(item):
                raise ValueError("grid coordinates must be finite")
            return f"{item:.12g}"

        return f"[({value(self.start)}):{self.stride}:({value(self.stop)})]"


def griddap_url(
    base: str, dataset: str, variables: Sequence[str], slices: Sequence[GridSlice]
) -> str:
    """Build a CSV subset URL for variables sharing the specified dimension order."""
    if not variables or not slices:
        raise ValueError("griddap requires variables and dimension slices")
    suffix = "".join(part.expression() for part in slices)
    query = ",".join(_identifier(variable) + suffix for variable in variables)
    return _endpoint(base, "griddap", dataset) + ".csv?" + quote(query, safe=",():-.")
