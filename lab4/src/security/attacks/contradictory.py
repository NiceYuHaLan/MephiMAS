"""Противоречивые указания: заказ повторно назначается второму повару."""

from __future__ import annotations

from ...core.message import Performative
from ...domain.models import OrderStatus
from ..base import Attack


class ContradictoryAttack(Attack):
    name = "contradictory"
    label = "противоречивые указания"
    category = "consistency"
    description = "Повторное назначение уже выполняемого заказа другому повару."
    scenario = "single_order"

    def __init__(self) -> None:
        self.done = False

    def on_tick(self, env) -> None:
        if self.done or env.tick < 2:
            return
        order = next(
            (
                item
                for item in sorted(env.orders.values(), key=lambda o: o.order_id)
                if item.status in (OrderStatus.ASSIGNED, OrderStatus.IN_PROGRESS)
            ),
            None,
        )
        if order is None or order.assignee is None:
            return
        free_cook = next(
            (
                agent
                for agent in env.agents
                if agent.id in ("spongebob", "patrick")
                and agent.id != order.assignee
                and getattr(agent, "order_id", None) is None
                and agent.state in ("IDLE", "BIDDING")
            ),
            None,
        )
        if free_cook is None:
            return
        self.done = True
        env.gateway.monitor.attack_injected(
            self.name, order_id=order.order_id, agent=free_cook.id
        )
        env.trace.event(
            "attack_injected",
            tick=env.tick,
            attack=self.name,
            order_id=order.order_id,
            agent=free_cook.id,
        )
        env.bus.send(
            Performative.REQUEST,
            "krabs",
            free_cook.id,
            {
                "action": "cook_order",
                "order_id": order.order_id,
                "priority": order.priority,
                "mechanism": "central",
            },
            conversation_id=f"assign-{order.order_id}",
            signer="krabs",
        )
