"""Централизованная диспетчеризация: Krabs назначает повара напрямую."""

from __future__ import annotations

from typing import Any

from ..core.message import Message, Performative
from ..domain.kitchen import KitchenEnvironment
from ..domain.models import Order, OrderStatus
from .base import AssignmentMechanism


class CentralDispatcher:
    """Правила выбора повара и свободной станции (baseline-приоритеты)."""

    def __init__(self, cook_priority: dict[str, int] | None = None) -> None:
        self.cook_priority = cook_priority or {"spongebob": 0, "patrick": 1}

    def choose_cook(self, available: list[str]) -> str | None:
        if not available:
            return None
        return min(available, key=lambda cook: self.cook_priority.get(cook, 99))


class CentralDispatchMechanism(AssignmentMechanism):
    """Пуш-назначение: Krabs выбирает свободного повара по приоритету."""

    name = "central"
    label = "централизованная диспетчеризация"

    def __init__(self) -> None:
        super().__init__()
        self.dispatcher = CentralDispatcher()
        self.offers: dict[str, str] = {}
        self.offered_cooks: set[str] = set()

    @property
    def busy_cooks(self) -> set[str]:
        """Повара, которым уже отправлено предложение или которые заняты."""
        return self.offered_cooks

    def announce_new_orders(self, krabs: Any, env: "KitchenEnvironment") -> None:
        candidates = [
            order
            for order in env.orders.values()
            if order.status == OrderStatus.NEW
            and order.announced
            and order.order_id not in self.offers
            and order.order_id not in self.assigned_orders
        ]
        candidates.sort(key=lambda order: (-order.priority, order.created_tick, order.order_id))
        for order in candidates:
            available = [
                cook
                for cook in self.dispatcher.cook_priority
                if cook in env.agent_ids
                and cook not in self.offered_cooks
                and cook not in self._occupied_cooks(env)
            ]
            cook = self.dispatcher.choose_cook(available)
            if cook is None:
                break
            self.offers[order.order_id] = cook
            self.offered_cooks.add(cook)
            env.trace.event(
                "order_offered",
                tick=env.tick,
                mechanism=self.name,
                order_id=order.order_id,
                agent=cook,
            )
            krabs.send(
                Performative.REQUEST,
                cook,
                {
                    "action": "cook_order",
                    "order_id": order.order_id,
                    "priority": order.priority,
                    "mechanism": self.name,
                },
                conversation_id=self.new_conversation(order),
            )

    def _occupied_cooks(self, env: "KitchenEnvironment") -> set[str]:
        occupied: set[str] = set()
        for order in env.orders.values():
            if order.assignee and order.status in (
                OrderStatus.ASSIGNED,
                OrderStatus.IN_PROGRESS,
            ):
                occupied.add(order.assignee)
        return occupied

    def handle(self, krabs: Any, message: Message, env: "KitchenEnvironment") -> bool:
        content = message.content
        action = content.get("action")
        event = content.get("event")

        if message.performative == Performative.AGREE and action == "cook_order":
            order_id = content.get("order_id")
            self.offers.pop(order_id, None)
            self.offered_cooks.discard(message.sender)
            self._assign(order_id, message.sender, env, bid=None)
            return True

        if message.performative == Performative.REFUSE and action == "cook_order":
            order_id = content.get("order_id")
            self.offers.pop(order_id, None)
            self.offered_cooks.discard(message.sender)
            return True

        if message.performative == Performative.FAILURE and action == "cook_order":
            order_id = content.get("order_id")
            self.offers.pop(order_id, None)
            self.offered_cooks.discard(message.sender)
            env.cancel_order(order_id, content.get("event", "failure"))
            return True

        if message.performative == Performative.INFORM and event == "order_complete":
            self.offered_cooks.discard(message.sender)
            return False

        return False

    def _assign(
        self,
        order_id: str | None,
        cook: str,
        env: "KitchenEnvironment",
        bid: float | None,
    ) -> None:
        if order_id is None:
            return
        order = env.orders.get(order_id)
        if order is None:
            return
        order.status = OrderStatus.ASSIGNED
        order.assignee = cook
        order.assigned_tick = env.tick
        if bid is not None:
            order.bid = bid
        self.assigned_orders[order_id] = cook
        env.trace.event(
            "order_assigned",
            tick=env.tick,
            mechanism=self.name,
            order_id=order_id,
            agent=cook,
            bid=bid,
        )
