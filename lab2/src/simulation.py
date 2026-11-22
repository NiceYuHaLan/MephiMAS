"""Сборка и запуск симуляции кухни."""

from __future__ import annotations

from pathlib import Path

from .agents import build_agents
from .core.trace import TraceRecorder
from .domain.kitchen import KitchenEnvironment
from .mechanisms import AssignmentMechanism, get_mechanism
from .scenarios.catalog import get_scenario


class Simulation:
    """Симуляция: сценарий, механизм распределения, среда и трасса."""

    def __init__(
        self,
        scenario_name: str = "dinner_rush",
        trace_path: str | Path | None = None,
        mechanism: AssignmentMechanism | str | None = None,
    ) -> None:
        self.trace = TraceRecorder(trace_path)
        self.mechanism_name = (
            mechanism if isinstance(mechanism, str) else (mechanism.name if mechanism else "central")
        )
        self.env = self._build(scenario_name)

    def _build(self, scenario_name: str) -> KitchenEnvironment:
        scenario = get_scenario(scenario_name)
        mechanism = get_mechanism(self.mechanism_name)
        env = KitchenEnvironment(scenario, self.trace)
        env.mechanism = mechanism.name
        env.mechanism_label = mechanism.label
        for agent in build_agents(env.bus, mechanism):
            env.add_agent(agent)
        return env

    def reset(self, scenario_name: str | None = None, mechanism: str | None = None) -> None:
        if mechanism is not None and mechanism != self.mechanism_name:
            self.mechanism_name = mechanism
        self.env = self._build(scenario_name or self.env.scenario.name)

    def set_mechanism(self, mechanism: str, scenario_name: str | None = None) -> None:
        self.reset(scenario_name, mechanism=mechanism)

    def step(self) -> None:
        self.env.step()

    def run(self, max_ticks: int | None = None, on_tick=None) -> dict:
        return self.env.run(max_ticks=max_ticks, on_tick=on_tick)

    def snapshot(self) -> dict:
        data = self.env.snapshot()
        data["tick_limit"] = self.env.scenario.max_ticks
        data["mechanism"] = {
            "name": self.mechanism_name,
            "label": self.env.mechanism_label,
        }
        return data

    def close(self) -> None:
        self.trace.close()
