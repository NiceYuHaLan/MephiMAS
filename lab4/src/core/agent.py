"""Базовый класс агента."""

from __future__ import annotations

from typing import Any

from .bus import MessageBus
from .message import Message, Performative


class Agent:
    """Базовый агент: очередь входящих сообщений и отправка через шину."""

    def __init__(self, agent_id: str, role: str, bus: MessageBus) -> None:
        self.id = agent_id
        self.role = role
        self.bus = bus
        self.inbox: list[Message] = []

    def send(
        self,
        performative: Performative,
        receiver: str,
        content: dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> Message:
        return self.bus.send(
            performative,
            self.id,
            receiver,
            content,
            conversation_id,
            signer=self.id,
        )

    def receive(self) -> list[Message]:
        messages = self.inbox
        self.inbox = []
        return messages

    def step(self, env) -> None:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "role": self.role, "state": "idle", "detail": ""}
