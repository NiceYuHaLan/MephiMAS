"""Защита от циклов: повторные заявки на станцию в пределах тика."""

from __future__ import annotations

from ..base import Guard, Verdict


class CycleGuard(Guard):
    name = "cycle"
    label = "защита от циклов"

    def __init__(self) -> None:
        self._seen: set[tuple] = set()

    def check(self, message, env) -> Verdict:
        if not (
            message.performative.value == "request"
            and message.content.get("action") == "station"
        ):
            return Verdict.ok()
        key = (
            message.sender,
            message.content.get("order_id"),
            message.content.get("task_index"),
            message.tick,
        )
        if key in self._seen:
            return Verdict.deny("cycle", "повторная заявка на станцию")
        self._seen.add(key)
        return Verdict.ok()
