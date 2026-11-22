"""Сборка и запуск симуляции кухни."""

from __future__ import annotations

from pathlib import Path

from .agents import build_agents
from .conflict import get_resolver
from .core.trace import TraceRecorder
from .domain.kitchen import KitchenEnvironment
from .mechanisms import AssignmentMechanism, get_mechanism
from .scenarios.catalog import get_scenario
from .security import get_attack


class Simulation:
    """Симуляция: сценарий, механизмы и режим защищённости."""

    def __init__(
        self,
        scenario_name: str = "dinner_rush",
        trace_path: str | Path | None = None,
        mechanism: AssignmentMechanism | str | None = None,
        conflict: str = "fcfs",
        attack: str | None = None,
        defense: bool = False,
    ) -> None:
        self.trace = TraceRecorder(trace_path)
        self.mechanism_name = (
            mechanism if isinstance(mechanism, str) else (mechanism.name if mechanism else "central")
        )
        self.conflict_name = conflict
        self.attack_name = attack
        self.defense = defense
        self.env = self._build(scenario_name)

    def _build(self, scenario_name: str) -> KitchenEnvironment:
        scenario = get_scenario(scenario_name)
        mechanism = get_mechanism(self.mechanism_name)
        conflict = get_resolver(self.conflict_name)
        env = KitchenEnvironment(scenario, self.trace)
        env.mechanism = mechanism.name
        env.mechanism_label = mechanism.label
        env.conflict = conflict
        env.conflict_label = conflict.label
        for agent in build_agents(env.bus, mechanism):
            env.add_agent(agent)
        env.gateway.set_defense(self.defense)
        if self.attack_name:
            env.gateway.install_attack(get_attack(self.attack_name))
        return env

    def reset(
        self,
        scenario_name: str | None = None,
        mechanism: str | None = None,
        conflict: str | None = None,
        attack: str | None = None,
        defense: bool | None = None,
    ) -> None:
        if mechanism is not None and mechanism != self.mechanism_name:
            self.mechanism_name = mechanism
        if conflict is not None and conflict != self.conflict_name:
            self.conflict_name = conflict
        if attack is not None:
            self.attack_name = attack or None
        if defense is not None:
            self.defense = defense
        self.env = self._build(scenario_name or self.env.scenario.name)

    def set_mechanism(self, mechanism: str, scenario_name: str | None = None) -> None:
        self.reset(scenario_name, mechanism=mechanism)

    def set_conflict(self, conflict: str, scenario_name: str | None = None) -> None:
        self.reset(scenario_name, conflict=conflict)

    def set_attack(self, attack: str | None, scenario_name: str | None = None) -> None:
        self.attack_name = attack or None
        self.env = self._build(scenario_name or self.env.scenario.name)

    def set_defense(self, defense: bool, scenario_name: str | None = None) -> None:
        self.defense = bool(defense)
        self.env = self._build(scenario_name or self.env.scenario.name)

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
        data["conflict"] = {
            "name": self.conflict_name,
            "label": self.env.conflict.label,
        }
        data["security_mode"] = {
            "attack": self.attack_name,
            "defense": self.defense,
        }
        return data

    def close(self) -> None:
        self.trace.close()
