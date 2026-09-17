"""The wgrib2 index sidecar NCEP publishes beside each GRIB2 object, and message selection.

Every HRRR, GFS, RAP, and NBM object has a ``<key>.idx`` companion: one
colon-delimited line per GRIB2 field, in message order, with no length field::

    71:43023331:d=2026091412:TMP:2 m above ground:1 hour fcst:
    72:44188209:d=2026091412:POT:2 m above ground:1 hour fcst:

The fields are the message number, its byte offset in the object, the run's
initialization stamp, the wgrib2 short name, the level text, the step text,
and, in some products, a further text such as ``ens std dev`` or a probability
threshold. A message's length is the next message's offset minus its own, and
the last message runs to the end of the object, so parsing needs the object's
size. Two dialects widen that picture: RAP numbers the fields of one GRIB2
message holding several as ``12.1`` and ``12.2`` at one offset, so they are one
byte range; and NBM's fourth text distinguishes a value from its ensemble
spread, so a selector without it names the plain field alone.

Selection speaks the index's own vocabulary, not the ecCodes names the reader's
``select`` uses: ``TMP:2 m above ground``, optionally with a step text and then
the further text. Nothing here performs I/O, so the caller fetches the index
text and the object size and this module turns them into byte ranges. See
ADR 0028.
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
    """One field of one object, as its index line describes it.

    ``number`` is the GRIB2 message the field belongs to and ``field`` its
    position inside a message that holds several (``12.2``), or ``None`` for a
    message holding one. Fields of one message share an offset and a length.
    """

    number: int
    offset: int
    length: int
    short_name: str
    level: str
    step: str
    field: int | None = None
    extra: str = ""

    @property
    def byte_range(self) -> ByteRange:
        """The inclusive byte interval this field's message occupies in the object."""
        return ByteRange(start=self.offset, end=self.offset + self.length - 1)

    @property
    def label(self) -> str:
        """The selector that names exactly this field, short name through the last text."""
        parts = [self.short_name, self.level, self.step]
        if self.extra:
            parts.append(self.extra)
        return ":".join(parts)


class Selection(BaseModel):
    """One selected message and the index selector text that names exactly it."""

    entry: IndexEntry
    selector: str


class Selector(BaseModel):
    """One ``VAR:level text`` request, optionally narrowed by a step text and a further text.

    Without the further text the selector names the plain field: an index line
    whose extra text is empty. Naming the text selects that variant instead,
    such as ``TMP:2 m above ground:1 hour fcst:ens std dev``.
    """

    short_name: str
    level: str
    step: str | None = None
    extra: str | None = None

    @property
    def text(self) -> str:
        """The selector as it was written, for an error message to quote."""
        parts = (self.short_name, self.level, self.step, self.extra)
        return ":".join(part for part in parts if part)

    def matches(self, entry: IndexEntry) -> bool:
        """Whether one index entry is exactly what this selector names."""
        return (
            entry.short_name == self.short_name
            and entry.level == self.level
            and (self.step is None or entry.step == self.step)
            and entry.extra == (self.extra or "")
        )


def parse_selector(raw: str) -> Selector:
    """Read one ``VAR:level text`` selector, with an optional ``:step text[:further text]``.

    Args:
        raw: The selector as the caller wrote it, such as ``TMP:2 m above ground``.

    Returns:
        The parsed selector.

    Raises:
        QueryError: The selector has the wrong number of fields or an empty one.
    """
    parts = [part.strip() for part in raw.split(":")]
    if len(parts) not in (2, 3, 4) or not all(parts):
        raise QueryError(
            f"messages selector {raw!r} must be 'VAR:level text', with an optional "
            "':step text' and then an optional further text, such as 'TMP:2 m above ground'"
        )
    return Selector(
        short_name=parts[0],
        level=parts[1],
        step=parts[2] if len(parts) > 2 else None,
        extra=parts[3] if len(parts) > 3 else None,
    )


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
    rows: list[tuple[int, int | None, int, str, str, str, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split(":")
        if len(fields) < FIELDS:
            raise QueryError(f"{url}{INDEX_SUFFIX} line {number} is not a wgrib2 index line")
        message, _, field = fields[0].partition(".")
        try:
            rows.append(
                (
                    int(message),
                    int(field) if field else None,
                    int(fields[1]),
                    fields[3],
                    fields[4],
                    fields[5],
                    ":".join(fields[6:]).strip(":"),
                )
            )
        except ValueError:
            raise QueryError(
                f"{url}{INDEX_SUFFIX} line {number} has no message number and offset"
            ) from None
    if not rows:
        raise QueryError(f"{url}{INDEX_SUFFIX} lists no GRIB2 messages")
    entries: list[IndexEntry] = []
    for position, (message, field, offset, short_name, level, step, extra) in enumerate(rows):
        # Fields of one message share its offset, so a message ends at the next distinct one.
        end = next((row[2] for row in rows[position + 1 :] if row[2] != offset), object_size)
        if position and rows[position - 1][2] == offset and rows[position - 1][0] != message:
            raise QueryError(
                f"{url}{INDEX_SUFFIX} messages {rows[position - 1][0]} and {message} share "
                f"offset {offset}, which only fields of one message may"
            )
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
                field=field,
                extra=extra,
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
    a broader one that several messages answered. A message holding several
    fields is one selection however many of its fields were named, carrying the
    first; its other fields travel with it, since a byte range cannot split them.

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
        for entry in hits:
            chosen.setdefault(entry.number, Selection(entry=entry, selector=text or entry.label))
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
