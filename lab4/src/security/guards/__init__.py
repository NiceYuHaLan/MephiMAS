"""Реестр защитных правил."""

from __future__ import annotations

from .authentication import AuthenticationGuard
from .authorization import AuthorizationGuard
from .consistency import ConsistencyGuard
from .cycle import CycleGuard
from .integrity import IntegrityGuard
from .provenance import ProvenanceGuard
from .replay import ReplayGuard

GUARDS: dict[str, type] = {
    guard.name: guard
    for guard in (
        AuthenticationGuard,
        ProvenanceGuard,
        AuthorizationGuard,
        IntegrityGuard,
        ReplayGuard,
        ConsistencyGuard,
        CycleGuard,
    )
}


def build_guards() -> list:
    """Собрать конвейер защит в порядке применения."""
    return [guard() for guard in GUARDS.values()]


def list_guards() -> list[type]:
    return list(GUARDS.values())


__all__ = [
    "GUARDS",
    "AuthenticationGuard",
    "AuthorizationGuard",
    "ConsistencyGuard",
    "CycleGuard",
    "IntegrityGuard",
    "ProvenanceGuard",
    "ReplayGuard",
    "build_guards",
    "list_guards",
]
