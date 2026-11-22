"""Сбор и расчёт показателей эффективности, координации и справедливости."""

from __future__ import annotations

from collections import Counter
from statistics import mean


def gini(values: list[float]) -> float:
    if not values or sum(values) == 0:
        return 0.0
    ordered = sorted(values)
    count = len(ordered)
    cumulative = sum((index + 1) * value for index, value in enumerate(ordered))
    return (2 * cumulative) / (count * sum(ordered)) - (count + 1) / count


def jain(values: list[float]) -> float:
    if not values:
        return 0.0
    total = sum(values)
    squares = sum(value * value for value in values)
    if squares == 0:
        return 0.0
    return (total * total) / (len(values) * squares)


COORDINATION_PERFORMATIVES = frozenset({"cfp", "propose", "accept", "refuse"})


def is_coordination_message(message) -> bool:
    """Сообщение протокола распределения задач (а не станций/ремонта)."""
    if message.performative.value in COORDINATION_PERFORMATIVES:
        action = message.content.get("action")
        if message.performative.value in ("cfp", "propose"):
            return True
        return action == "cook_order"
    if message.performative.value in ("request", "agree"):
        return message.content.get("action") == "cook_order"
    return False


class MetricsCollector:
    """Считает метрики по текущему состоянию среды."""

    def __init__(self, env) -> None:
        self.env = env

    def snapshot(self) -> dict:
        env = self.env
        orders = list(env.orders.values())
        served = [order for order in orders if order.served_tick is not None]
        waits = [order.served_tick - order.created_tick for order in served]
        assigned = [order for order in orders if order.assigned_tick is not None]
        latencies = [order.assigned_tick - order.created_tick for order in assigned]
        makespan = 0
        if served:
            makespan = max(order.served_tick for order in served) - min(
                order.created_tick for order in orders
            )
        statuses = Counter(order.status.value for order in orders)
        performatives = Counter(message.performative.value for message in env.bus.history)
        pairs = Counter((message.sender, message.receiver) for message in env.bus.history)
        workload_values = [float(value) for value in env.workload.values()]
        coordination_messages = sum(
            1 for message in env.bus.history if is_coordination_message(message)
        )
        served_count = len(served)
        utilization = {
            station.station_id: round(
                env.station_busy_ticks[station.station_id] / max(1, env.tick), 3
            )
            for station in env.stations
        }
        elapsed = max(1, env.tick)
        return {
            "mechanism": env.mechanism,
            "mechanism_label": env.mechanism_label,
            "orders_total": len(orders),
            "orders_served": served_count,
            "orders_cancelled": statuses.get("cancelled", 0),
            "orders_open": sum(
                1
                for order in orders
                if order.status.value not in ("served", "cancelled")
            ),
            "statuses": dict(statuses),
            "makespan": makespan,
            "avg_wait": round(mean(waits), 2) if waits else 0.0,
            "max_wait": max(waits) if waits else 0,
            "late_orders": sum(1 for order in served if order.served_tick > order.deadline),
            "throughput": round(served_count / elapsed, 3),
            "ticks": env.tick,
            "messages_total": len(env.bus.history),
            "messages_by_performative": dict(performatives),
            "messages_by_pair": {
                f"{sender}->{receiver}": count for (sender, receiver), count in pairs.items()
            },
            "coordination_messages": coordination_messages,
            "coordination_cost": (
                round(coordination_messages / served_count, 2) if served_count else 0.0
            ),
            "assignment_latency_avg": round(mean(latencies), 2) if latencies else 0.0,
            "assignment_latency_max": max(latencies) if latencies else 0,
            "coordination_spend": round(env.coordination_spend, 2),
            "station_utilization": utilization,
            "workload": dict(env.workload),
            "tasks_completed": env.tasks_completed,
            "gini_workload": round(gini(workload_values), 3),
            "jain_workload": round(jain(workload_values), 3),
            "revenue": env.revenue,
            "tips": env.tips,
            "treasury": env.treasury,
        }
