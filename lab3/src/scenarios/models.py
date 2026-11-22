"""Описание сценария: расписание заказов и поломок."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OrderSpec:
    tick: int
    customer: str
    table: int
    items: tuple[str, ...]
    priority: int = 0
    patience: int = 20


@dataclass(frozen=True)
class BreakdownSpec:
    tick: int
    station_id: str
    repair_ticks: int = 3


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    description: str
    orders: tuple[OrderSpec, ...]
    breakdowns: tuple[BreakdownSpec, ...] = field(default_factory=tuple)
    external_probe: bool = False
    max_ticks: int = 200
