"""Агенты кухни."""

from ..core.bus import MessageBus
from ..core.agent import Agent
from .cook import PatrickAgent, SpongeBobAgent
from .krabs import KrabsAgent
from .plankton import PlanktonAgent
from .sandy import SandyAgent
from .squidward import SquidwardAgent


def build_agents(bus: MessageBus) -> list[Agent]:
    return [
        SquidwardAgent("squidward", bus),
        KrabsAgent("krabs", bus),
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
