"""Sandy — инженер по обслуживанию станций."""

from __future__ import annotations

from ..core.agent import Agent
from ..core.message import Performative


class SandyAgent(Agent):
    def __init__(self, agent_id: str, bus, repair_ticks: int = 3) -> None:
        super().__init__(agent_id, "инженер по оборудованию", bus)
        self.repair_ticks = repair_ticks
        self.station_id: str | None = None
        self.repair_until = 0
        self.state = "IDLE"

    def step(self, env) -> None:
        for message in self.receive():
            self.handle(message, env)
        if self.station_id is not None and env.tick >= self.repair_until:
            env.repair_station(self.station_id)
            env.trace.event(
                "station_repaired",
                tick=env.tick,
                station_id=self.station_id,
                agent=self.id,
            )
            self.send(
                Performative.INFORM,
                "krabs",
                {"event": "repair_done", "station_id": self.station_id},
                conversation_id=f"repair-{self.station_id}",
            )
            self.station_id = None
            self.repair_until = 0
            self.state = "IDLE"

    def handle(self, message, env) -> None:
        if (
            message.performative == Performative.REQUEST
            and message.content.get("action") == "repair"
        ):
            if self.station_id is None:
                self.station_id = message.content["station_id"]
                self.repair_until = env.tick + self.repair_ticks
                self.state = "REPAIRING"
                env.trace.event(
                    "repair_started",
                    tick=env.tick,
                    station_id=self.station_id,
                    agent=self.id,
                )
                self.send(
                    Performative.AGREE,
                    "krabs",
                    {
                        "action": "repair",
                        "station_id": self.station_id,
                        "duration": self.repair_ticks,
                    },
                    conversation_id=message.conversation_id,
                )
            else:
                self.send(
                    Performative.REFUSE,
                    "krabs",
                    {
                        "action": "repair",
                        "station_id": message.content.get("station_id"),
                    },
                    conversation_id=message.conversation_id,
                )

    def describe(self) -> dict:
        detail = ""
        if self.station_id is not None:
            detail = f"ремонт {self.station_id} до тика {self.repair_until}"
        return {"id": self.id, "role": self.role, "state": self.state, "detail": detail}
