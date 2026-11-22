"""Непротиворечивость: сообщение должно соответствовать состоянию заказа."""

from __future__ import annotations

from ...domain.models import OrderStatus
from ..base import Guard, Verdict

ACTIVE = {OrderStatus.ASSIGNED, OrderStatus.IN_PROGRESS, OrderStatus.COMPLETED}


class ConsistencyGuard(Guard):
    name = "consistency"
    label = "согласованность состояний"

    def check(self, message, env) -> Verdict:
        content = message.content
        performative = message.performative.value
        action = content.get("action")
        event = content.get("event")

        if performative in ("request", "cfp") and action == "cook_order":
            order = env.orders.get(content.get("order_id"))
            if order is None:
                return Verdict.deny("consistency", "заказ не существует")
            if order.status != OrderStatus.NEW and order.assignee != message.receiver:
                return Verdict.deny(
                    "consistency",
                    f"заказ {order.order_id} уже в состоянии {order.status.value}",
                )

        if performative == "inform" and event == "order_complete":
            order = env.orders.get(content.get("order_id"))
            if order is None:
                return Verdict.deny("consistency", "заказ не существует")
            if order.status not in ACTIVE:
                return Verdict.deny(
                    "consistency",
                    f"нельзя завершить заказ в состоянии {order.status.value}",
                )

        if performative == "inform" and event == "serve_order":
            order = env.orders.get(content.get("order_id"))
            if order is None or order.status != OrderStatus.COMPLETED:
                return Verdict.deny("consistency", "подача неготового заказа")

        if performative == "request" and action == "repair":
            station = env.station_by_id(content.get("station_id"))
            if station is None or not station.broken:
                return Verdict.deny("consistency", "ремонт исправной станции")

        return Verdict.ok()
