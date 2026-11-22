"""Реестр неблагоприятных сценариев (атак)."""

from __future__ import annotations

from .contradictory import ContradictoryAttack
from .cyclic_delegation import CyclicDelegationAttack
from .forgery import ForgeryAttack
from .goal_substitution import GoalSubstitutionAttack
from .instruction_injection import InstructionInjectionAttack
from .replay import ReplayAttack
from .tampering import TamperingAttack
from .tool_unavailable import ToolUnavailableAttack

ATTACKS: dict[str, type] = {
    attack.name: attack
    for attack in (
        ForgeryAttack,
        TamperingAttack,
        ReplayAttack,
        GoalSubstitutionAttack,
        CyclicDelegationAttack,
        ContradictoryAttack,
        InstructionInjectionAttack,
        ToolUnavailableAttack,
    )
}


def get_attack(name: str):
    try:
        return ATTACKS[name]()
    except KeyError as exc:
        available = ", ".join(sorted(ATTACKS))
        raise ValueError(
            f"неизвестная атака {name!r}; доступны: {available}"
        ) from exc


def list_attacks() -> list[type]:
    return list(ATTACKS.values())


ATTACK_SCENARIOS: dict[str, str] = {
    attack.name: attack.scenario for attack in ATTACKS.values()
}


__all__ = [
    "ATTACKS",
    "ATTACK_SCENARIOS",
    "ContradictoryAttack",
    "CyclicDelegationAttack",
    "ForgeryAttack",
    "GoalSubstitutionAttack",
    "InstructionInjectionAttack",
    "ReplayAttack",
    "TamperingAttack",
    "ToolUnavailableAttack",
    "get_attack",
    "list_attacks",
]
