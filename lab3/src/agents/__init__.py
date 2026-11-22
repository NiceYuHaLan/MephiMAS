"""Агенты кухни."""

from ..core.agent import Agent
from ..core.bus import MessageBus
from ..mechanisms import AssignmentMechanism, get_mechanism
from .cook import PatrickAgent, SpongeBobAgent
from .krabs import KrabsAgent
from .plankton import PlanktonAgent
from .sandy import SandyAgent
from .squidward import SquidwardAgent


def build_agents(
    bus: MessageBus, mechanism: AssignmentMechanism | str | None = None
) -> list[Agent]:
    resolved = get_mechanism(mechanism) if isinstance(mechanism, str) or mechanism is None else mechanism
    return [
        SquidwardAgent("squidward", bus),
        KrabsAgent("krabs", bus, resolved),
        SpongeBobAgent("spongebob", bus),
        PatrickAgent("patrick", bus),
        SandyAgent("sandy", bus),
        PlanktonAgent("plankton", bus),
    ]


__all__ = [
    "KrabsAgent",
    "PatrickAgent",
    "PlanktonAgent",
    "SandyAgent",
    "SpongeBobAgent",
    "SquidwardAgent",
    "build_agents",
]
