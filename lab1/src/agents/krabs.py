"""Mr. Krabs — центральный диспетчер."""

from __future__ import annotations

from ..core.agent import Agent
from ..core.message import Performative
from ..domain.models import OrderStatus, StationKind
from ..mechanisms.central_dispatch import CentralDispatcher


class KrabsAgent(Agent):
    def __init__(self, agent_id: str, bus) -> None:
        super().__init__(agent_id, "диспетчер / владелец", bus)
        self.dispatcher = CentralDispatcher()
        self.offers: dict[str, str] = {}
        self.offered_cooks: set[str] = set()
        self.busy_cooks: set[str] = set()
        self.reserved_stations: set[str] = set()
        self.station_queue: list[dict] = []
        self.repairing: set[str] = set()
        self.state = "IDLE"
        self.beliefs: dict[str, object] = {}
        self.desires = ("прибыль", "минимальное ожидание", "справедливая загрузка")
        self.intentions: dict[str, str] = self.offers
        self.assigning_this_tick = False
        self.feedback: list[dict] = []

    def step(self, env) -> None:
        self.assigning_this_tick = False
        for message in self.receive():
            self.handle(message, env)
        self.refresh_beliefs(env)
        self.assign_orders(env)
        self.grant_stations(env)
        self.update_state(env)

    def refresh_beliefs(self, env) -> None:
        self.beliefs["open_orders"] = [
            order.order_id for order in env.orders.values() if order.is_open
        ]
        self.beliefs["busy_cooks"] = sorted(self.busy_cooks)
        self.beliefs["free_stations"] = [
            station.station_id for station in env.stations if station.is_free
        ]

    def update_state(self, env) -> None:
        waiting = [
            order
            for order in env.orders.values()
            if order.status == OrderStatus.NEW and order.announced
        ]
        previous = self.state
        if self.repairing:
            self.state = "MAINTENANCE"
        elif self.station_queue:
            self.state = "COORDINATING_STATIONS"
        elif self.assigning_this_tick:
            self.state = "ASSIGNING"
        elif self.offers:
            self.state = "AWAITING_ACCEPT"
        elif waiting and not self.has_available_cook(env):
            self.state = "ARBITRATING"
        else:
            self.state = "IDLE"
        if self.state == "ARBITRATING" and previous != "ARBITRATING":
            env.trace.event(
                "arbitration_started",
                tick=env.tick,
                waiting_orders=[order.order_id for order in waiting],
            )

    def has_available_cook(self, env) -> bool:
        return any(
            cook in env.agent_ids
            and cook not in self.busy_cooks
            and cook not in self.offered_cooks
            for cook in self.dispatcher.cook_priority
        )

    def handle(self, message, env) -> None:
        content = message.content
        event = content.get("event")

        if message.performative == Performative.INFORM:
            if event == "order_new":
                env.trace.event(
                    "order_announced_to_krabs",
                    tick=env.tick,
                    order_id=content.get("order_id"),
                    sender=message.sender,
                )
            elif event == "order_complete":
                order_id = content.get("order_id")
                order = env.orders.get(order_id)
                if order is not None:
                    order.status = OrderStatus.COMPLETED
                self.busy_cooks.discard(message.sender)
                env.trace.event(
                    "order_completed",
                    tick=env.tick,
                    order_id=order_id,
                    agent=message.sender,
                )
                self.send(
                    Performative.INFORM,
                    "squidward",
                    {"event": "serve_order", "order_id": order_id},
                    conversation_id=message.conversation_id,
                )
            elif event == "step_done":
                env.trace.event(
                    "step_done",
                    tick=env.tick,
                    order_id=content.get("order_id"),
                    task_index=content.get("task_index"),
                    agent=message.sender,
                )
            elif event == "station_released":
                self.reserved_stations.discard(content.get("station_id"))
            elif event == "station_broken":
                station_id = content.get("station_id")
                self.reserved_stations.discard(station_id)
                if station_id not in self.repairing:
                    self.repairing.add(station_id)
                    self.send(
                        Performative.REQUEST,
                        "sandy",
                        {"action": "repair", "station_id": station_id},
                        conversation_id=f"repair-{station_id}",
                    )
            elif event == "repair_done":
                self.repairing.discard(content.get("station_id"))
            elif event == "served":
                env.trace.event(
                    "order_confirmed_served",
                    tick=env.tick,
                    order_id=content.get("order_id"),
                )
            elif event == "feedback":
                record = {
                    "order_id": content.get("order_id"),
                    "served": content.get("served"),
                    "rating": content.get("rating"),
                }
                self.feedback.append(record)
                env.trace.event("feedback_received", tick=env.tick, **record)

        elif message.performative == Performative.AGREE:
            if content.get("action") == "cook_order":
                order_id = content.get("order_id")
                cook = message.sender
                self.offers.pop(order_id, None)
                self.offered_cooks.discard(cook)
                self.busy_cooks.add(cook)
                order = env.orders.get(order_id)
                if order is not None:
                    order.status = OrderStatus.ASSIGNED
                    order.assignee = cook
                env.trace.event(
                    "order_assigned",
                    tick=env.tick,
                    order_id=order_id,
                    agent=cook,
                )

        elif message.performative == Performative.REFUSE:
            if content.get("action") == "cook_order":
                order_id = content.get("order_id")
                self.offers.pop(order_id, None)
                self.offered_cooks.discard(message.sender)
            elif content.get("action") == "repair":
                self.repairing.discard(content.get("station_id"))

        elif message.performative == Performative.FAILURE:
            order_id = content.get("order_id")
            self.busy_cooks.discard(message.sender)
            env.cancel_order(order_id, content.get("event", "failure"))

        elif message.performative == Performative.REQUEST:
            action = content.get("action")
            if action == "station":
                self.station_queue.append(dict(content, agent=message.sender))
            elif action == "external":
                env.trace.event(
                    "external_request_refused",
                    tick=env.tick,
                    agent=self.id,
                    sender=message.sender,
                )
                self.send(
                    Performative.REFUSE,
                    message.sender,
                    {"event": "external_request_denied", "reason": "нет полномочий"},
                    conversation_id=message.conversation_id,
                )

    def assign_orders(self, env) -> None:
        candidates = [
            order
            for order in env.orders.values()
            if order.status == OrderStatus.NEW
            and order.announced
            and order.order_id not in self.offers
        ]
        candidates.sort(key=lambda order: (-order.priority, order.created_tick, order.order_id))
        for order in candidates:
            available = [
                cook
                for cook in self.dispatcher.cook_priority
                if cook in env.agent_ids
                and cook not in self.busy_cooks
                and cook not in self.offered_cooks
            ]
            cook = self.dispatcher.choose_cook(available)
            if cook is None:
                break
            self.offers[order.order_id] = cook
            self.offered_cooks.add(cook)
            self.assigning_this_tick = True
            env.trace.event(
                "order_offered",
                tick=env.tick,
                order_id=order.order_id,
                agent=cook,
            )
            self.send(
                Performative.REQUEST,
                cook,
                {
                    "action": "cook_order",
                    "order_id": order.order_id,
                    "priority": order.priority,
                },
                conversation_id=f"order-{order.order_id}",
            )

    def grant_stations(self, env) -> None:
        remaining: list[dict] = []
        for request in self.station_queue:
            order = env.orders.get(request.get("order_id"))
            if order is None or order.status in (
                OrderStatus.COMPLETED,
                OrderStatus.SERVED,
                OrderStatus.CANCELLED,
            ):
                continue
            kind = StationKind(request["station_kind"])
            station = self.dispatcher.choose_station(
                env.stations, kind, self.reserved_stations
            )
            if station is None:
                remaining.append(request)
                continue
            self.reserved_stations.add(station.station_id)
            self.send(
                Performative.AGREE,
                request["agent"],
                {
                    "event": "station_granted",
                    "station_id": station.station_id,
                    "order_id": request.get("order_id"),
                    "task_index": request.get("task_index"),
                },
                conversation_id=f"order-{request.get('order_id')}",
            )
        self.station_queue = remaining

    def describe(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "state": self.state,
            "detail": (
                f"заняты: {', '.join(sorted(self.busy_cooks)) or '—'}; "
                f"очередь станций: {len(self.station_queue)}"
            ),
        }
