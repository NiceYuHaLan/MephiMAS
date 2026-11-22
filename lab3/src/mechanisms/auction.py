"""Аукцион: повара называют цены, Krabs присуждает заказ минимальной ставке.

Реализован sealed-bid аукцион Викри: побеждает минимальная цена,
платёж равен второй по величине ставке (экономическая стоимость координации).
"""

from __future__ import annotations

from typing import Any

from ..core.message import Message, Performative
from ..domain.kitchen import KitchenEnvironment
from ..domain.models import Order, OrderStatus
from .base import AssignmentMechanism

NO_BID = float("inf")


class AuctionMechanism(AssignmentMechanism):
    """Аукцион с секретными ставками и платежом по второй цене."""

    name = "auction"
    label = "аукцион (Викри)"

    def __init__(self) -> None:
        super().__init__()
        self.open_auctions: dict[str, set[str]] = {}
        self.bids: dict[str, dict[str, float]] = {}
        self.busy_cooks: set[str] = set()

    def announce_new_orders(self, krabs: Any, env: "KitchenEnvironment") -> None:
        if self.open_auctions:
            return
        candidates = [
            order
            for order in env.orders.values()
            if order.status == OrderStatus.NEW
            and order.announced
            and order.order_id not in self.open_auctions
            and order.order_id not in self.assigned_orders
        ]
        candidates.sort(key=lambda order: (-order.priority, order.created_tick, order.order_id))
        for order in candidates:
            bidders = self._free_cooks(env)
            if not bidders:
                break
            self.open_auctions[order.order_id] = set(bidders)
            self.bids[order.order_id] = {}
            env.trace.event(
                "auction_opened",
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
                    conversation_id=f"auction-{order.order_id}",
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
            "auction": "vickrey",
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
            if order_id not in self.open_auctions:
                return True
            price = float(content.get("price", NO_BID))
            bids = self.bids.setdefault(order_id, {})
            bids[message.sender] = price
            env.trace.event(
                "bid_received",
                tick=env.tick,
                mechanism=self.name,
                order_id=order_id,
                agent=message.sender,
                price=price,
            )
            if set(bids) >= self.open_auctions[order_id]:
                self._settle(krabs, order_id, env)
            return True

        if message.performative == Performative.REFUSE and action == "cook_order":
            order_id = content.get("order_id")
            if order_id in self.open_auctions:
                bids = self.bids.setdefault(order_id, {})
                bids.setdefault(message.sender, NO_BID)
                if set(bids) >= self.open_auctions[order_id]:
                    self._settle(krabs, order_id, env)
            return True

        if message.performative == Performative.AGREE and action == "cook_order":
            order_id = content.get("order_id")
            if order_id in self.assigned_orders:
                return True
            payment = float(content.get("payment", 0.0))
            self.open_auctions.pop(order_id, None)
            self.bids.pop(order_id, None)
            self.busy_cooks.add(message.sender)
            self._assign(order_id, message.sender, env, bid=payment)
            return True

        if message.performative == Performative.FAILURE and action == "cook_order":
            order_id = content.get("order_id")
            self.open_auctions.pop(order_id, None)
            self.bids.pop(order_id, None)
            self.busy_cooks.discard(message.sender)
            env.cancel_order(order_id, content.get("event", "failure"))
            return True

        if message.performative == Performative.INFORM and event == "order_complete":
            self.busy_cooks.discard(message.sender)
            return False

        return False

    def _settle(self, krabs: Any, order_id: str, env: "KitchenEnvironment") -> None:
        expected = self.open_auctions.pop(order_id, set())
        bids = self.bids.pop(order_id, {})
        active = {
            cook: price
            for cook, price in bids.items()
            if price < NO_BID and cook not in self.busy_cooks
        }
        if not active:
            env.trace.event(
                "auction_failed",
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
                        "reason": "аукцион не состоялся",
                        "mechanism": self.name,
                    },
                    conversation_id=f"auction-{order_id}",
                )
            return
        ranked = sorted(active.items(), key=lambda item: (item[1], item[0]))
        winner, winning_price = ranked[0]
        payment = ranked[1][1] if len(ranked) > 1 else winning_price
        for cook in expected:
            conversation = f"auction-{order_id}"
            if cook == winner:
                krabs.send(
                    Performative.ACCEPT,
                    cook,
                    {
                        "action": "cook_order",
                        "order_id": order_id,
                        "price": winning_price,
                        "payment": payment,
                        "mechanism": self.name,
                    },
                    conversation_id=conversation,
                )
            elif cook in bids and bids[cook] < NO_BID:
                krabs.send(
                    Performative.REFUSE,
                    cook,
                    {
                        "action": "cook_order",
                        "order_id": order_id,
                        "reason": "ставка выше минимальной",
                        "mechanism": self.name,
                    },
                    conversation_id=conversation,
                )
        env.trace.event(
            "auction_settled",
            tick=env.tick,
            mechanism=self.name,
            order_id=order_id,
            agent=winner,
            price=winning_price,
            payment=payment,
        )
        self.busy_cooks.add(winner)
        self._assign(order_id, winner, env, bid=payment)

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
            env.coordination_spend += bid
        self.assigned_orders[order_id] = cook
        env.trace.event(
            "order_assigned",
            tick=env.tick,
            mechanism=self.name,
            order_id=order_id,
            agent=cook,
            bid=bid,
        )
