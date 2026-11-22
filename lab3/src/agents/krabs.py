"""Mr. Krabs — диспетчер, делегирующий распределение выбранному механизму."""

from __future__ import annotations

from typing import Any

from ..core.agent import Agent
from ..core.message import Performative
from ..domain.models import OrderStatus, StationKind
from ..mechanisms import AssignmentMechanism, CentralDispatchMechanism, get_mechanism


class KrabsAgent(Agent):
    def __init__(
        self,
        agent_id: str,
        bus,
        mechanism: AssignmentMechanism | str | None = None,
    ) -> None:
        super().__init__(agent_id, "диспетчер / владелец", bus)
        if isinstance(mechanism, str) or mechanism is None:
            self.mechanism: AssignmentMechanism = get_mechanism(
                mechanism or CentralDispatchMechanism.name
            )
        else:
            self.mechanism = mechanism
        self.repairing: set[str] = set()
        self.state = "IDLE"
        self.beliefs: dict[str, object] = {}
        self.desires = ("прибыль", "минимальное ожидание", "справедливая загрузка")
        self.intentions: dict[str, str] = {}
        self.assigning_this_tick = False
        self.feedback: list[dict] = []
        self._queue_len = 0
        self._conflict_label = "—"

    @property
    def busy_cooks(self) -> set[str]:
        return getattr(self.mechanism, "busy_cooks", set())

    @property
    def offers(self) -> dict[str, str]:
        return getattr(self.mechanism, "offers", {})

    def step(self, env) -> None:
        self.assigning_this_tick = False
        for message in self.receive():
            self.handle(message, env)
        self.refresh_beliefs(env)
        before = self._pending_assignments()
        self.mechanism.on_tick(self, env)
        if self._pending_assignments() > before:
            self.assigning_this_tick = True
        env.conflict.resolve(self, env)
        self.update_state(env)

    def _pending_assignments(self) -> int:
        mechanism = self.mechanism
        return (
            len(getattr(mechanism, "offers", {}))
            + len(getattr(mechanism, "open_cfps", {}))
            + len(getattr(mechanism, "open_auctions", {}))
        )

    def refresh_beliefs(self, env) -> None:
        self.beliefs["open_orders"] = [
            order.order_id for order in env.orders.values() if order.is_open
        ]
        self.beliefs["busy_cooks"] = sorted(self.busy_cooks)
        self.beliefs["free_stations"] = [
            station.station_id for station in env.stations if station.is_free
        ]
        self.beliefs["mechanism"] = self.mechanism.name

    def update_state(self, env) -> None:
        waiting = [
            order
            for order in env.orders.values()
            if order.status == OrderStatus.NEW and order.announced
        ]
        self._queue_len = len(env.conflict.queue)
        self._conflict_label = env.conflict.label
        previous = self.state
        if self.repairing:
            self.state = "MAINTENANCE"
        elif getattr(env.conflict, "active_episodes", 0):
            self.state = "NEGOTIATING"
        elif self._queue_len:
            self.state = "COORDINATING_STATIONS"
        elif self.assigning_this_tick:
            self.state = "ASSIGNING"
        elif getattr(self.mechanism, "open_cfps", None) or getattr(
            self.mechanism, "open_auctions", None
        ):
            self.state = "AUCTIONING"
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
        busy = self.busy_cooks
        return any(
            cook in env.agent_ids and cook not in busy for cook in ("spongebob", "patrick")
        )

    def handle(self, message, env) -> None:
        if self.mechanism.handle(self, message, env):
            return
        if env.conflict.handle(self, message, env):
            return

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
                env.conflict.release(content.get("station_id"))
            elif event == "station_broken":
                station_id = content.get("station_id")
                env.conflict.release(station_id)
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
                order = env.orders.get(record["order_id"])
                if order is not None and order.assignee:
                    env.conflict.adjust(
                        order.assignee,
                        0.02 if record["served"] else -0.05,
                        env,
                        "feedback",
                    )
                env.trace.event("feedback_received", tick=env.tick, **record)

        elif message.performative == Performative.REQUEST:
            action = content.get("action")
            if action == "station":
                env.conflict.submit(content, message.sender, env.tick)
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

    def describe(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "state": self.state,
            "detail": (
                f"механизм: {self.mechanism.label}; "
                f"конфликт: {self._conflict_label}; "
                f"заняты: {', '.join(sorted(self.busy_cooks)) or '—'}; "
                f"очередь станций: {self._queue_len}"
            ),
        }
