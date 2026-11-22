"""Дискретная среда кухни ресторана."""

from __future__ import annotations

from collections import Counter
from typing import Callable

from ..core.agent import Agent
from ..core.bus import MessageBus
from ..core.message import Performative
from ..core.trace import TraceRecorder
from ..metrics.collector import MetricsCollector
from ..scenarios.models import BreakdownSpec, Scenario
from .models import (
    DISH_LABELS,
    Order,
    OrderStatus,
    Station,
    StationKind,
    Inventory,
    build_order_tasks,
)


class KitchenEnvironment:
    """Среда с заказами, станциями, инвентарём и шиной сообщений."""

    def __init__(self, scenario: Scenario, trace: TraceRecorder | None = None) -> None:
        self.scenario = scenario
        self.trace = trace or TraceRecorder()
        self.bus = MessageBus(self.trace)
        self.bus.register("environment")
        self.tick = 0
        self.orders: dict[str, Order] = {}
        self.stations = [
            Station("grill-1", StationKind.GRILL),
            Station("fryer-1", StationKind.FRYER),
            Station("soda-1", StationKind.SODA),
            Station("assembly-1", StationKind.ASSEMBLY),
        ]
        self.inventory = Inventory(
            {
                "patty": 24,
                "bun": 24,
                "lettuce": 24,
                "coral_bits": 24,
                "kelp": 24,
                "sausage": 16,
            }
        )
        self.agents: list[Agent] = []
        self.agent_ids: set[str] = set()
        self.treasury = 100
        self.revenue = 0
        self.tips = 0
        self.workload: Counter[str] = Counter()
        self.station_busy_ticks: Counter[str] = Counter()
        self.tasks_completed = 0
        self.coordination_spend = 0.0
        self.mechanism = "central"
        self.mechanism_label = "централизованная диспетчеризация"
        self._order_schedule = sorted(scenario.orders, key=lambda item: item.tick)
        self._breakdown_schedule = sorted(scenario.breakdowns, key=lambda item: item.tick)
        self._order_index = 0
        self._breakdown_index = 0
        self.finished = False
        self.metrics = MetricsCollector(self)

    def add_agent(self, agent: Agent) -> None:
        self.bus.register(agent.id)
        self.agents.append(agent)
        self.agent_ids.add(agent.id)

    def create_order(self, spec) -> Order:
        order_id = f"O-{len(self.orders) + 1:03d}"
        tasks, price = build_order_tasks(list(spec.items))
        order = Order(
            order_id=order_id,
            customer=spec.customer,
            table=spec.table,
            items=list(spec.items),
            created_tick=self.tick,
            deadline=self.tick + spec.patience,
            priority=spec.priority,
            tasks=tasks,
            price=price,
        )
        self.orders[order_id] = order
        self.trace.event(
            "order_created",
            tick=self.tick,
            order_id=order_id,
            customer=spec.customer,
            items=list(spec.items),
            price=price,
            deadline=order.deadline,
        )
        return order

    def begin_task(self, station_id: str, agent_id: str, duration: int) -> bool:
        station = self.station_by_id(station_id)
        if station is None or station.broken or station.occupant is not None:
            return False
        station.occupant = agent_id
        station.busy_until = self.tick + duration
        self.station_busy_ticks[station_id] += duration
        self.trace.event(
            "task_started",
            tick=self.tick,
            station_id=station_id,
            agent=agent_id,
            duration=duration,
        )
        return True

    def finish_task(self, station_id: str, agent_id: str) -> bool:
        station = self.station_by_id(station_id)
        if station is None or station.occupant != agent_id:
            return False
        station.occupant = None
        station.busy_until = 0
        self.trace.event("task_finished", tick=self.tick, station_id=station_id, agent=agent_id)
        return True

    def record_work(self, agent_id: str, duration: int) -> None:
        self.workload[agent_id] += duration
        self.tasks_completed += 1

    def station_by_id(self, station_id: str) -> Station | None:
        for station in self.stations:
            if station.station_id == station_id:
                return station
        return None

    def serve_order(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if order is None or order.status != OrderStatus.COMPLETED:
            return False
        order.status = OrderStatus.SERVED
        order.served_tick = self.tick
        late = self.tick > order.deadline
        order.tip = round(order.price * (0.05 if late else 0.15))
        self.revenue += order.price
        self.tips += order.tip
        self.treasury += order.price + order.tip
        self.trace.event(
            "order_served",
            tick=self.tick,
            order_id=order_id,
            wait=self.tick - order.created_tick,
            late=late,
            tip=order.tip,
        )
        return True

    def cancel_order(self, order_id: str, reason: str = "") -> None:
        order = self.orders.get(order_id)
        if order is None or not order.is_open:
            return
        order.status = OrderStatus.CANCELLED
        self.trace.event("order_cancelled", tick=self.tick, order_id=order_id, reason=reason)

    def trigger_breakdown(self, spec: BreakdownSpec) -> None:
        station = self.station_by_id(spec.station_id)
        if station is None or station.broken:
            return
        station.broken = True
        self.trace.event("station_broken", tick=self.tick, station_id=spec.station_id)
        self.bus.send(
            Performative.INFORM,
            "environment",
            "krabs",
            {"event": "station_broken", "station_id": spec.station_id},
            conversation_id=f"repair-{spec.station_id}",
        )

    def repair_station(self, station_id: str) -> bool:
        station = self.station_by_id(station_id)
        if station is None or not station.broken:
            return False
        station.broken = False
        self.trace.event("station_repaired", tick=self.tick, station_id=station_id)
        return True

    def step(self) -> None:
        if self.finished:
            return
        self.bus.tick = self.tick
        while (
            self._order_index < len(self._order_schedule)
            and self._order_schedule[self._order_index].tick <= self.tick
        ):
            self.create_order(self._order_schedule[self._order_index])
            self._order_index += 1
        while (
            self._breakdown_index < len(self._breakdown_schedule)
            and self._breakdown_schedule[self._breakdown_index].tick <= self.tick
        ):
            self.trigger_breakdown(self._breakdown_schedule[self._breakdown_index])
            self._breakdown_index += 1

        for agent in self.agents:
            agent.inbox.extend(self.bus.drain(agent.id))
        for agent in self.agents:
            agent.step(self)

        self.tick += 1
        if self.is_done():
            self.finished = True
        self.trace.event(
            "tick",
            tick=self.tick,
            orders=len(self.orders),
            served=sum(1 for order in self.orders.values() if order.status == OrderStatus.SERVED),
            messages=len(self.bus.history),
        )

    def is_done(self) -> bool:
        if self._order_index < len(self._order_schedule):
            return False
        return all(
            order.status in (OrderStatus.SERVED, OrderStatus.CANCELLED)
            for order in self.orders.values()
        )

    def run(
        self,
        max_ticks: int | None = None,
        on_tick: Callable[["KitchenEnvironment"], None] | None = None,
    ) -> dict:
        limit = max_ticks or self.scenario.max_ticks
        while self.tick < limit and not self.finished:
            self.step()
            if on_tick is not None:
                on_tick(self)
        if not self.finished:
            self.trace.event("run_limit_reached", tick=self.tick)
        return self.metrics.snapshot()

    def snapshot(self) -> dict:
        orders = []
        for order in sorted(self.orders.values(), key=lambda item: item.order_id):
            reference_tick = order.served_tick if order.served_tick is not None else self.tick
            orders.append(
                {
                    "id": order.order_id,
                    "customer": order.customer,
                    "table": order.table,
                    "items": [DISH_LABELS.get(item, item) for item in order.items],
                    "status": order.status.value,
                    "status_label": order.status.label,
                    "created": order.created_tick,
                    "deadline": order.deadline,
                    "wait": max(0, reference_tick - order.created_tick),
                    "price": order.price,
                    "tip": order.tip,
                    "assignee": order.assignee,
                    "priority": order.priority,
                }
            )
        stations = [
            {
                "id": station.station_id,
                "kind": station.kind.value,
                "kind_label": station.kind.label,
                "occupant": station.occupant,
                "busy_until": station.busy_until,
                "broken": station.broken,
            }
            for station in self.stations
        ]
        return {
            "scenario": {
                "name": self.scenario.name,
                "title": self.scenario.title,
                "description": self.scenario.description,
            },
            "mechanism": {"name": self.mechanism, "label": self.mechanism_label},
            "tick": self.tick,
            "finished": self.finished,
            "orders": orders,
            "stations": stations,
            "agents": [agent.describe() for agent in self.agents],
            "inventory": self.inventory.levels(),
            "metrics": self.metrics.snapshot(),
            "messages": [message.to_dict() for message in self.bus.history[-40:]],
        }
