"""Шина сообщений с раздельными очередями для каждого агента."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .message import Message, Performative
from .trace import TraceRecorder


class MessageBus:
    """Доставляет сообщения в очередь получателя и ведёт статистику."""

    def __init__(self, trace: TraceRecorder | None = None) -> None:
        self.trace = trace
        self.tick = 0
        self.seq = 0
        self.history: list[Message] = []
        self.stats: Counter[tuple[str, str, str]] = Counter()
        self._queues: dict[str, list[Message]] = defaultdict(list)
        self._registered: list[str] = []

    def register(self, *agent_ids: str) -> None:
        for agent_id in agent_ids:
            if agent_id not in self._registered:
                self._registered.append(agent_id)
            self._queues.setdefault(agent_id, [])

    @property
    def registered(self) -> tuple[str, ...]:
        return tuple(self._registered)

    def send(
        self,
        performative: Performative,
        sender: str,
        receiver: str,
        content: dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> Message:
        self.seq += 1
        message = Message(
            performative=performative,
            sender=sender,
            receiver=receiver,
            content=dict(content or {}),
            conversation_id=conversation_id,
            tick=self.tick,
            seq=self.seq,
        )
        self.history.append(message)
        self.stats[(sender, receiver, performative.value)] += 1
        if receiver == "*":
            targets = list(self._registered)
        else:
            if receiver not in self._registered:
                self.register(receiver)
            targets = [receiver]
        for target in targets:
            self._queues[target].append(message)
        if self.trace is not None:
            self.trace.event(
                "message",
                tick=self.tick,
                seq=self.seq,
                performative=performative.value,
                sender=sender,
                receiver=receiver,
                conversation_id=conversation_id,
                content=message.content,
            )
        return message

    def broadcast(
        self,
        performative: Performative,
        sender: str,
        content: dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> Message:
        return self.send(performative, sender, "*", content, conversation_id)

    def drain(self, agent_id: str) -> list[Message]:
        """Забирает все сообщения из очереди агента."""
        messages = self._queues.get(agent_id, [])
        self._queues[agent_id] = []
        return messages

    def pending(self, agent_id: str) -> int:
        return len(self._queues.get(agent_id, []))

    def count_by_performative(self) -> dict[str, int]:
        result: Counter[str] = Counter()
        for message in self.history:
            result[message.performative.value] += 1
        return dict(result)
