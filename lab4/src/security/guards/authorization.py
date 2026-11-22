"""Полномочия: кто вправе отправлять какие управляющие сообщения."""

from __future__ import annotations

from ..base import Guard, Verdict

COOKS = {"spongebob", "patrick"}


def _rule(sender: str, message) -> bool | None:
    content = message.content
    performative = message.performative.value
    action = content.get("action")
    event = content.get("event")

    if performative == "inform" and event in ("order_complete", "step_done"):
        return sender in COOKS
    if performative == "inform" and event == "station_released":
        return sender in COOKS
    if performative == "inform" and event == "serve_order":
        return sender == "krabs"
    if performative == "inform" and event in ("served", "feedback"):
        return sender == "squidward"
    if performative == "inform" and event in ("repair_done",):
        return sender == "sandy"
    if performative == "inform" and event == "station_broken":
        return sender == "environment"
    if performative == "agree" and event == "station_granted":
        return sender == "krabs"
    if performative == "accept" and action == "cook_order":
        return sender == "krabs"
    if performative == "cfp" and action in ("cook_order", "station_conflict"):
        return sender == "krabs"
    if performative == "request" and action in ("cook_order", "station", "repair"):
        return sender in COOKS if action == "station" else sender == "krabs"
    if performative == "request" and action == "external":
        return sender == "plankton"
    if performative == "propose" and action in ("cook_order", "claim_response"):
        return sender in COOKS
    if performative == "agree" and action in ("cook_order", "repair"):
        return sender in COOKS if action == "cook_order" else sender == "sandy"
    if performative == "refuse" and action in ("cook_order", "repair"):
        return True
    return None


class AuthorizationGuard(Guard):
    name = "authorization"
    label = "полномочия агента"

    def check(self, message, env) -> Verdict:
        verdict = _rule(message.sender, message)
        if verdict is False:
            return Verdict.deny(
                "authorization",
                f"{message.sender} не вправе отправлять "
                f"{message.performative.value}/{message.content.get('action') or message.content.get('event')}",
            )
        return Verdict.ok()
