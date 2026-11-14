"""Централизованная диспетчеризация заказов и станций."""

from __future__ import annotations

from ..domain.models import Station, StationKind


class CentralDispatcher:
    """Правила выбора повара и свободной станции."""

    def __init__(self, cook_priority: dict[str, int] | None = None) -> None:
        self.cook_priority = cook_priority or {"spongebob": 0, "patrick": 1}

    def choose_cook(self, available: list[str]) -> str | None:
        if not available:
            return None
        return min(available, key=lambda cook: self.cook_priority.get(cook, 99))

    def choose_station(
        self, stations: list[Station], kind: StationKind, reserved: set[str]
    ) -> Station | None:
        for station in stations:
            if (
                station.kind == kind
                and station.is_free
                and station.station_id not in reserved
            ):
                return station
        return None
