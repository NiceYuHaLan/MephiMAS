"""FIPA Contract Net: CFP -> PROPOSE -> ACCEPT/REFUSE."""

from __future__ import annotations

from typing import Any

from ..core.message import Message, Performative
from ..domain.kitchen import KitchenEnvironment
from ..domain.models import Order, OrderStatus
from .base import AssignmentMechanism

NO_BID = float("-inf")


class ContractNetMechanism(AssignmentMechanism):
    """Контрактная сеть: повара делают ставки-оценки, Krabs выбирает лучшую.

    Ставка (score) тем выше, чем быстрее повар и чем меньше его нагрузка.
    Занятые повара отвечают REFUSE; контракт достаётся максимуму score.
    """

    name = "contract_net"
    label = "контрактная сеть"

    def __init__(self) -> None:
        super().__init__()
        self.open_cfps: dict[str, set[str]] = {}
        self.proposals: dict[str, dict[str, float]] = {}
        self.busy_cooks: set[str] = set()

    def announce_new_orders(self, krabs: Any, env: "KitchenEnvironment") -> None:
        if self.open_cfps:
            return
        candidates = [
            order
            for order in env.orders.values()
            if order.status == OrderStatus.NEW
            and order.announced
            and order.order_id not in self.open_cfps
            and order.order_id not in self.assigned_orders
        ]
        candidates.sort(key=lambda order: (-order.priority, order.created_tick, order.order_id))
        for order in candidates:
            bidders = self._free_cooks(env)
            if not bidders:
                break
            self.open_cfps[order.order_id] = set(bidders)
            self.proposals[order.order_id] = {}
            env.trace.event(
                "cfp_sent",
                tick=env.tick,
                mechanism=self.name,
                order_id=order.order_id,
                bidders=sorted(bidders),
            )
            for cook in bidders:
                krabs.send(
                    Performative.CFP,
                    cook,
                    self._cfp_content(order),
                    conversation_id=self.new_conversation(order),
                )
            break

    def _cfp_content(self, order: Order) -> dict[str, Any]:
        return {
            "action": "cook_order",
            "order_id": order.order_id,
            "priority": order.priority,
            "items": list(order.items),
            "tasks": len(order.tasks),
            "deadline": order.deadline,
            "mechanism": self.name,
        }

    def _free_cooks(self, env: "KitchenEnvironment") -> list[str]:
        return [
            cook
            for cook in self.cook_ids
            if cook in env.agent_ids and cook not in self.busy_cooks
        ]

    def handle(self, krabs: Any, message: Message, env: "KitchenEnvironment") -> bool:
        content = message.content
        action = content.get("action")
        event = content.get("event")

        if message.performative == Performative.PROPOSE and action == "cook_order":
            order_id = content.get("order_id")
            if order_id not in self.open_cfps:
                return True
            score = float(content.get("score", NO_BID))
            proposals = self.proposals.setdefault(order_id, {})
            proposals[message.sender] = score
            env.trace.event(
                "proposal_received",
                tick=env.tick,
                mechanism=self.name,
                order_id=order_id,
                agent=message.sender,
                score=score,
            )
            if set(proposals) >= self.open_cfps[order_id]:
                self._award(krabs, order_id, env)
            return True

        if message.performative == Performative.REFUSE and action == "cook_order":
            order_id = content.get("order_id")
            if order_id in self.open_cfps:
                proposals = self.proposals.setdefault(order_id, {})
                proposals.setdefault(message.sender, NO_BID)
                if set(proposals) >= self.open_cfps[order_id]:
                    self._award(krabs, order_id, env)
            return True

        if message.performative == Performative.AGREE and action == "cook_order":
            order_id = content.get("order_id")
            if order_id in self.assigned_orders:
                return True
            self.open_cfps.pop(order_id, None)
            self.proposals.pop(order_id, None)
            self.busy_cooks.add(message.sender)
            self._assign(order_id, message.sender, env, bid=None)
            return True

        if message.performative == Performative.FAILURE and action == "cook_order":
            order_id = content.get("order_id")
            self.open_cfps.pop(order_id, None)
            self.proposals.pop(order_id, None)
            self.busy_cooks.discard(message.sender)
            env.cancel_order(order_id, content.get("event", "failure"))
            return True

        if message.performative == Performative.INFORM and event == "order_complete":
            self.busy_cooks.discard(message.sender)
            return False

        return False

    def _award(self, krabs: Any, order_id: str, env: "KitchenEnvironment") -> None:
        expected = self.open_cfps.pop(order_id, set())
        proposals = self.proposals.pop(order_id, {})
        bidders = {
            cook: score
            for cook, score in proposals.items()
            if score > NO_BID and cook not in self.busy_cooks
        }
        if not bidders:
            env.trace.event(
                "cfp_failed",
                tick=env.tick,
                mechanism=self.name,
                order_id=order_id,
            )
            for cook in expected:
                krabs.send(
                    Performative.REFUSE,
                    cook,
                    {
                        "action": "cook_order",
                        "order_id": order_id,
                        "reason": "торги не состоялись",
                        "mechanism": self.name,
                    },
                    conversation_id=self.new_conversation_id(order_id),
                )
            return
        winner, score = max(bidders.items(), key=lambda item: (item[1], item[0]))
        for cook in expected:
            conversation = self.new_conversation_id(order_id)
            if cook == winner:
                krabs.send(
                    Performative.ACCEPT,
                    cook,
                    {
                        "action": "cook_order",
                        "order_id": order_id,
                        "score": score,
                        "mechanism": self.name,
                    },
                    conversation_id=conversation,
                )
            elif cook in proposals and proposals[cook] > NO_BID:
                krabs.send(
                    Performative.REFUSE,
                    cook,
                    {
                        "action": "cook_order",
                        "order_id": order_id,
                        "reason": "не лучшая ставка",
                        "mechanism": self.name,
                    },
                    conversation_id=conversation,
                )
        env.trace.event(
            "contract_awarded",
            tick=env.tick,
            mechanism=self.name,
            order_id=order_id,
            agent=winner,
            score=score,
        )
        self.busy_cooks.add(winner)
        self._assign(order_id, winner, env, bid=score)

    @staticmethod
    def new_conversation_id(order_id: str) -> str:
        return f"assign-{order_id}"

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
