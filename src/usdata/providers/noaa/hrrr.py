"""HRRR forecast output from the anonymous ``noaa-hrrr-bdp-pds`` S3 bucket.

One model run is identified by its UTC initialization day and ``cycle`` hour;
each run writes one GRIB2 file per forecast hour under
``hrrr.YYYYMMDD/conus/hrrr.tHHz.<variant>fNN.grib2``. The query window selects
runs by initialization time, ``cycle`` names the run's hour, ``forecast_hour``
names the files, and ``file`` chooses the surface, pressure-level, or native
variant. Files are whole CONUS grids of hundreds of fields; the server subsets
none of them, so message selection happens either after download with the GRIB2
reader's ``select``, or before it with ``messages``.

``messages`` names fields the way the object's ``.idx`` sidecar names them, and
the adapter turns them into byte ranges at listing time; the resulting asset is
the concatenation of those messages, which is itself a valid GRIB2 file. See
ADR 0028.

The run-selection helpers (:func:`select_runs`, :func:`list_run_files`) and the
:class:`ModelRuns` listing base are shared with the GFS adapter.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, ClassVar, NamedTuple

import httpx
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from usdata.cache import sha256_bytes
from usdata.models import (
    PARTIAL_FRAGMENT,
    Asset,
    Dataset,
    PartialFetch,
    Protocol,
    Provenance,
    Query,
    TimeRange,
)
from usdata.protocols import http, s3
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.noaa import grib_index
from usdata.providers.params import StrList, choice, int_list, int_range

BUCKET = "noaa-hrrr-bdp-pds"
DOMAIN = "conus"
MEDIA_TYPE = "application/x-grib2"
ARCHIVE_START = datetime(2014, 7, 30, 18, tzinfo=UTC)
MAX_WINDOW = timedelta(days=1)
FILES: Mapping[str, str] = {"sfc": "wrfsfcf", "prs": "wrfprsf", "nat": "wrfnatf"}
LONG_CYCLES = frozenset({0, 6, 12, 18})
MAX_HOUR = 18
LONG_MAX_HOUR = 48
KEY_RE = re.compile(r"hrrr\.t(?P<cycle>\d{2})z\.(?P<variant>wrf[a-z]+f)(?P<hour>\d{2,3})\.grib2")
ABSENT_INDEX = {403, 404}
MESSAGES = (
    "Optional GRIB2 messages to fetch instead of the whole file, spelled as the object's "
    "wgrib2 .idx sidecar spells them: 'SHORTNAME:level text', such as "
    "'TMP:2 m above ground', with an optional ':step text'; one value, a list, or a "
    "comma-separated string. Short names are upper case and both fields match exactly."
)


def checked_selectors(value: list[str]) -> list[str]:
    """Reject a misspelled ``messages`` entry while the parameters are validated.

    Shape is checked here so a typo fails before any request; whether the index
    holds a matching message can only be answered once it has been read.
    """
    for raw in value:
        grib_index.parse_selector(raw)
    return value


MessageList = Annotated[StrList, AfterValidator(checked_selectors)]
"""``messages`` as a list of well-formed selectors, in request order."""


class HrrrParams(BaseModel):
    """Which run, which forecast hours, and which file variant one HRRR query names."""

    model_config = ConfigDict(extra="forbid")

    cycle: Annotated[int, int_range(0, 23)] = Field(
        description="Required UTC initialization hour of the run, 0 to 23."
    )
    forecast_hour: Annotated[list[int], int_list(0, LONG_MAX_HOUR)] = Field(
        description="Required forecast hour(s): an integer, list, or comma-separated "
        "string; 0 to 18, or 0 to 48 for the 00, 06, 12, and 18 UTC runs."
    )
    file: Annotated[str, choice(*FILES)] = Field(
        default="sfc",
        description="File variant: sfc (default, 2-D fields), prs (pressure levels), or nat "
        "(native levels).",
    )

    messages: MessageList | None = Field(default=None, description=MESSAGES)

    @field_validator("file", mode="before")
    @classmethod
    def _reject_subhourly(cls, value: object) -> object:
        """Name the one variant this adapter leaves out, rather than listing it as a typo."""
        if value == "subh":
            raise ValueError("file=subh (15-minute output) is out of scope; use sfc, prs, or nat")
        return value

    @model_validator(mode="after")
    def _hours_fit_the_cycle(self) -> HrrrParams:
        """Only the 00, 06, 12, and 18 UTC runs reach 48 hours; the others stop at 18."""
        ceiling = LONG_MAX_HOUR if self.cycle in LONG_CYCLES else MAX_HOUR
        if any(hour > ceiling for hour in self.forecast_hour):
            raise ValueError(f"forecast_hour must be an integer from 0 to {ceiling}")
        return self

    @property
    def variant(self) -> str:
        """The key fragment naming the chosen file variant, for example ``wrfsfcf``."""
        return FILES[self.file]


def select_runs(start: datetime, end: datetime, cycle: int) -> list[datetime]:
    """Initialization times at ``cycle`` inside the inclusive UTC window, in order."""
    candidates = {
        datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=cycle)
        for day in (start.date(), end.date())
    }
    return sorted(init for init in candidates if start <= init <= end)


def list_run_files(
    client: httpx.Client,
    bucket: str,
    prefix: str,
    key_re: re.Pattern[str],
    hours: list[int],
) -> dict[int, s3.S3Object]:
    """Objects under ``prefix`` whose parsed forecast hour is requested, keyed by hour."""
    found: dict[int, s3.S3Object] = {}
    wanted = set(hours)
    for obj in s3.list_objects(bucket, prefix, client):
        match = key_re.fullmatch(obj.key.rsplit("/", 1)[-1])
        if match is None:
            continue
        hour = int(match["hour"])
        if hour in wanted:
            found[hour] = obj
    return found


class RunSelection(NamedTuple):
    """What one query names: the run, its file variant, its hours, and any message selectors."""

    cycle: int
    variant: str
    hours: list[int]
    messages: list[str]


def message_digest(messages: Sequence[int]) -> str:
    """Twelve hex characters standing for one message list, so a partial asset id is stable."""
    numbers = ",".join(str(number) for number in messages)
    return hashlib.sha256(numbers.encode()).hexdigest()[:12]


def pinned_partial(pinned: Provenance) -> PartialFetch:
    """Rebuild the byte ranges a provenance record pins, without reading any index.

    Args:
        pinned: The record a lockfile holds for a partial asset.

    Returns:
        The same selection the original fetch resolved.

    Raises:
        QueryError: The record is missing part of what a range request needs.
    """
    object_url, _, fragment = pinned.source_url.partition("#")
    numbers = fragment.removeprefix(f"{PARTIAL_FRAGMENT}=").split(",")
    try:
        return PartialFetch(
            object_url=object_url,
            object_size=pinned.object_size or 0,
            object_etag=pinned.object_etag or "",
            index_url=pinned.index_url or "",
            index_checksum=pinned.index_checksum or "",
            messages=[int(number) for number in numbers],
            ranges=list(pinned.ranges),
            selectors=list(pinned.selectors),
        )
    except (ValidationError, ValueError) as error:
        raise QueryError(
            f"the pinned record for {pinned.source_url} does not describe byte ranges "
            f"that can be re-fetched ({error}); pull with force to resolve it again"
        ) from None


class ModelRuns(HttpProvider):
    """Shared listing for models that publish one whole GRIB2 file per run and forecast hour.

    Subclasses validate their own parameters in :meth:`resolve` and describe the
    bucket layout through :meth:`run_prefix`, :meth:`asset_id`, :meth:`files_label`,
    and the ``suffix`` their ids end with; the window, run selection, listing,
    missing-file errors, and message selection are identical for HRRR and GFS.

    With ``messages``, listing reads each object's ``.idx`` sidecar and resolves
    the selectors to byte ranges, which :meth:`fetch` then concatenates. Those
    ranges live on the adapter instance, keyed by the asset href that names them;
    a later process reaches them through the provenance sidecar instead, so see
    :meth:`prepare_fetch`.
    """

    name: ClassVar[str]
    bucket: ClassVar[str]
    archive_start: ClassVar[datetime]
    key_re: ClassVar[re.Pattern[str]]
    hint: ClassVar[str]
    hour_width: ClassVar[int] = 2
    suffix: ClassVar[str] = ""

    def __init__(self, dataset: Dataset, client: httpx.Client | None = None) -> None:
        super().__init__(dataset, client)
        self._partials: dict[str, PartialFetch] = {}

    def resolve(self, query: Query) -> RunSelection:
        """Validated run, variant, forecast hours, and message selectors for one query."""
        raise NotImplementedError

    def run_prefix(self, init: datetime, variant: str) -> str:
        """The S3 key prefix that lists one run's files of ``variant``."""
        raise NotImplementedError

    def asset_id(self, init: datetime, variant: str, hour: int) -> str:
        """A stable, day-qualified id for one file, used as the cache filename."""
        raise NotImplementedError

    def files_label(self, variant: str) -> str:
        """How a missing run's files are named in errors, for example ``HRRR conus wrfsfcf``."""
        raise NotImplementedError

    def list_assets(self, query: Query) -> list[Asset]:
        """One asset per requested forecast hour of each run initialized inside the window."""
        self.reject(query, "bbox", "text", "variables", hint=self.hint)
        start, end = self.utc_window(query)
        if end - start > MAX_WINDOW:
            raise QueryError(
                f"{self.name} requests must span at most 1 day; split longer intervals"
            )
        cycle, variant, hours, messages = self.resolve(query)
        if end < self.archive_start:
            raise QueryError(
                f"the {self.bucket} archive begins with the {self.archive_start:%Y-%m-%d %HZ} run"
            )
        runs = select_runs(start, end, cycle)
        if not runs:
            raise QueryError(
                f"no {cycle:02d}Z initialization falls inside {start.isoformat()} to "
                f"{end.isoformat()}; widen the window or change cycle"
            )
        assets: list[Asset] = []
        for init in runs:
            prefix = self.run_prefix(init, variant)
            found = list_run_files(self._http(), self.bucket, prefix, self.key_re, hours)
            if not found:
                raise QueryError(
                    f"no {self.files_label(variant)} files for the {init:%Y-%m-%d %H}Z run; "
                    "the run may be missing from the archive or predate this variant"
                )
            if missing := [f"{hour:0{self.hour_width}d}" for hour in hours if hour not in found]:
                raise QueryError(
                    f"the {init:%Y-%m-%d %H}Z run has no forecast hour(s) {', '.join(missing)}"
                )
            for hour in hours:
                obj = found[hour]
                valid = init + timedelta(hours=hour)
                whole = Asset(
                    id=self.asset_id(init, variant, hour),
                    dataset_id=self.dataset.id,
                    href=f"s3://{self.bucket}/{obj.key}",
                    protocol=Protocol.S3,
                    media_type=MEDIA_TYPE,
                    size=obj.size,
                    time=TimeRange(start=valid, end=valid),
                )
                assets.append(self.select_messages(whole, messages) if messages else whole)
        return assets

    def partial_id(self, asset_id: str, digest: str) -> str:
        """The whole file's id with ``.part-<digest>`` before the suffix, or at its end."""
        tag = f".part-{digest}"
        if self.suffix and asset_id.endswith(self.suffix):
            return f"{asset_id[: -len(self.suffix)]}{tag}{self.suffix}"
        return f"{asset_id}{tag}"

    def index_text(self, index_url: str) -> tuple[str, str]:
        """The index sidecar's text, and the sha256 of the bytes it arrived as.

        Raises:
            QueryError: The object publishes no index, so there is nothing to
                resolve selectors against and never a whole-file fetch instead.
        """
        try:
            response = http.get(s3.object_url(index_url), self._http())
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in ABSENT_INDEX:
                raise
            raise QueryError(
                f"{index_url} is not published ({error.response.status_code}), so messages "
                "cannot be selected; drop messages to fetch the whole file"
            ) from None
        return response.text, sha256_bytes(response.content)

    def select_messages(self, whole: Asset, selectors: Sequence[str]) -> Asset:
        """Resolve message selectors against one object's index into a partial asset.

        The object's size and ETag are read first, so the ranges and the identity
        they will be checked against describe the same copy of the object.

        Args:
            whole: The whole-file asset listing resolved, whose href names the object.
            selectors: ``messages`` as the caller wrote them.

        Returns:
            An asset whose id carries a digest of the selected message numbers,
            whose href carries the numbers as a fragment, and whose size is their
            total. The selector each message was fetched for travels with the
            ranges, so provenance can name it later.

        Raises:
            QueryError: The index is absent or unreadable, or a selector matches nothing.
        """
        parsed = [grib_index.parse_selector(selector) for selector in selectors]
        index_url = f"{whole.href}{grib_index.INDEX_SUFFIX}"
        obj = s3.head_object(whole.href, self._http())
        text, checksum = self.index_text(index_url)
        entries = grib_index.parse_index(text, object_size=obj.size, url=whole.href)
        chosen = grib_index.resolve(entries, parsed, url=whole.href)
        partial = PartialFetch(
            object_url=whole.href,
            object_size=obj.size,
            object_etag=obj.etag or "",
            index_url=index_url,
            index_checksum=checksum,
            messages=[selection.entry.number for selection in chosen],
            ranges=[selection.entry.byte_range for selection in chosen],
            selectors=[selection.selector for selection in chosen],
        )
        href = f"{whole.href}#{partial.fragment}"
        self._partials[href] = partial
        return whole.model_copy(
            update={
                "id": self.partial_id(whole.id, message_digest(partial.messages)),
                "href": href,
                "size": partial.size,
            }
        )

    def prepare_fetch(self, asset: Asset, pinned: Provenance | None = None) -> PartialFetch | None:
        """The ranges this asset's fetch will concatenate, or ``None`` for a whole object.

        A partial asset this adapter listed is already resolved. One restored from
        a lockfile is rebuilt from its pinned record, ranges and ETag included, so
        no index is read and a republished index cannot move a pin.
        """
        if f"#{PARTIAL_FRAGMENT}=" not in asset.href:
            return None
        known = self._partials.get(asset.href)
        if known is not None:
            return known
        if pinned is None or pinned.source_url != asset.href or not pinned.is_partial:
            raise QueryError(
                f"{asset.id} selects GRIB2 messages, but neither this adapter nor a pinned "
                "provenance record holds their byte ranges; resolve the query again with "
                "fetch or pull --force"
            )
        partial = pinned_partial(pinned)
        self._partials[asset.href] = partial
        return partial

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one whole GRIB2 object, or the messages it selects, to ``dest``."""
        partial = self.prepare_fetch(asset)
        if partial is None:
            return s3.download(asset.href, dest, self._http())
        return http.download_ranges(
            s3.object_url(partial.object_url),
            dest,
            partial.ranges,
            etag=partial.object_etag,
            total=partial.object_size,
            http=self._http(),
        )


class Hrrr(ModelRuns):
    """HRRR CONUS GRIB2 files, whole or by message; params: cycle, forecast_hour, file, messages."""

    name = "HRRR"
    bucket = BUCKET
    archive_start = ARCHIVE_START
    key_re = KEY_RE
    hint = (
        "HRRR files are whole CONUS grids; fetch with messages=..., or download and let "
        "open(select=...) pick fields"
    )
    suffix = ".grib2"
    params_model = HrrrParams

    def resolve(self, query: Query) -> RunSelection:
        """Validated cycle, file variant, forecast hours, and messages for one HRRR query."""
        params = self.parse_params(query, HrrrParams)
        return RunSelection(
            params.cycle, params.variant, params.forecast_hour, params.messages or []
        )

    def run_prefix(self, init: datetime, variant: str) -> str:
        """Key prefix listing one run's files of the chosen variant."""
        return f"hrrr.{init:%Y%m%d}/{DOMAIN}/hrrr.t{init:%H}z.{variant}"

    def asset_id(self, init: datetime, variant: str, hour: int) -> str:
        """Cache filename: the upstream name with the run day inserted."""
        return f"hrrr.{init:%Y%m%d}.t{init:%H}z.{variant}{hour:02d}.grib2"

    def files_label(self, variant: str) -> str:
        """Name for these files in missing-run errors."""
        return f"HRRR {DOMAIN} {variant}"
