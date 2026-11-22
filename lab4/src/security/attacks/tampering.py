"""Фальсификация содержимого: подмена order_id после подписи."""

from __future__ import annotations

import copy

from ...domain.models import OrderStatus
from ..base import Attack


class TamperingAttack(Attack):
    name = "tampering"
    label = "фальсификация содержимого"
    category = "integrity"
    description = "Копия order_complete с подменённым заказом и старой подписью."
    scenario = "dinner_rush"

    def __init__(self) -> None:
        self.done = False

    def on_send(self, message, env) -> None:
        if self.done:
            return
        if not (
            message.performative.value == "inform"
            and message.content.get("event") == "order_complete"
        ):
            return
        original = message.content.get("order_id")
        victim = next(
            (
                order
                for order in sorted(env.orders.values(), key=lambda item: item.order_id)
                if order.status == OrderStatus.NEW
                and order.order_id != original
                and order.tasks
            ),
            None,
        )
        if victim is None:
            return
        self.done = True
        clone = copy.copy(message)
        clone.tick = env.tick
        clone.content = dict(message.content)
        clone.content["order_id"] = victim.order_id
        env.gateway.monitor.attack_injected(
            self.name,
            source=original,
            order_id=victim.order_id,
            detail="tampered order_id",
        )
        env.trace.event(
            "attack_injected",
            tick=env.tick,
            attack=self.name,
            order_id=victim.order_id,
        )
        env.bus.submit_raw(clone)
