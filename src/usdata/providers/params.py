"""Coercions shared by the parameter models adapters declare.

``query.params`` is the wire format between the CLI, a manifest, and an adapter,
so values arrive as strings (``--param cycle=12``) as often as they arrive
typed. These validators accept those shapes and reject the ones a lax integer
would otherwise let through, notably booleans, floats, and non-ASCII digits.

Use them as ``Annotated`` metadata on a field of a parameter model::

    cycle: Annotated[int, int_range(0, 23)]
    forecast_hour: Annotated[list[int], int_list(0, 48)]
    file: Annotated[str, choice("sfc", "prs", "nat")]

Every message reads as the tail of a sentence about the field; the formatter in
``usdata.providers.base`` prefixes the field name.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator


def _items(value: object) -> list[object]:
    """One value, a list or tuple, or a comma-separated string, as a list of items."""
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _integer(value: object, low: int, high: int) -> int:
    """One integer inside ``[low, high]``, read from an int or a digit string."""
    message = f"must be an integer from {low} to {high}"
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(message)
    text = str(value).strip()
    digits = text[1:] if text.startswith("-") else text
    if not digits.isascii() or not digits.isdigit() or not low <= int(text) <= high:
        raise ValueError(message)
    return int(text)


def _text(value: object) -> str:
    """One non-empty string, rejecting the numbers and booleans YAML may hand over."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be text: one value, a list, or a comma-separated string")
    return value.strip()


def int_range(low: int, high: int) -> BeforeValidator:
    """Validate an integer field, accepting the digit strings the CLI passes."""
    return BeforeValidator(lambda value: _integer(value, low, high))


def int_list(low: int, high: int) -> BeforeValidator:
    """Validate an integer list field: one value, a list, or a comma-separated string.

    Items keep request order, repeats collapse to the first occurrence, and an
    empty selection is an error rather than a silent match-everything.
    """

    def parse(value: object) -> list[int]:
        items = [_integer(item, low, high) for item in _items(value)]
        if not items:
            raise ValueError("must not be empty")
        return list(dict.fromkeys(items))

    return BeforeValidator(parse)


def choice(*allowed: str) -> BeforeValidator:
    """Validate a field against a fixed set of values, naming them in the error."""
    names = (
        f"{', '.join(allowed[:-1])}, or {allowed[-1]}" if len(allowed) > 2 else " or ".join(allowed)
    )

    def parse(value: object) -> str:
        if not isinstance(value, str) or value not in allowed:
            raise ValueError(f"must be {names}")
        return value

    return BeforeValidator(parse)


def _strings(value: object) -> list[str]:
    """Distinct non-empty strings in request order, split on commas."""
    items = [_text(item) for item in _items(value)]
    if not items:
        raise ValueError("must not be empty")
    return list(dict.fromkeys(items))


def _upper_strings(value: object) -> list[str]:
    """``_strings`` with each item upper-cased before the duplicates collapse."""
    return list(dict.fromkeys(item.upper() for item in _strings(value)))


StrList = Annotated[list[str], BeforeValidator(_strings)]
"""A string list field: one value, a list, or a comma-separated string."""

UpperStrList = Annotated[list[str], BeforeValidator(_upper_strings)]
"""``StrList`` for codes written in upper case, such as radar ids and product codes.

Items are upper-cased before repeats collapse, so ``ktlx,KTLX`` is one site
rather than two spellings of one.
"""

OptionalUpperStrList = Annotated[list[str] | None, BeforeValidator(_upper_strings)]
"""``UpperStrList`` for a key that may be left out, but never given as empty or null.

The coercion runs on whatever the query supplies, so an explicit ``None`` is the
error it has always been; only an absent key reaches the ``None`` default.
"""

__all__ = [
    "OptionalUpperStrList",
    "StrList",
    "UpperStrList",
    "choice",
    "int_list",
    "int_range",
]
