"""Базовый класс разрешения конфликтов за станции.

Конфликт: несколько поваров одновременно претендуют на станцию одного
типа (дефицит ресурса). Резолвер владеет очередью заявок, репутацией
поваров и приоритетными кредитами; протоколы различаются правилом
выбора победителя и наличием переговоров.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from typing import TYPE_CHECKING, Any

from ..core.message import Message, Performative

if TYPE_CHECKING:
    from ..domain.kitchen import KitchenEnvironment

YIELD_SLACK = 6.0
STARVE_LIMIT = 12
REPUTATION_FLOOR = 0.0
REPUTATION_CAP = 2.0
CREDIT_CAP = 2
NEGOTIATION_TIMEOUT = 3


class ConflictResolver(ABC):
    """Стратегия разрешения конкурирующих заявок на станции."""

    name: str = "base"
    label: str = "базовый"

    def __init__(self) -> None:
        self.queue: list[dict] = []
        self.reserved: set[str] = set()
        self.reputation: dict[str, float] = {}
        self.credits: dict[str, int] = {}
        self.conflict_events = 0
        self.contention_ticks = 0
        self.negotiation_rounds = 0
        self.negotiation_messages = 0
        self.agreements = 0
        self.yields = 0
        self.sanctions = 0
        self.violations = 0
        self.starved = 0
        self.wait_sum = 0
        self.wait_count = 0
        self.wait_max = 0
        self._contention_kinds: set[str] = set()

    # --- приём заявок ----------------------------------------------------

    def submit(self, content: dict, agent: str, tick: int) -> None:
        self.queue.append(
            {
                "agent": agent,
                "station_kind": content.get("station_kind"),
                "order_id": content.get("order_id"),
                "task_index": int(content.get("task_index", 0)),
                "claim_tick": tick,
            }
        )

    def release(self, station_id: str) -> None:
        self.reserved.discard(station_id)

    def adjust(self, agent: str, delta: float, env, reason: str) -> None:
        """Корректирует репутацию повара с ограничением диапазона."""
        before = self.reputation.get(agent, 1.0)
        after = max(
            REPUTATION_FLOOR, min(REPUTATION_CAP, before + delta)
        )
        self.reputation[agent] = round(after, 3)
        if env is not None:
            env.trace.event(
                "reputation_changed",
                tick=env.tick,
                agent=agent,
                delta=round(delta, 3),
                value=round(after, 3),
                reason=reason,
            )

    # --- жизненный цикл --------------------------------------------------

    def resolve(self, krabs: Any, env: "KitchenEnvironment") -> None:
        self._prune(env)
        self._track_contention(env)
        self.plan(krabs, env)
        self._grant(krabs, env)

    @abstractmethod
    def plan(self, krabs: Any, env: "KitchenEnvironment") -> None:
        """Шаг протокола: сообщения переговоров, выбор победителя."""

    def handle(self, krabs: Any, message: Message, env) -> bool:
        """Обработать ответы претендентов. True — сообщение поглощено."""
        return False

    def grant_order(self, env) -> list[dict]:
        """Порядок рассмотрения заявок при выдаче станций."""
        return list(self.queue)

    def _blocked(self, claim: dict, env) -> bool:
        """Заявка не может получить станцию на этом тике."""
        return False

    # --- внутренности ----------------------------------------------------

    def _prune(self, env) -> None:
        alive: list[dict] = []
        for claim in self.queue:
            waited = env.tick - claim["claim_tick"]
            if waited > STARVE_LIMIT and not claim.get("starved"):
                claim["starved"] = True
                self.starved += 1
            order = env.orders.get(claim["order_id"])
            cook = next(
                (a for a in env.agents if a.id == claim["agent"]), None
            )
            stale = (
                order is None
                or order.status.value in ("completed", "served", "cancelled")
                or cook is None
                or cook.state != "WAITING_STATION"
                or getattr(cook, "order_id", None) != claim["order_id"]
            )
            if stale:
                continue
            alive.append(claim)
        self.queue = alive

    def _track_contention(self, env) -> None:
        counts = Counter(
            claim["station_kind"] for claim in self.queue
        )
        current = {
            kind for kind, count in counts.items() if count >= 2
        }
        self.conflict_events += len(current - self._contention_kinds)
        if current:
            self.contention_ticks += 1
        self._contention_kinds = current

    def _grant(self, krabs: Any, env) -> None:
        for claim in self.grant_order(env):
            if self._blocked(claim, env):
                continue
            station = self._free_station(env, claim["station_kind"])
            if station is None:
                continue
            self._do_grant(krabs, env, claim, station)

    def _free_station(self, env, kind: str):
        for station in env.stations:
            if (
                station.kind.value == kind
                and station.is_free
                and station.station_id not in self.reserved
            ):
                return station
        return None

    def _do_grant(self, krabs: Any, env, claim: dict, station) -> None:
        if station.station_id in self.reserved or station.occupant is not None:
            self.violations += 1
            return
        self.reserved.add(station.station_id)
        wait = env.tick - claim["claim_tick"]
        self.wait_sum += wait
        self.wait_count += 1
        self.wait_max = max(self.wait_max, wait)
        agent = claim["agent"]
        if self.credits.get(agent, 0) > 0:
            self.credits[agent] -= 1
        if claim in self.queue:
            self.queue.remove(claim)
        krabs.send(
            Performative.AGREE,
            agent,
            {
                "event": "station_granted",
                "station_id": station.station_id,
                "order_id": claim["order_id"],
                "task_index": claim["task_index"],
            },
            conversation_id=f"order-{claim['order_id']}",
        )
        env.trace.event(
            "station_granted",
            tick=env.tick,
            mechanism=self.name,
            station_id=station.station_id,
            station_kind=claim["station_kind"],
            agent=agent,
            order_id=claim["order_id"],
            wait=wait,
        )
        self.on_granted(claim, env)

    def on_granted(self, claim: dict, env) -> None:
        """Хук: эпизод конфликта закрыт (переопределяет переговорщик)."""

    # --- оценка заявок ---------------------------------------------------

    def _skill(self, env, agent_id: str) -> float:
        for agent in env.agents:
            if agent.id == agent_id:
                return float(getattr(agent, "skill", 1.0))
        return 1.0

    def claim_slack(self, claim: dict, env) -> float:
        """Запас времени до дедлайна с учётом оставшейся работы."""
        order = env.orders.get(claim["order_id"])
        if order is None:
            return -999.0
        remaining = sum(
            task.duration for task in order.tasks[claim["task_index"] :]
        ) * self._skill(env, claim["agent"])
        return float((order.deadline - env.tick) - remaining)

    def claim_score(self, claim: dict, env) -> float:
        """Сила заявки: приоритет, срочность, репутация, кредит, загрузка."""
        order = env.orders.get(claim["order_id"])
        if order is None:
            return -1.0
        slack = self.claim_slack(claim, env)
        urgency = 1.0 / (1.0 + max(0.0, slack))
        rep = self.reputation.get(claim["agent"], 1.0)
        credit = self.credits.get(claim["agent"], 0)
        load = sum(
            1
            for other in env.orders.values()
            if other.assignee == claim["agent"] and other.is_open
        )
        return round(
            2.0 * order.priority
            + 2.0 * urgency
            + 0.5 * rep
            + 0.5 * credit
            - 0.25 * load,
            4,
        )

    def _rank(self, claims: list[dict], env) -> list[dict]:
        return sorted(
            claims,
            key=lambda claim: (
                -self.claim_score(claim, env),
                -self.credits.get(claim["agent"], 0),
                claim["claim_tick"],
                claim["agent"],
            ),
        )

    # --- снимок для метрик -----------------------------------------------

    def snapshot(self) -> dict:
        scores = list(self.reputation.values())
        return {
            "mode": self.name,
            "label": self.label,
            "queue": len(self.queue),
            "conflict_events": self.conflict_events,
            "contention_ticks": self.contention_ticks,
            "negotiation_rounds": self.negotiation_rounds,
            "negotiation_messages": self.negotiation_messages,
            "agreements": self.agreements,
            "yields": self.yields,
            "sanctions": self.sanctions,
            "violations": self.violations,
            "starved": self.starved,
            "station_wait_avg": (
                round(self.wait_sum / self.wait_count, 2)
                if self.wait_count
                else 0.0
            ),
            "station_wait_max": self.wait_max,
            "reputation": {
                agent: round(value, 3)
                for agent, value in sorted(self.reputation.items())
            },
            "reputation_mean": (
                round(sum(scores) / len(scores), 3) if scores else 1.0
            ),
            "credits": dict(self.credits),
        }
