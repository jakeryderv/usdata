"""Coercions shared by the parameter models adapters declare.

``query.params`` is the wire format between the CLI, a manifest, and an adapter,
so values arrive as strings (``--param cycle=12``) as often as they arrive
typed. These validators accept those shapes and reject the ones a lax integer
would otherwise let through, notably booleans, floats, and non-ASCII digits.

Use them as ``Annotated`` metadata on a field of a parameter model::

    cycle: Annotated[int, int_range(0, 23)]
    min_magnitude: Annotated[float, number_range(-10, 10)]
    nearest: Annotated[int, positive_int()]
    forecast_hour: Annotated[list[int], int_list(0, 48)]
    file: Annotated[str, choice("sfc", "prs", "nat")]

Every message reads as the tail of a sentence about the field; the formatter in
``usdata.providers.base`` prefixes the field name.
"""

from __future__ import annotations

import math
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


def _positive_integer(value: object) -> int:
    """One integer of at least 1, read from an int or a digit string."""
    message = "must be a positive integer"
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(message)
    text = str(value).strip()
    if not text.isascii() or not text.isdigit() or int(text) < 1:
        raise ValueError(message)
    return int(text)


def _text(value: object) -> str:
    """One non-empty string, rejecting the numbers and booleans YAML may hand over."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be text: one value, a list, or a comma-separated string")
    return value.strip()


def _number(value: object, low: float, high: float) -> float:
    """One finite number inside ``[low, high]``, read from an int, float, or numeric string."""
    message = f"must be a number from {low:g} to {high:g}"
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(message)
    try:
        number = float(str(value).strip())
    except ValueError:
        raise ValueError(message) from None
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(message)
    return number


def number_range(low: float, high: float) -> BeforeValidator:
    """Validate a decimal field such as a magnitude or depth, accepting the CLI's strings."""
    return BeforeValidator(lambda value: _number(value, low, high))


def int_range(low: int, high: int) -> BeforeValidator:
    """Validate an integer field, accepting the digit strings the CLI passes."""
    return BeforeValidator(lambda value: _integer(value, low, high))


def positive_int() -> BeforeValidator:
    """Validate a count field: an integer of at least 1, with no upper bound."""
    return BeforeValidator(_positive_integer)


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

OptionalUpperStrList = UpperStrList | None
"""``UpperStrList`` for a key the query may leave out, spelling out that it is optional.

An explicit null means "not given", the same as an absent key: it matches the
``None`` member and falls through to the field's default. Only a value that was
meant to select something, such as ``""`` or ``[]``, is still an error.
"""

__all__ = [
    "OptionalUpperStrList",
    "StrList",
    "UpperStrList",
    "choice",
    "int_list",
    "int_range",
    "number_range",
    "positive_int",
]
