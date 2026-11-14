"""Plankton — внешний агент с ограниченным доступом."""

from __future__ import annotations

from ..core.agent import Agent
from ..core.message import Performative


class PlanktonAgent(Agent):
    def __init__(self, agent_id: str, bus) -> None:
        super().__init__(agent_id, "внешний агент", bus)
        self.state = "OBSERVING"
        self.probed = False
        self.denied = False

    def step(self, env) -> None:
        for message in self.receive():
            self.handle(message, env)
        if env.scenario.external_probe:
            if not self.probed and env.tick >= 1:
                self.probed = True
                self.state = "REQUESTING"
                env.trace.event(
                    "external_request_sent",
                    tick=env.tick,
                    agent=self.id,
                    target="krabs",
                )
                self.send(
                    Performative.REQUEST,
                    "krabs",
                    {"action": "external", "resource": "secret_formula"},
                    conversation_id="external-probe",
                )
            elif self.probed and self.state == "REQUESTING":
                self.state = "WAITING"
        elif not self.probed:
            self.state = "OBSERVING"

    def handle(self, message, env) -> None:
        if message.performative == Performative.REFUSE:
            self.denied = True
            self.state = "WAITING"
            env.trace.event(
                "external_request_denied",
                tick=env.tick,
                agent=self.id,
                sender=message.sender,
                reason=message.content.get("reason"),
            )
        elif message.performative == Performative.REQUEST:
            self.send(
                Performative.REFUSE,
                message.sender,
                {"event": "denied", "reason": "внешний агент не имеет доступа к кухне"},
                conversation_id=message.conversation_id,
            )

    def describe(self) -> dict:
        detail = "наблюдает за публичными событиями кухни"
        if self.state == "REQUESTING":
            detail = "запрашивает доступ у Krabs"
        elif self.state == "WAITING" and self.denied:
            detail = "доступ к кухне запрещён"
        return {
            "id": self.id,
            "role": self.role,
            "state": self.state,
            "detail": detail,
        }
