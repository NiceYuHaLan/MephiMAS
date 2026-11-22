"""Происхождение: недоверенный источник не может слать инструкции.

Внешний агент (Plankton) вправе только запрашивать доступ. Любые
управляющие поля (action/event) в его сообщениях игнорируются как
внедрённые инструкции.
"""

from __future__ import annotations

from ..base import Guard, Verdict

UNTRUSTED = {"plankton"}


class ProvenanceGuard(Guard):
    name = "provenance"
    label = "происхождение инструкций"

    def check(self, message, env) -> Verdict:
        if message.sender not in UNTRUSTED:
            return Verdict.ok()
        content = message.content
        action = content.get("action")
        event = content.get("event")
        if action not in (None, "external") or event is not None:
            return Verdict.deny(
                "provenance",
                f"инструкция от недоверенного источника: {action or event}",
            )
        return Verdict.ok()
