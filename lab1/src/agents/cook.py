"""Повара: SpongeBob и Patrick."""

from __future__ import annotations

import math

from ..core.agent import Agent
from ..core.message import Performative
from ..domain.models import OrderStatus


class CookAgent(Agent):
    def __init__(self, agent_id: str, role: str, bus, skill: float) -> None:
        super().__init__(agent_id, role, bus)
        self.skill = skill
        self.order_id: str | None = None
        self.task_index = 0
        self.station_id: str | None = None
        self.busy_until = 0
        self.current_duration = 0
        self.waiting_kind = None
        self.state = "IDLE"
        self.reporting_complete = False

    def step(self, env) -> None:
        for message in self.receive():
            self.handle(message, env)
        if self.state == "REPORTING":
            self.finish_reporting()
            return
        if self.order_id is None:
            self.state = "IDLE"
            return
        order = env.orders.get(self.order_id)
        if order is None or order.status in (
            OrderStatus.CANCELLED,
            OrderStatus.SERVED,
            OrderStatus.COMPLETED,
        ):
            self.reset()
            return
        if self.state == "COOKING":
            if env.tick >= self.busy_until:
                self.finish_task(env)
            return
        if self.state == "ASSIGNED":
            self.request_station(env)

    def finish_reporting(self) -> None:
        if self.reporting_complete:
            self.reset()
            return
        self.reporting_complete = False
        self.state = "ASSIGNED"

    def handle(self, message, env) -> None:
        content = message.content
        if message.performative == Performative.REQUEST and content.get("action") == "cook_order":
            if self.order_id is None:
                self.order_id = content["order_id"]
                self.task_index = 0
                self.state = "ASSIGNED"
                env.trace.event(
                    "order_accepted",
                    tick=env.tick,
                    order_id=self.order_id,
                    agent=self.id,
                )
                self.send(
                    Performative.AGREE,
                    "krabs",
                    {"action": "cook_order", "order_id": self.order_id},
                    conversation_id=message.conversation_id,
                )
            else:
                self.send(
                    Performative.REFUSE,
                    "krabs",
                    {"action": "cook_order", "order_id": content.get("order_id")},
                    conversation_id=message.conversation_id,
                )
        elif message.performative == Performative.AGREE and content.get("event") == "station_granted":
            if (
                self.order_id == content.get("order_id")
                and self.state == "WAITING_STATION"
            ):
                self.start_task(env, content)
        elif message.performative == Performative.REFUSE:
            if self.state == "WAITING_STATION":
                self.state = "ASSIGNED"

    def request_station(self, env) -> None:
        order = env.orders.get(self.order_id)
        if order is None:
            self.reset()
            return
        if self.task_index >= len(order.tasks):
            self.complete_order(env, order)
            return
        task = order.tasks[self.task_index]
        self.waiting_kind = task.kind
        self.state = "WAITING_STATION"
        self.send(
            Performative.REQUEST,
            "krabs",
            {
                "action": "station",
                "station_kind": task.kind.value,
                "order_id": order.order_id,
                "task_index": self.task_index,
            },
            conversation_id=f"order-{order.order_id}",
        )

    def start_task(self, env, content) -> None:
        order = env.orders.get(self.order_id)
        if order is None:
            self.reset()
            return
        task_index = int(content.get("task_index", self.task_index))
        if task_index >= len(order.tasks):
            self.complete_order(env, order)
            return
        task = order.tasks[task_index]
        if not env.inventory.has(task.ingredients):
            self.send(
                Performative.INFORM,
                "krabs",
                {"event": "station_released", "station_id": content["station_id"]},
                conversation_id=f"order-{order.order_id}",
            )
            self.send(
                Performative.FAILURE,
                "krabs",
                {
                    "action": "cook_order",
                    "event": "ingredients_missing",
                    "order_id": order.order_id,
                },
                conversation_id=f"order-{order.order_id}",
            )
            env.cancel_order(order.order_id, "ingredients_missing")
            self.reset()
            return
        duration = max(1, math.ceil(task.duration * self.skill))
        station_id = content["station_id"]
        if not env.begin_task(station_id, self.id, duration):
            self.send(
                Performative.INFORM,
                "krabs",
                {"event": "station_released", "station_id": station_id},
                conversation_id=f"order-{order.order_id}",
            )
            self.state = "ASSIGNED"
            return
        env.inventory.consume(task.ingredients)
        self.station_id = station_id
        self.current_duration = duration
        self.busy_until = env.tick + duration
        self.state = "COOKING"
        order.status = OrderStatus.IN_PROGRESS
        env.trace.event(
            "cook_task_started",
            tick=env.tick,
            order_id=order.order_id,
            agent=self.id,
            station_id=station_id,
            task=task.label,
            duration=duration,
        )

    def finish_task(self, env) -> None:
        order = env.orders.get(self.order_id)
        if order is None or self.station_id is None:
            self.reset()
            return
        env.finish_task(self.station_id, self.id)
        env.record_work(self.id, self.current_duration)
        self.send(
            Performative.INFORM,
            "krabs",
            {"event": "station_released", "station_id": self.station_id},
            conversation_id=f"order-{order.order_id}",
        )
        self.send(
            Performative.INFORM,
            "krabs",
            {
                "event": "step_done",
                "order_id": order.order_id,
                "task_index": self.task_index,
            },
            conversation_id=f"order-{order.order_id}",
        )
        self.task_index += 1
        self.station_id = None
        self.busy_until = 0
        self.current_duration = 0
        self.waiting_kind = None
        if self.task_index >= len(order.tasks):
            self.complete_order(env, order)
            return
        self.state = "REPORTING"
        self.reporting_complete = False

    def complete_order(self, env, order) -> None:
        order.status = OrderStatus.COMPLETED
        env.trace.event(
            "order_completed_by_cook",
            tick=env.tick,
            order_id=order.order_id,
            agent=self.id,
        )
        self.send(
            Performative.INFORM,
            "krabs",
            {"event": "order_complete", "order_id": order.order_id},
            conversation_id=f"order-{order.order_id}",
        )
        self.station_id = None
        self.busy_until = 0
        self.current_duration = 0
        self.waiting_kind = None
        self.state = "REPORTING"
        self.reporting_complete = True

    def reset(self) -> None:
        self.order_id = None
        self.task_index = 0
        self.station_id = None
        self.busy_until = 0
        self.current_duration = 0
        self.waiting_kind = None
        self.state = "IDLE"
        self.reporting_complete = False

    def describe(self) -> dict:
        detail = ""
        if self.order_id is not None:
            detail = f"заказ {self.order_id}, шаг {self.task_index + 1}"
        return {"id": self.id, "role": self.role, "state": self.state, "detail": detail}


class SpongeBobAgent(CookAgent):
    def __init__(self, agent_id: str, bus) -> None:
        super().__init__(agent_id, "повар-универсал", bus, 1.0)


class PatrickAgent(CookAgent):
    def __init__(self, agent_id: str, bus) -> None:
        super().__init__(agent_id, "второй повар", bus, 1.4)
