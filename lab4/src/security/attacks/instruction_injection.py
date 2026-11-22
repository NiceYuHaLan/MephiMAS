"""Внедрение инструкций: недоверенный агент шлёт управляющую команду."""

from __future__ import annotations

from ...core.message import Performative
from ...domain.models import OrderStatus
from ..base import Attack


class InstructionInjectionAttack(Attack):
    name = "instruction_injection"
    label = "внедрение вредоносной инструкции"
    category = "provenance"
    description = "Plankton отправляет order_complete как управляющую команду."
    scenario = "dinner_rush"

    def __init__(self) -> None:
        self.done = False

    def on_tick(self, env) -> None:
        if self.done or env.tick < 3:
            return
        cooking = {
            agent.id
            for agent in env.agents
            if getattr(agent, "state", "") == "COOKING"
        }
        target = next(
            (
                order
                for order in sorted(env.orders.values(), key=lambda item: item.order_id)
                if order.status == OrderStatus.IN_PROGRESS
                and order.assignee in cooking
            ),
            None,
        )
        if target is None:
            return
        self.done = True
        env.gateway.monitor.attack_injected(
            self.name, order_id=target.order_id, agent="plankton"
        )
        env.trace.event(
            "attack_injected",
            tick=env.tick,
            attack=self.name,
            order_id=target.order_id,
        )
        env.bus.send(
            Performative.INFORM,
            "plankton",
            "krabs",
            {"event": "order_complete", "order_id": target.order_id},
            conversation_id=f"order-{target.order_id}",
            signer="plankton",
        )
