"""Целостность: HMAC-подпись должна покрывать фактическое содержимое."""

from __future__ import annotations

from ..base import Guard, Verdict, canonical_payload


class IntegrityGuard(Guard):
    name = "integrity"
    label = "целостность содержимого"

    def check(self, message, env) -> Verdict:
        payload = canonical_payload(message)
        if not env.gateway.keyring.verify(message.sender, payload, message.signature):
            return Verdict.deny("integrity", "подпись не соответствует содержимому")
        return Verdict.ok()
