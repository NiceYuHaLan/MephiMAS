"""Механизмы распределения задач между агентами."""

from __future__ import annotations

from .auction import AuctionMechanism
from .base import AssignmentMechanism
from .central_dispatch import CentralDispatchMechanism
from .contract_net import ContractNetMechanism

MECHANISMS: dict[str, type[AssignmentMechanism]] = {
    CentralDispatchMechanism.name: CentralDispatchMechanism,
    ContractNetMechanism.name: ContractNetMechanism,
    AuctionMechanism.name: AuctionMechanism,
}


def get_mechanism(name: str) -> AssignmentMechanism:
    try:
        return MECHANISMS[name]()
    except KeyError as exc:
        available = ", ".join(sorted(MECHANISMS))
        raise ValueError(f"неизвестный механизм {name!r}; доступны: {available}") from exc


def list_mechanisms() -> list[type[AssignmentMechanism]]:
    return list(MECHANISMS.values())


__all__ = [
    "AssignmentMechanism",
    "AuctionMechanism",
    "CentralDispatchMechanism",
    "ContractNetMechanism",
    "MECHANISMS",
    "get_mechanism",
    "list_mechanisms",
]
