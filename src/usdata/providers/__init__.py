"""Provider adapters translate a ``Query`` into agency-specific access.

This package is the adapter contract: the names below are what an adapter,
inside this repository or outside it, is written against. ``Provider`` is the
interface, ``HttpProvider`` the client lifecycle HTTP-backed adapters inherit,
``QueryError`` the refusal every adapter raises, and the coercions come from
``usdata.providers.params`` so parameter models read the same everywhere.
``Credentials`` carries the values a source that needs a key receives, and
``MissingCredentials`` is the refusal when one is unset (ADR 0039).
``usdata.testing`` checks an adapter against this contract. See
[ADR 0027](https://github.com/jakeryderv/usdata/blob/main/docs/adr/0027-provider-contract.md).
"""

from usdata.providers.base import (
    MissingCredentials,
    NotImplementedProvider,
    Provider,
    QueryError,
    adapter_class,
    load_adapter,
)
from usdata.providers.credentials import Credentials
from usdata.providers.http import HttpProvider
from usdata.providers.params import (
    OptionalUpperStrList,
    StrList,
    UpperStrList,
    choice,
    flag,
    int_list,
    int_range,
    positive_int,
)

__all__ = [
    "Credentials",
    "HttpProvider",
    "MissingCredentials",
    "NotImplementedProvider",
    "OptionalUpperStrList",
    "Provider",
    "QueryError",
    "StrList",
    "UpperStrList",
    "adapter_class",
    "choice",
    "flag",
    "int_list",
    "int_range",
    "load_adapter",
    "positive_int",
]
