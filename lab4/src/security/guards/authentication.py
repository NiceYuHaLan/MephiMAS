"""Аутентификация: у сообщения должна быть подпись известного агента."""

from __future__ import annotations

from ..base import Guard, Verdict


class AuthenticationGuard(Guard):
    name = "authentication"
    label = "аутентификация отправителя"

    def check(self, message, env) -> Verdict:
        if not message.signature:
            return Verdict.deny("auth", "сообщение без подписи")
        if not env.gateway.keyring.has(message.sender):
            return Verdict.deny("auth", f"неизвестный отправитель {message.sender}")
        return Verdict.ok()
