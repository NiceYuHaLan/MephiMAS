"""Шина сообщений с раздельными очередями для каждого агента."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .message import Message, Performative
from .trace import TraceRecorder


class MessageBus:
    """Доставляет сообщения в очередь получателя и ведёт статистику.

    Если к шине подключён шлюз безопасности, исходящие сообщения
    подписываются, а входящие проходят проверки перед доставкой.
    """

    def __init__(self, trace: TraceRecorder | None = None) -> None:
        self.trace = trace
        self.tick = 0
        self.seq = 0
        self.history: list[Message] = []
        self.stats: Counter[tuple[str, str, str]] = Counter()
        self._queues: dict[str, list[Message]] = defaultdict(list)
        self._registered: list[str] = []
        self.gateway = None
        self.env = None

    def register(self, *agent_ids: str) -> None:
        for agent_id in agent_ids:
            if agent_id not in self._registered:
                self._registered.append(agent_id)
            self._queues.setdefault(agent_id, [])
            if self.gateway is not None:
                self.gateway.keyring.issue(agent_id)

    def send(
        self,
        performative: Performative,
        sender: str,
        receiver: str,
        content: dict[str, Any] | None = None,
        conversation_id: str = "",
        signer: str | None = None,
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
        if self.gateway is not None:
            if signer is not None:
                self.gateway.sign(message, signer)
            self.gateway.on_send(message, self.env)
            verdict = self.gateway.inspect(message, self.env)
            if not verdict.allow:
                return message
        self._deliver(message)
        return message

    def submit_raw(self, message: Message) -> Message:
        """Доставить готовое сообщение (подмена/повтор) через проверки."""
        self.seq += 1
        message.seq = self.seq
        if self.gateway is not None:
            verdict = self.gateway.inspect(message, self.env)
            if not verdict.allow:
                return message
        self._deliver(message)
        return message

    def _deliver(self, message: Message) -> None:
        self.history.append(message)
        self.stats[(message.sender, message.receiver, message.performative.value)] += 1
        if message.receiver == "*":
            targets = list(self._registered)
        else:
            if message.receiver not in self._registered:
                self.register(message.receiver)
            targets = [message.receiver]
        for target in targets:
            self._queues[target].append(message)
        if self.gateway is not None:
            self.gateway.monitor.observe(message)
        if self.trace is not None:
            self.trace.event(
                "message",
                tick=self.tick,
                seq=self.seq,
                performative=message.performative.value,
                sender=message.sender,
                receiver=message.receiver,
                conversation_id=message.conversation_id,
                content=message.content,
            )

    def drain(self, agent_id: str) -> list[Message]:
        """Забирает все сообщения из очереди агента."""
        messages = self._queues.get(agent_id, [])
        self._queues[agent_id] = []
        return messages

    def pending(self, agent_id: str) -> int:
        return len(self._queues.get(agent_id, []))
