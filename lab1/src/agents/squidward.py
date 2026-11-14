"""Squidward — приём и выдача заказов."""

from __future__ import annotations

from ..core.agent import Agent
from ..core.message import Performative
from ..domain.models import OrderStatus


class SquidwardAgent(Agent):
    def __init__(self, agent_id: str, bus) -> None:
        super().__init__(agent_id, "кассир / приём заказов", bus)
        self.state = "IDLE"
        self.beliefs: dict[str, object] = {}
        self.desires = ("обслужить вовремя", "точно принять заказ")
        self.intentions: list[str] = []
        self.pending_serve: list[tuple[str, int]] = []
        self.served_this_tick = False
        self.announced_this_tick = False

    def step(self, env) -> None:
        self.served_this_tick = False
        self.announced_this_tick = False
        for message in self.receive():
            self.handle(message, env)
        for order in sorted(
            env.orders.values(), key=lambda item: (item.created_tick, item.order_id)
        ):
            if order.status == OrderStatus.NEW and not order.announced:
                order.announced = True
                self.announced_this_tick = True
                self.intentions.append(order.order_id)
                env.trace.event(
                    "order_announced",
                    tick=env.tick,
                    order_id=order.order_id,
                    agent=self.id,
                )
                self.send(
                    Performative.INFORM,
                    "krabs",
                    {"event": "order_new", "order_id": order.order_id},
                    conversation_id=f"order-{order.order_id}",
                )
        self.serve_pending(env)
        self.refresh_beliefs(env)
        if self.served_this_tick:
            self.state = "SERVING"
        elif self.announced_this_tick:
            self.state = "TAKING_ORDER"
        elif self.pending_serve or any(
            order.status == OrderStatus.COMPLETED for order in env.orders.values()
        ):
            self.state = "WAITING_SERVE"
        else:
            self.state = "IDLE"

    def refresh_beliefs(self, env) -> None:
        self.beliefs["open_orders"] = [
            order.order_id for order in env.orders.values() if order.is_open
        ]
        self.beliefs["pending_serve"] = [
            order_id for order_id, _ in self.pending_serve
        ]

    def handle(self, message, env) -> None:
        if (
            message.performative == Performative.INFORM
            and message.content.get("event") == "serve_order"
        ):
            order_id = message.content.get("order_id")
            if all(existing != order_id for existing, _ in self.pending_serve):
                self.pending_serve.append((order_id, env.tick))
            self.state = "WAITING_SERVE"

    def serve_pending(self, env) -> None:
        if not self.pending_serve:
            return
        order_id, arrived = self.pending_serve[0]
        if arrived >= env.tick:
            return
        self.pending_serve.pop(0)
        order = env.orders.get(order_id)
        served = env.serve_order(order_id)
        rating = 1 if served else 0
        env.trace.event(
            "serve_attempt",
            tick=env.tick,
            order_id=order_id,
            served=served,
            agent=self.id,
        )
        self.send(
            Performative.INFORM,
            "krabs",
            {"event": "served", "order_id": order_id, "served": served},
            conversation_id=f"order-{order_id}",
        )
        env.trace.event(
            "feedback_collected",
            tick=env.tick,
            order_id=order_id,
            served=served,
            rating=rating,
            agent=self.id,
        )
        self.send(
            Performative.INFORM,
            "krabs",
            {
                "event": "feedback",
                "order_id": order_id,
                "served": served,
                "rating": rating,
                "tip": order.tip if order is not None else 0,
            },
            conversation_id=f"feedback-{order_id}",
        )
        if order_id in self.intentions:
            self.intentions.remove(order_id)
        self.served_this_tick = True

    def describe(self) -> dict:
        detail = "принимает заказы и выдаёт готовые блюда"
        if self.pending_serve:
            detail = f"ожидают подачи: {len(self.pending_serve)}"
        return {
            "id": self.id,
            "role": self.role,
            "state": self.state,
            "detail": detail,
        }
