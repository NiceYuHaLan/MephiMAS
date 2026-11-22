"""Baseline: очередь FCFS — как в лабораторной работе № 2."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ConflictResolver

if TYPE_CHECKING:
    from ..domain.kitchen import KitchenEnvironment


class FcfsResolver(ConflictResolver):
    """Первая заявка — первая получает станцию (поведение lab2)."""

    name = "fcfs"
    label = "очередь FCFS (до)"

    def plan(self, krabs, env: "KitchenEnvironment") -> None:
        return None
