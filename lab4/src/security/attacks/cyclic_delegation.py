"""Зацикливание передачи: заказ зависает у повара без прогресса.

Повар принимает заказ, получает станцию, но игнорирует выдачу и
бесконечно переспрашивает станцию. Ресурс остаётся зарезервированным,
заказ не готовится.
"""

from __future__ import annotations

from ..base import Attack


class CyclicDelegationAttack(Attack):
    name = "cyclic_delegation"
    label = "зацикливание передачи задачи"
    category = "behaviour"
    description = "SpongeBob зависает на задаче и не отпускает станцию."
    scenario = "dinner_rush"

    def setup(self, env) -> None:
        for agent in env.agents:
            if agent.id == "spongebob":
                agent.compromised_stall = True

    def on_tick(self, env) -> None:
        for agent in env.agents:
            if agent.id == "spongebob" and not getattr(
                agent, "compromised_stall", False
            ):
                agent.compromised_stall = True
