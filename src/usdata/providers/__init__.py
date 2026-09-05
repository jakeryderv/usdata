"""Provider adapters translate a ``Query`` into agency-specific access."""

from usdata.providers.base import Provider, load_adapter

__all__ = ["Provider", "load_adapter"]
