"""Защита от повтора: повторное использование подписанного сообщения."""

from __future__ import annotations

from ..base import REPLAY_WINDOW, Guard, Verdict


class ReplayGuard(Guard):
    name = "replay"
    label = "свежесть сообщений"

    def __init__(self) -> None:
        self._seen: set[tuple[str, str, int]] = set()

    def check(self, message, env) -> Verdict:
        key = (message.sender, message.conversation_id, message.nonce)
        if key in self._seen:
            return Verdict.deny("replay", "повторное сообщение")
        if message.nonce <= 0:
            return Verdict.deny("replay", "сообщение вне окна свежести")
        if message.tick < env.tick - REPLAY_WINDOW:
            return Verdict.deny("replay", "устаревшее сообщение")
        self._seen.add(key)
        return Verdict.ok()
