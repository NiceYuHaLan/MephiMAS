"""Централизованный арбитраж: приоритет, срочность, репутация."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ConflictResolver

if TYPE_CHECKING:
    from ..domain.kitchen import KitchenEnvironment


class ArbitrationResolver(ConflictResolver):
    """Krabs решает конфликт по правилам приоритезации, без торга."""

    name = "arbitration"
    label = "арбитраж по правилам"

    def plan(self, krabs, env: "KitchenEnvironment") -> None:
        return None

    def grant_order(self, env) -> list[dict]:
        return self._rank(self.queue, env)
