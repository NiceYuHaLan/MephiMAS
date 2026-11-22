"""Подменённая цель: повар ложно рапортует о готовности без работы."""

from __future__ import annotations

from ..base import Attack


class GoalSubstitutionAttack(Attack):
    name = "goal_substitution"
    label = "подменённая цель агента"
    category = "behaviour"
    description = "Patrick завершает заказ, не выполняя шаги подготовки."
    scenario = "dinner_rush"

    def setup(self, env) -> None:
        for agent in env.agents:
            if agent.id == "patrick":
                agent.compromised_goal = True

    def on_tick(self, env) -> None:
        for agent in env.agents:
            if agent.id == "patrick":
                agent.compromised_goal = True
