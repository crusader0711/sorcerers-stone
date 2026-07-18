"""Connector registry — entry-point style plugin discovery.

Ref: .kiro/specs/phase-1-architecture/design.md §8.2
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.connectors.base import Connector
    from app.services.crypto import FieldCipher
    from app.models import ConnectorItem


_registry: dict[str, type] = {}


def register(source_type: str):
    """Decorator to register a connector class for a given source_type."""

    def decorator(cls):
        _registry[source_type] = cls
        return cls

    return decorator


def get_connector(item: "ConnectorItem", cipher: "FieldCipher") -> "Connector":
    """Instantiate the appropriate connector for a given ConnectorItem.

    Raises:
        KeyError: If source_type is not registered.
    """
    cls = _registry[item.source_type]
    return cls(item=item, cipher=cipher)


def list_registered() -> list[str]:
    """Return all registered source types."""
    return list(_registry.keys())
