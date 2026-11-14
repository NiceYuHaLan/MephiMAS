"""Сборка и запуск симуляции кухни."""

from __future__ import annotations

from pathlib import Path

from .agents import build_agents
from .core.trace import TraceRecorder
from .domain.kitchen import KitchenEnvironment
from .scenarios.catalog import get_scenario


class Simulation:
    """Симуляция: сценарий, среда, агенты и трасса."""

    def __init__(
        self,
        scenario_name: str = "dinner_rush",
        trace_path: str | Path | None = None,
    ) -> None:
        self.trace = TraceRecorder(trace_path)
        self.env = self._build(scenario_name)

    def _build(self, scenario_name: str) -> KitchenEnvironment:
        scenario = get_scenario(scenario_name)
        env = KitchenEnvironment(scenario, self.trace)
        for agent in build_agents(env.bus):
            env.add_agent(agent)
        return env

    def reset(self, scenario_name: str | None = None) -> None:
        self.env = self._build(scenario_name or self.env.scenario.name)

    def step(self) -> None:
        self.env.step()

    def run(self, max_ticks: int | None = None, on_tick=None) -> dict:
        return self.env.run(max_ticks=max_ticks, on_tick=on_tick)

    def snapshot(self) -> dict:
        data = self.env.snapshot()
        data["tick_limit"] = self.env.scenario.max_ticks
        return data

    def close(self) -> None:
        self.trace.close()
