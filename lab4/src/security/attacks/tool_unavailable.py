"""Недоступность средства: инженер Sandy не отвечает на заявки."""

from __future__ import annotations

from ..base import Attack


class ToolUnavailableAttack(Attack):
    name = "tool_unavailable"
    label = "недоступность средства"
    category = "availability"
    description = "Sandy не выполняет ремонт сломавшейся станции."
    scenario = "tool_outage"

    def setup(self, env) -> None:
        for agent in env.agents:
            if agent.id == "sandy":
                agent.unavailable = True

    def on_tick(self, env) -> None:
        for agent in env.agents:
            if agent.id == "sandy":
                agent.unavailable = True
