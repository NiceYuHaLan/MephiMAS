"""Шлюз безопасности: подпись исходящих, инъекции и проверка входящих."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import (
    Attack,
    Guard,
    KeyRing,
    SecurityMonitor,
    Verdict,
    canonical_payload,
)
from .guards import build_guards

if TYPE_CHECKING:
    from ..core.message import Message
    from ..domain.kitchen import KitchenEnvironment


class SecurityGateway:
    """Единая точка контроля обмена сообщениями.

    - подписывает исходящие сообщения ключом отправителя;
    - даёт атакам возможность наблюдать/подменять исходящие;
    - при включённой защите прогоняет цепочку проверок перед доставкой.
    """

    def __init__(self, trace, env: "KitchenEnvironment") -> None:
        self.trace = trace
        self.env = env
        self.keyring = KeyRing()
        self.monitor = SecurityMonitor()
        self.guards: list[Guard] = build_guards()
        self.attacks: list[Attack] = []
        self.defense_active = False
        self._nonces: dict[str, int] = {}

    # --- конфигурация ----------------------------------------------------

    def install_attack(self, attack: Attack) -> None:
        self.attacks.append(attack)
        self.monitor.attack = attack.name
        self.monitor.attack_category = attack.category
        attack.setup(self.env)

    def set_defense(self, enabled: bool) -> None:
        self.defense_active = bool(enabled)

    # --- подпись ---------------------------------------------------------

    def next_nonce(self, signer_id: str) -> int:
        value = self._nonces.get(signer_id, 0) + 1
        self._nonces[signer_id] = value
        return value

    def sign(self, message: "Message", signer_id: str) -> None:
        message.nonce = self.next_nonce(signer_id)
        message.signature = self.keyring.sign(
            signer_id, canonical_payload(message)
        )

    # --- хуки жизненного цикла ------------------------------------------

    def on_tick(self, env: "KitchenEnvironment") -> None:
        for attack in self.attacks:
            attack.on_tick(env)

    def on_send(self, message: "Message", env: "KitchenEnvironment") -> None:
        for attack in list(self.attacks):
            attack.on_send(message, env)

    # --- проверка --------------------------------------------------------

    def inspect(self, message: "Message", env: "KitchenEnvironment") -> Verdict:
        if not self.defense_active:
            return Verdict.ok()
        for guard in self.guards:
            verdict = guard.check(message, env)
            if not verdict.allow:
                self.monitor.mark_blocked(verdict)
                self.trace.event(
                    "security_blocked",
                    tick=env.tick,
                    guard=guard.name,
                    category=verdict.kind,
                    reason=verdict.reason,
                    sender=message.sender,
                    receiver=message.receiver,
                    performative=message.performative.value,
                )
                return verdict
        return Verdict.ok()

    # --- снимок ----------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        data = self.monitor.snapshot(self.env)
        data["defense"] = self.defense_active
        data["guards"] = [guard.name for guard in self.guards]
        return data
