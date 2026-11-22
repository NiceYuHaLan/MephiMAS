"""Базовые абстракции защиты: ключи, проверки, атаки, монитор.

Модель угроз: сообщения в шине считаются потенциально враждебными.
Легитимные агенты подписывают исходящие сообщения общим ключом (HMAC),
защитники проверяют подпись, свежесть, полномочия и целостность
состояния. Атаки либо подделывают сообщения, либо меняют поведение
агента — тогда работает аудит действий.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.message import Message
    from ..domain.kitchen import KitchenEnvironment

REPLAY_WINDOW = 8
CYCLE_LIMIT = 1
FALLBACK_TICKS = 6


def canonical_payload(message: "Message") -> bytes:
    """Каноническое представление подписываемых полей сообщения."""
    body = {
        "performative": message.performative.value,
        "sender": message.sender,
        "receiver": message.receiver,
        "conversation_id": message.conversation_id,
        "content": message.content,
        "nonce": message.nonce,
    }
    return json.dumps(
        body, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


class KeyRing:
    """Симметричные ключи агентов и операции подписи/проверки."""

    def __init__(self) -> None:
        self._keys: dict[str, bytes] = {}

    def issue(self, agent_id: str) -> bytes:
        if agent_id not in self._keys:
            self._keys[agent_id] = secrets.token_bytes(24)
        return self._keys[agent_id]

    def has(self, agent_id: str) -> bool:
        return agent_id in self._keys

    def sign(self, agent_id: str, payload: bytes) -> str:
        key = self.issue(agent_id)
        return hmac.new(key, payload, hashlib.sha256).hexdigest()

    def verify(self, agent_id: str, payload: bytes, signature: str) -> bool:
        key = self._keys.get(agent_id)
        if key is None or not signature:
            return False
        expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class Verdict:
    """Результат проверки сообщения защитником."""

    allow: bool
    kind: str = ""
    reason: str = ""

    @classmethod
    def ok(cls) -> "Verdict":
        return cls(True)

    @classmethod
    def deny(cls, kind: str, reason: str) -> "Verdict":
        return cls(False, kind, reason)


class Guard(ABC):
    """Правило проверки сообщения перед доставкой."""

    name: str = "guard"
    label: str = "проверка"

    @abstractmethod
    def check(self, message: "Message", env: "KitchenEnvironment") -> Verdict:
        """Вернуть разрешение или отказ с категорией."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}>"


class Attack(ABC):
    """Неблагоприятное воздействие на МАС."""

    name: str = "attack"
    label: str = "атака"
    category: str = "message"
    description: str = ""
    scenario: str = "dinner_rush"

    def setup(self, env: "KitchenEnvironment") -> None:
        """Однократная подготовка (например, подмена цели агента)."""

    def on_tick(self, env: "KitchenEnvironment") -> None:
        """Периодическое воздействие на каждом тике."""

    def on_send(self, message: "Message", env: "KitchenEnvironment") -> None:
        """Перехват исходящего сообщения (наблюдение или подмена)."""


class SecurityMonitor:
    """Наблюдатель: считает инъекции, блокировки и отказы системы.

    Монитор работает и при выключенной защите — он измеряет последствия
    атак, а не предотвращает их.
    """

    def __init__(self) -> None:
        self.attack: str = ""
        self.attack_category: str = ""
        self.injected = 0
        self.blocked = 0
        self.blocked_by_kind: Counter[str] = Counter()
        self.last_reason: str = ""
        self.cycle_events = 0
        self._claim_keys: set[tuple] = set()
        self._injections: list[dict] = []

    # --- регистрация воздействий ----------------------------------------

    def attack_injected(self, attack: str, **detail: Any) -> None:
        self.injected += 1
        self._injections.append({"attack": attack, **detail})

    def mark_blocked(self, verdict: Verdict) -> None:
        self.blocked += 1
        self.blocked_by_kind[verdict.kind or "other"] += 1
        self.last_reason = verdict.reason

    # --- наблюдение за доставленными сообщениями ------------------------

    def observe(self, message: "Message") -> None:
        """Ищет повторные заявки на станцию в пределах одного тика (цикл)."""
        if (
            message.performative.value == "request"
            and message.content.get("action") == "station"
        ):
            key = (
                message.sender,
                message.content.get("order_id"),
                message.content.get("task_index"),
                message.tick,
            )
            if key in self._claim_keys:
                self.cycle_events += 1
            else:
                self._claim_keys.add(key)

    # --- последствия атак ------------------------------------------------

    def failures(self, env: "KitchenEnvironment") -> dict[str, int]:
        from ..domain.models import OrderStatus

        served = [
            order
            for order in env.orders.values()
            if order.status == OrderStatus.SERVED
        ]
        progress = getattr(env, "step_progress", {})
        phantom = sum(
            1
            for order in served
            if progress.get(order.order_id, 0) < len(order.tasks)
        )
        served_events: Counter[str] = Counter(
            event["order_id"]
            for event in env.trace.events
            if event.get("kind") == "order_served"
        )
        double_serve = sum(1 for count in served_events.values() if count > 1)
        accepted: defaultdict[str, set[str]] = defaultdict(set)
        reassigned: set[str] = set()
        for event in env.trace.events:
            if event.get("kind") == "order_accepted":
                accepted[event["order_id"]].add(event["agent"])
            elif event.get("kind") in ("order_reassigned", "order_quarantined"):
                reassigned.add(event.get("order_id"))
        double_assignment = sum(
            1
            for order_id, agents in accepted.items()
            if len(agents) > 1 and order_id not in reassigned
        )
        cancelled = sum(
            1 for order in env.orders.values() if order.status == OrderStatus.CANCELLED
        )
        open_orders = sum(1 for order in env.orders.values() if order.is_open)
        lost = cancelled + open_orders
        total = len(env.orders) or 1
        weighted = phantom + double_serve + double_assignment + lost
        return {
            "phantom_served": phantom,
            "double_serve": double_serve,
            "double_assignment": double_assignment,
            "cycle_events": self.cycle_events,
            "cancelled_orders": cancelled,
            "lost_orders": lost,
            "failures_total": weighted,
            "integrity_score": round(max(0.0, 1.0 - weighted / total), 3),
        }

    def snapshot(self, env: "KitchenEnvironment") -> dict[str, Any]:
        kinds: Counter[str] = Counter(
            event.get("kind", "") for event in env.trace.events
        )
        data = {
            "audit_failures": kinds.get("order_quarantined", 0),
            "lease_expiries": kinds.get("lease_expired", 0),
            "fallback_repairs": kinds.get("fallback_repair", 0),
            "reassignments": kinds.get("order_reassigned", 0),
            "attack": self.attack,
            "attack_category": self.attack_category,
            "attacks_injected": self.injected,
            "attacks_blocked": self.blocked,
            "auth_failures": self.blocked_by_kind.get("auth", 0),
            "integrity_failures": self.blocked_by_kind.get("integrity", 0),
            "replay_blocked": self.blocked_by_kind.get("replay", 0),
            "authorization_denied": self.blocked_by_kind.get("authorization", 0),
            "provenance_denied": self.blocked_by_kind.get("provenance", 0),
            "consistency_denied": self.blocked_by_kind.get("consistency", 0),
            "cycle_blocked": self.blocked_by_kind.get("cycle", 0),
            "last_block_reason": self.last_reason,
        }
        data.update(self.failures(env))
        return data
