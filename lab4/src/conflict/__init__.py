"""Разрешение конфликтов за дефицитные станции."""

from __future__ import annotations

from .arbitration import ArbitrationResolver
from .base import ConflictResolver
from .fcfs import FcfsResolver
from .negotiation import NegotiationResolver

CONFLICT_MODES: dict[str, type[ConflictResolver]] = {
    FcfsResolver.name: FcfsResolver,
    NegotiationResolver.name: NegotiationResolver,
    ArbitrationResolver.name: ArbitrationResolver,
}


def get_resolver(name: str) -> ConflictResolver:
    try:
        return CONFLICT_MODES[name]()
    except KeyError as exc:
        available = ", ".join(sorted(CONFLICT_MODES))
        raise ValueError(
            f"неизвестный режим конфликта {name!r}; доступны: {available}"
        ) from exc


def list_resolvers() -> list[type[ConflictResolver]]:
    return list(CONFLICT_MODES.values())


__all__ = [
    "CONFLICT_MODES",
    "ArbitrationResolver",
    "ConflictResolver",
    "FcfsResolver",
    "NegotiationResolver",
    "get_resolver",
    "list_resolvers",
]
