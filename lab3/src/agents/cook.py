"""Повара: SpongeBob и Patrick.

Понимает три протокола распределения:
- централизованный REQUEST/AGREE (push-назначение);
- CFP/PROPOSE/ACCEPT контрактной сети (score-оценка);
- CFP/PROPOSE/ACCEPT аукциона (цена, платёж по второй цене);
и переговоры о дефицитной станции (CFP station_conflict ->
PROPOSE claim_response с позицией can_yield/slack).
"""

from __future__ import annotations

import math

from ..core.agent import Agent
from ..core.message import Performative
from ..domain.models import OrderStatus


class CookAgent(Agent):
    def __init__(
        self,
        agent_id: str,
        role: str,
        bus,
        skill: float,
        greedy: bool = False,
    ) -> None:
        super().__init__(agent_id, role, bus)
        self.skill = skill
        self.greedy = greedy
        self.order_id: str | None = None
        self.task_index = 0
        self.station_id: str | None = None
        self.busy_until = 0
        self.current_duration = 0
        self.waiting_kind = None
        self.state = "IDLE"
        self.reporting_complete = False
        self.pending_bids: set[str] = set()

    # --- ставки для контрактной сети и аукциона -------------------------

    def coordination_score(self, env) -> float:
        """Оценка контрактной сети: выше, когда повар быстрее и свободнее."""
        load = float(env.workload.get(self.id, 0))
        return round(10.0 / self.skill - 0.25 * load, 2)

    def bid_price(self, env) -> float:
        """Цена аукциона: стоимость свободной ёмкости повара.

        Растёт с текущей загрузкой: чем больше повар занят, тем дороже
        его привлечь. Мастерство в цену не входит — аукцион выбирает
        наименее загруженного, тогда как контрактная сеть смотрит в
        первую очередь на мастерство.
        """
        load = float(env.workload.get(self.id, 0))
        return round(1.0 + load, 2)

    # --- основной цикл ---------------------------------------------------

    def step(self, env) -> None:
        for message in self.receive():
            self.handle(message, env)
        self._drop_stale_bids(env)
        if self.state == "REPORTING":
            self.finish_reporting()
            return
        if self.order_id is None:
            if self.state not in ("BIDDING",):
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

    # --- обработка сообщений ---------------------------------------------

    def handle(self, message, env) -> None:
        content = message.content
        action = content.get("action")
        event = content.get("event")

        if message.performative == Performative.REQUEST and action == "cook_order":
            self._handle_direct_request(content, message, env)
            return

        if message.performative == Performative.CFP and action == "cook_order":
            self._handle_cfp(content, message, env)
            return

        if message.performative == Performative.CFP and action == "station_conflict":
            self._handle_conflict_cfp(content, message, env)
            return

        if message.performative == Performative.ACCEPT and action == "cook_order":
            self._handle_accept(content, message, env)
            return

        if message.performative == Performative.REFUSE and action == "cook_order":
            order_id = content.get("order_id")
            if order_id in self.pending_bids:
                self.pending_bids.discard(order_id)
                if self.order_id is None and not self.pending_bids:
                    self.state = "IDLE"
            return

        if message.performative == Performative.AGREE and event == "station_granted":
            if (
                self.order_id == content.get("order_id")
                and self.state == "WAITING_STATION"
            ):
                self.start_task(env, content)
            return

        if message.performative == Performative.REFUSE and self.state == "WAITING_STATION":
            self.state = "ASSIGNED"

    def _drop_stale_bids(self, env) -> None:
        """Сбрасывает ставки по заказам, уже разрешённым без нашего участия."""
        if not self.pending_bids:
            return
        for order_id in list(self.pending_bids):
            order = env.orders.get(order_id)
            if order is None or order.status != OrderStatus.NEW:
                self.pending_bids.discard(order_id)
        if not self.pending_bids and self.state == "BIDDING" and self.order_id is None:
            self.state = "IDLE"

    def _handle_direct_request(self, content: dict, message, env) -> None:
        """Централизованное назначение: REQUEST -> AGREE/REFUSE."""
        if self.order_id is None:
            self._accept_order(content["order_id"], env)
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

    def _handle_cfp(self, content: dict, message, env) -> None:
        """Запрос предложений: ответить ставкой или отказом."""
        order_id = content.get("order_id")
        if order_id is None:
            return
        if self.order_id is not None or order_id in self.pending_bids:
            self.send(
                Performative.REFUSE,
                "krabs",
                {
                    "action": "cook_order",
                    "order_id": order_id,
                    "reason": "занят",
                    "mechanism": content.get("mechanism"),
                },
                conversation_id=message.conversation_id,
            )
            return
        self.pending_bids.add(order_id)
        self.state = "BIDDING"
        self.send(
            Performative.PROPOSE,
            "krabs",
            {
                "action": "cook_order",
                "order_id": order_id,
                "score": self.coordination_score(env),
                "price": self.bid_price(env),
                "mechanism": content.get("mechanism"),
            },
            conversation_id=message.conversation_id,
        )
        env.trace.event(
            "bid_sent",
            tick=env.tick,
            agent=self.id,
            order_id=order_id,
            score=self.coordination_score(env),
            price=self.bid_price(env),
        )

    def _handle_conflict_cfp(self, content: dict, message, env) -> None:
        """Переговоры о дефицитной станции: сообщить свою позицию.

        can_yield — готов ли повар уступить станцию (честные повара
        всегда готовы, если у них остаётся запас; жадный — никогда).
        slack — запас тиков до дедлайна с учётом мастерства.
        """
        if self.state != "WAITING_STATION" or self.order_id is None:
            return
        order = env.orders.get(self.order_id)
        if order is None:
            return
        remaining = sum(
            task.duration for task in order.tasks[self.task_index :]
        ) * self.skill
        slack = order.deadline - env.tick - remaining
        self.send(
            Performative.PROPOSE,
            "krabs",
            {
                "action": "claim_response",
                "station_kind": content.get("station_kind"),
                "order_id": self.order_id,
                "can_yield": not self.greedy,
                "slack": round(slack, 2),
                "greedy": self.greedy,
            },
            conversation_id=message.conversation_id,
        )
        env.trace.event(
            "negotiation_offer",
            tick=env.tick,
            agent=self.id,
            order_id=self.order_id,
            can_yield=not self.greedy,
            slack=round(slack, 2),
        )

    def _handle_accept(self, content: dict, message, env) -> None:
        """Победа в распределении: принять заказ и начать работу."""
        order_id = content.get("order_id")
        if order_id is None:
            return
        if self.order_id is not None:
            self.send(
                Performative.REFUSE,
                "krabs",
                {"action": "cook_order", "order_id": order_id, "reason": "уже занят"},
                conversation_id=message.conversation_id,
            )
            return
        self.pending_bids.discard(order_id)
        self._accept_order(order_id, env)
        env.trace.event(
            "contract_accepted",
            tick=env.tick,
            mechanism=content.get("mechanism"),
            agent=self.id,
            order_id=order_id,
            score=content.get("score"),
            price=content.get("price"),
            payment=content.get("payment"),
        )

    def _accept_order(self, order_id: str, env) -> None:
        self.order_id = order_id
        self.task_index = 0
        self.state = "ASSIGNED"
        self.pending_bids.clear()
        env.trace.event(
            "order_accepted",
            tick=env.tick,
            order_id=order_id,
            agent=self.id,
        )

    # --- работа над заказом ----------------------------------------------

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
        self.pending_bids.clear()

    def describe(self) -> dict:
        detail = ""
        if self.order_id is not None:
            detail = f"заказ {self.order_id}, шаг {self.task_index + 1}"
        elif self.pending_bids:
            detail = f"ставки: {', '.join(sorted(self.pending_bids))}"
        return {"id": self.id, "role": self.role, "state": self.state, "detail": detail}


class SpongeBobAgent(CookAgent):
    def __init__(self, agent_id: str, bus) -> None:
        super().__init__(agent_id, "повар-универсал", bus, 1.0)


class PatrickAgent(CookAgent):
    def __init__(self, agent_id: str, bus) -> None:
        super().__init__(agent_id, "второй повар", bus, 1.4, greedy=True)
