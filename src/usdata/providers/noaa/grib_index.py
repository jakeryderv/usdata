"""The wgrib2 index sidecar NCEP publishes beside each GRIB2 object, and message selection.

Every HRRR and GFS object has a ``<key>.idx`` companion: one colon-delimited
line per GRIB2 message, in message order, with no length field::

    71:43023331:d=2026091412:TMP:2 m above ground:1 hour fcst:
    72:44188209:d=2026091412:POT:2 m above ground:1 hour fcst:

The fields are the message number, its byte offset in the object, the run's
initialization stamp, the wgrib2 short name, the level text, and the step text.
A message's length is the next message's offset minus its own, and the last
message runs to the end of the object, so parsing needs the object's size.

Selection speaks the index's own vocabulary, not the ecCodes names the reader's
``select`` uses: ``TMP:2 m above ground``, optionally with a step text. Nothing
here performs I/O, so the caller fetches the index text and the object size and
this module turns them into byte ranges. See ADR 0028.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from difflib import get_close_matches

from pydantic import BaseModel

from usdata.models import ByteRange
from usdata.providers.base import QueryError

INDEX_SUFFIX = ".idx"
FIELDS = 6
"""Fields a line must have before the optional trailing ones some products add."""


class IndexEntry(BaseModel):
    """One message of one object, as its index line describes it."""

    number: int
    offset: int
    length: int
    short_name: str
    level: str
    step: str

    @property
    def byte_range(self) -> ByteRange:
        """The inclusive byte interval this message occupies in the object."""
        return ByteRange(start=self.offset, end=self.offset + self.length - 1)

    @property
    def label(self) -> str:
        """The selector that names exactly this message, short name through step text."""
        return f"{self.short_name}:{self.level}:{self.step}"


class Selection(BaseModel):
    """One selected message and the index selector text that names exactly it."""

    entry: IndexEntry
    selector: str


class Selector(BaseModel):
    """One ``VAR:level text`` request, optionally narrowed by a step text."""

    short_name: str
    level: str
    step: str | None = None

    @property
    def text(self) -> str:
        """The selector as it was written, for an error message to quote."""
        return ":".join(part for part in (self.short_name, self.level, self.step) if part)

    def matches(self, entry: IndexEntry) -> bool:
        """Whether one index entry is exactly what this selector names."""
        return (
            entry.short_name == self.short_name
            and entry.level == self.level
            and (self.step is None or entry.step == self.step)
        )


def parse_selector(raw: str) -> Selector:
    """Read one ``VAR:level text`` selector, with an optional ``:step text``.

    Args:
        raw: The selector as the caller wrote it, such as ``TMP:2 m above ground``.

    Returns:
        The parsed selector.

    Raises:
        QueryError: The selector has the wrong number of fields or an empty one.
    """
    parts = [part.strip() for part in raw.split(":")]
    if len(parts) not in (2, 3) or not all(parts):
        raise QueryError(
            f"messages selector {raw!r} must be 'VAR:level text', with an optional "
            "':step text', such as 'TMP:2 m above ground'"
        )
    return Selector(short_name=parts[0], level=parts[1], step=parts[2] if len(parts) == 3 else None)


def parse_index(text: str, *, object_size: int, url: str) -> list[IndexEntry]:
    """Read a wgrib2 index into one entry per message, with lengths from the next offset.

    Args:
        text: The index sidecar exactly as it was fetched.
        object_size: Size of the object the index describes; the last message runs to it.
        url: The object the index belongs to, named in any error.

    Returns:
        Every message in index order.

    Raises:
        QueryError: The text is empty, a line is malformed, or offsets do not ascend
            inside the object.
    """
    rows: list[tuple[int, int, str, str, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split(":")
        if len(fields) < FIELDS:
            raise QueryError(f"{url}{INDEX_SUFFIX} line {number} is not a wgrib2 index line")
        try:
            rows.append((int(fields[0]), int(fields[1]), fields[3], fields[4], fields[5]))
        except ValueError:
            raise QueryError(
                f"{url}{INDEX_SUFFIX} line {number} has no message number and offset"
            ) from None
    if not rows:
        raise QueryError(f"{url}{INDEX_SUFFIX} lists no GRIB2 messages")
    entries: list[IndexEntry] = []
    for position, (message, offset, short_name, level, step) in enumerate(rows):
        end = rows[position + 1][1] if position + 1 < len(rows) else object_size
        if offset < 0 or end <= offset or end > object_size:
            raise QueryError(
                f"{url}{INDEX_SUFFIX} message {message} spans {offset} to {end}, "
                f"which is not inside the {object_size} byte object"
            )
        entries.append(
            IndexEntry(
                number=message,
                offset=offset,
                length=end - offset,
                short_name=short_name,
                level=level,
                step=step,
            )
        )
    return entries


def _hint(entries: Sequence[IndexEntry], selector: Selector) -> str:
    """What to try instead: this short name's levels, or the nearest short names."""
    levels = list(dict.fromkeys(e.level for e in entries if e.short_name == selector.short_name))
    if levels:
        return f"levels published for {selector.short_name}: {', '.join(levels)}"
    names = list(dict.fromkeys(e.short_name for e in entries))
    nearest = get_close_matches(selector.short_name, names, n=5, cutoff=0.4) or names[:5]
    return f"nearest short names: {', '.join(nearest)}"


def resolve(
    entries: Sequence[IndexEntry], selectors: Iterable[Selector], *, url: str
) -> list[Selection]:
    """The messages the selectors name, ascending by message number and each listed once.

    Each selection also carries the text that names its one message: the
    selector as the caller wrote it when that selector matched nothing else, and
    the index line's own short name, level, and step text when the caller wrote
    a broader one that several messages answered.

    Args:
        entries: Every message of the object, as ``parse_index`` read them.
        selectors: What the caller asked for, in request order.
        url: The object, named in any error.

    Returns:
        The selected messages, ascending by message number.

    Raises:
        QueryError: A selector matches no message, which is never a whole-file fetch.
    """
    chosen: dict[int, Selection] = {}
    for selector in selectors:
        hits = [entry for entry in entries if selector.matches(entry)]
        if not hits:
            raise QueryError(
                f"messages selector {selector.text!r} matched no message in "
                f"{url}{INDEX_SUFFIX}; {_hint(entries, selector)}"
            )
        text = selector.text if len(hits) == 1 else None
        chosen.update(
            {entry.number: Selection(entry=entry, selector=text or entry.label) for entry in hits}
        )
    return [chosen[number] for number in sorted(chosen)]


__all__ = [
    "INDEX_SUFFIX",
    "IndexEntry",
    "Selection",
    "Selector",
    "parse_index",
    "parse_selector",
    "resolve",
]
