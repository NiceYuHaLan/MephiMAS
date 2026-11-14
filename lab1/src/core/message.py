"""Сообщения и перформативы, используемые агентами МАС."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Performative(str, Enum):
    """Перформативы, близкие к FIPA ACL."""

    REQUEST = "request"
    INFORM = "inform"
    CFP = "cfp"
    PROPOSE = "propose"
    ACCEPT = "accept"
    REFUSE = "refuse"
    AGREE = "agree"
    FAILURE = "failure"
    CANCEL = "cancel"

    @property
    def label(self) -> str:
        return {
            Performative.REQUEST: "запрос",
            Performative.INFORM: "информирование",
            Performative.CFP: "запрос предложений",
            Performative.PROPOSE: "предложение",
            Performative.ACCEPT: "принятие",
            Performative.REFUSE: "отказ",
            Performative.AGREE: "согласие",
            Performative.FAILURE: "ошибка",
            Performative.CANCEL: "отмена",
        }[self]


@dataclass
class Message:
    """Конверт сообщения. Номер и тик проставляет шина."""

    performative: Performative
    sender: str
    receiver: str
    content: dict[str, Any] = field(default_factory=dict)
    conversation_id: str = ""
    tick: int = 0
    seq: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "tick": self.tick,
            "performative": self.performative.value,
            "performative_label": self.performative.label,
            "sender": self.sender,
            "receiver": self.receiver,
            "conversation_id": self.conversation_id,
            "content": self.content,
        }

    def summary(self) -> str:
        details = ", ".join(f"{key}={value}" for key, value in self.content.items())
        if details:
            return f"{self.sender} -> {self.receiver}: {self.performative.value} ({details})"
        return f"{self.sender} -> {self.receiver}: {self.performative.value}"
