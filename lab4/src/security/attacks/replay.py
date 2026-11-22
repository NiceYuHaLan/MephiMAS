"""Повтор сообщения: повторная доставка подписанного order_complete."""

from __future__ import annotations

import copy

from ...domain.models import OrderStatus
from ..base import Attack


class ReplayAttack(Attack):
    name = "replay"
    label = "повтор сообщения"
    category = "replay"
    description = "Повтор подписанного order_complete после подачи заказа."
    scenario = "dinner_rush"

    def __init__(self) -> None:
        self.captured: dict[str, object] = {}
        self.replayed: set[str] = set()
        self.done = False

    def on_send(self, message, env) -> None:
        if not (
            message.performative.value == "inform"
            and message.content.get("event") == "order_complete"
        ):
            return
        order_id = message.content.get("order_id")
        if order_id and order_id not in self.captured:
            self.captured[order_id] = copy.copy(message)

    def on_tick(self, env) -> None:
        if self.done:
            return
        for order_id, stored in list(self.captured.items()):
            if order_id in self.replayed:
                continue
            order = env.orders.get(order_id)
            if order is None or order.status != OrderStatus.SERVED:
                continue
            self.replayed.add(order_id)
            self.done = True
            clone = copy.copy(stored)
            clone.tick = env.tick
            clone.content = dict(stored.content)
            env.gateway.monitor.attack_injected(
                self.name, order_id=order_id, detail="replayed order_complete"
            )
            env.trace.event(
                "attack_injected",
                tick=env.tick,
                attack=self.name,
                order_id=order_id,
            )
            env.bus.submit_raw(clone)
