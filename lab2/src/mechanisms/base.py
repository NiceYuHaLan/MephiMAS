"""Абстрактный механизм распределения задач между поварами."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.message import Message
    from ..domain.kitchen import KitchenEnvironment
    from ..domain.models import Order


class AssignmentMechanism(ABC):
    """Стратегия назначения заказов поварам.

    Механизм владеет протоколом распределения: инициирует объявление
    заказа, обрабатывает ответы поваров и фиксирует назначение.
    Выделение станций остаётся централизованным (Krabs) во всех режимах.
    """

    name: str = "base"
    label: str = "базовый"
    cook_ids: tuple[str, ...] = ("spongebob", "patrick")

    def __init__(self) -> None:
        self.assigned_orders: dict[str, str] = {}

    # --- lifecycle -------------------------------------------------------

    def on_tick(self, krabs: Any, env: "KitchenEnvironment") -> None:
        """Вызывается каждый тик: начать протокол для новых заказов."""
        self.announce_new_orders(krabs, env)

    @abstractmethod
    def announce_new_orders(self, krabs: Any, env: "KitchenEnvironment") -> None:
        """Найти необработанные заказы и запустить для них протокол."""

    @abstractmethod
    def handle(self, krabs: Any, message: "Message", env: "KitchenEnvironment") -> bool:
        """Обработать входящее сообщение. True — сообщение поглощено."""

    def new_conversation(self, order: "Order") -> str:
        return f"assign-{order.order_id}"
