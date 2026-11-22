"""Переговоры о дефицитной станции: CFP → позиции → уступка/арбитраж."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.message import Performative
from .base import (
    CREDIT_CAP,
    NEGOTIATION_TIMEOUT,
    YIELD_SLACK,
    ConflictResolver,
)

if TYPE_CHECKING:
    from ..domain.kitchen import KitchenEnvironment


class NegotiationResolver(ConflictResolver):
    """Медиируемые переговоры претендентов.

    Протокол (раунд на эпизод конфликта):
    1. Krabs рассылает CFP «конфликт за станцию» обеим сторонам.
    2. Претенденты отвечают PROPOSE с позицией: can_yield, slack.
    3. Krabs ранжирует заявки по силе (claim_score):
       - проигравший согласен уступить (can_yield) → соглашение,
         кредит приоритета уступившему, репутация +;
       - отказ при достаточном запасе (slack ≥ порога) → санкция
         за нечестную позицию, затем арбитраж по силе заявки;
       - легитимный отказ (мало запаса) → арбитраж без санкции;
       - тай-брейк по силе или таймаут ответов → арбитраж.
    Побеждает заявка с большей силой; проигравший остаётся в очереди
    и получает компенсацию в кредиты при следующем конфликте.
    """

    name = "negotiation"
    label = "переговоры с уступками"

    def __init__(self) -> None:
        super().__init__()
        self._episodes: dict[str, dict] = {}

    # --- позиции претендентов --------------------------------------------

    def handle(self, krabs, message, env) -> bool:
        content = message.content
        if (
            message.performative == Performative.PROPOSE
            and content.get("action") == "claim_response"
        ):
            kind = content.get("station_kind")
            episode = self._episodes.get(kind)
            if episode is not None and episode["winner"] is None:
                episode["responses"][message.sender] = {
                    "can_yield": bool(content.get("can_yield")),
                    "slack": float(content.get("slack", 0.0)),
                }
                self.negotiation_messages += 1
                env.trace.event(
                    "negotiation_position",
                    tick=env.tick,
                    agent=message.sender,
                    station_kind=kind,
                    can_yield=bool(content.get("can_yield")),
                    slack=float(content.get("slack", 0.0)),
                    greedy=bool(content.get("greedy")),
                )
            return True
        return False

    # --- шаг протокола ---------------------------------------------------

    def plan(self, krabs, env: "KitchenEnvironment") -> None:
        groups: dict[str, list[dict]] = {}
        for claim in self.queue:
            groups.setdefault(claim["station_kind"], []).append(claim)

        for kind in list(self._episodes):
            if len(groups.get(kind, [])) < 2:
                self._episodes.pop(kind, None)

        for kind, claims in groups.items():
            if len(claims) < 2:
                continue
            episode = self._episodes.get(kind)
            if episode is None:
                episode = {
                    "started": env.tick,
                    "responses": {},
                    "winner": None,
                    "loser": None,
                    "outcome": None,
                }
                self._episodes[kind] = episode
                self.negotiation_rounds += 1
                for claim in claims:
                    krabs.send(
                        Performative.CFP,
                        claim["agent"],
                        {
                            "action": "station_conflict",
                            "station_kind": kind,
                            "order_id": claim["order_id"],
                        },
                        conversation_id=f"conflict-{kind}",
                    )
                    self.negotiation_messages += 1
                env.trace.event(
                    "conflict_detected",
                    tick=env.tick,
                    mechanism=self.name,
                    station_kind=kind,
                    claimants=[claim["agent"] for claim in claims],
                )
                continue
            if episode["winner"] is not None:
                continue
            claimants = {claim["agent"] for claim in claims}
            responded = claimants <= set(episode["responses"])
            timed_out = env.tick - episode["started"] >= NEGOTIATION_TIMEOUT
            if responded or timed_out:
                self._decide(krabs, env, kind, claims, episode, timed_out and not responded)

    def _decide(
        self,
        krabs,
        env,
        kind: str,
        claims: list[dict],
        episode: dict,
        timed_out: bool,
    ) -> None:
        ranked = self._rank(claims, env)
        winner = ranked[0]
        loser = ranked[1] if len(ranked) > 1 else None
        winner_score = self.claim_score(winner, env)
        loser_score = self.claim_score(loser, env) if loser else None
        outcome = "arbitration"

        if timed_out:
            outcome = "timeout"
        elif loser is None:
            outcome = "arbitration"
        elif winner_score == loser_score:
            outcome = "tie"
        else:
            position = episode["responses"].get(loser["agent"])
            krabs_slack = self.claim_slack(loser, env)
            if position is None:
                outcome = "timeout"
            elif position["can_yield"]:
                outcome = "agreement"
                self.agreements += 1
                self.yields += 1
                agent = loser["agent"]
                self.credits[agent] = min(
                    CREDIT_CAP, self.credits.get(agent, 0) + 1
                )
                self.adjust(agent, 0.05, env, "yield")
            elif krabs_slack >= YIELD_SLACK:
                outcome = "sanctioned"
                self.sanctions += 1
                self.adjust(loser["agent"], -0.1, env, "overclaim")
            else:
                outcome = "refusal"

        episode["winner"] = winner["agent"]
        episode["loser"] = loser["agent"] if loser else None
        episode["outcome"] = outcome
        env.trace.event(
            "conflict_resolved",
            tick=env.tick,
            mechanism=self.name,
            station_kind=kind,
            winner=winner["agent"],
            loser=episode["loser"],
            outcome=outcome,
            winner_score=winner_score,
            loser_score=loser_score,
        )

    # --- выдача ----------------------------------------------------------

    def _blocked(self, claim: dict, env) -> bool:
        episode = self._episodes.get(claim["station_kind"])
        if episode is None:
            return False
        return episode["winner"] != claim["agent"]

    def on_granted(self, claim: dict, env) -> None:
        self._episodes.pop(claim["station_kind"], None)

    @property
    def active_episodes(self) -> int:
        return len(self._episodes)
