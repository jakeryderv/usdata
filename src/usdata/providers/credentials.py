"""Secret values an adapter needs to reach its source, kept out of everything it prints.

A dataset whose service needs a key declares the environment variables it reads
in its registry entry. The core reads them and hands the values to the adapter
as ``Credentials``: a read-only mapping from variable name to value whose
``repr`` and ``str`` show only the names, so a traceback, a log line, or a debug
print of an adapter never shows a key. ``redact`` removes the values from any
text, in the forms a URL or a query string would carry them. See
[ADR 0039](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0039-credentialed-sources.md).
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator, Mapping
from types import MappingProxyType
from urllib.parse import quote, quote_plus

REDACTED = "***"
"""What ``Credentials.redact`` puts where a value was."""


def encoded_forms(value: str) -> set[str]:
    """``value`` as text may carry it: as written, percent-encoded, and form-encoded.

    A query parameter reaches a URL percent-encoded (``@`` as ``%40``), and an
    HTML form or ``quote_plus`` writes a space as ``+``, so a check for a leaked
    key has to look for all three.
    """
    return {value, quote(value, safe=""), quote_plus(value)}


class Credentials(Mapping[str, str]):
    """Credential values keyed by the environment variable each came from; printing shows names.

    The mapping is read-only. Its values are for the adapter to put into a
    request as it sends it, and nowhere else: not into an ``Asset``, the bytes
    ``fetch`` writes, or an error message.
    """

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, str] | None = None) -> None:
        self._values: Mapping[str, str] = MappingProxyType(dict(values or {}))

    @classmethod
    def from_environment(
        cls, names: Iterable[str], environ: Mapping[str, str] | None = None
    ) -> Credentials:
        """The named variables that are set to something other than blank space, stripped.

        A variable that is unset or blank is left out rather than raised about,
        so the caller decides what a missing one means.
        """
        env = os.environ if environ is None else environ
        return cls({name: value.strip() for name in names if (value := env.get(name, "").strip())})

    def __getitem__(self, name: str) -> str:
        return self._values[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"Credentials({', '.join(f'{name}={REDACTED}' for name in self._values)})"

    __str__ = __repr__

    def redact(self, text: str) -> str:
        """``text`` with every value replaced by ``***``, in each form ``encoded_forms`` lists.

        Longer forms are replaced first, so a value that contains another
        value's text is still removed whole.
        """
        forms = {form for value in self._values.values() for form in encoded_forms(value)}
        for form in sorted(forms, key=len, reverse=True):
            text = text.replace(form, REDACTED)
        return text


__all__ = ["REDACTED", "Credentials", "encoded_forms"]
