"""Модели заказов, блюд, станций и инвентаря."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StationKind(str, Enum):
    GRILL = "grill"
    FRYER = "fryer"
    SODA = "soda"
    ASSEMBLY = "assembly"

    @property
    def label(self) -> str:
        return {
            StationKind.GRILL: "гриль",
            StationKind.FRYER: "фритюр",
            StationKind.SODA: "газировка",
            StationKind.ASSEMBLY: "сборка",
        }[self]


class OrderStatus(str, Enum):
    NEW = "new"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SERVED = "served"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        return {
            OrderStatus.NEW: "новый",
            OrderStatus.QUEUED: "в очереди",
            OrderStatus.ASSIGNED: "назначен",
            OrderStatus.IN_PROGRESS: "готовится",
            OrderStatus.COMPLETED: "готов",
            OrderStatus.SERVED: "подан",
            OrderStatus.CANCELLED: "отменён",
        }[self]


INGREDIENT_LABELS = {
    "patty": "котлета",
    "bun": "булочка",
    "lettuce": "салат",
    "coral_bits": "коралловые шарики",
    "kelp": "ламинария",
    "sausage": "сосиска",
}

DISH_LABELS = {
    "krabby_patty": "Крабсбургер",
    "coral_bits": "Коралловые шарики",
    "kelp_shake": "Коктейль из ламинарии",
    "sea_dog": "Морской хот-дог",
}


@dataclass(frozen=True)
class TaskSpec:
    kind: StationKind
    duration: int
    ingredients: dict[str, int] = field(default_factory=dict)
    label: str = ""


@dataclass(frozen=True)
class Recipe:
    name: str
    price: int
    steps: tuple[TaskSpec, ...]


RECIPES: dict[str, Recipe] = {
    "krabby_patty": Recipe(
        "Крабсбургер",
        12,
        (
            TaskSpec(StationKind.GRILL, 2, {"patty": 1}, "обжарить котлету"),
            TaskSpec(StationKind.ASSEMBLY, 1, {"bun": 1, "lettuce": 1}, "собрать бургер"),
        ),
    ),
    "coral_bits": Recipe(
        "Коралловые шарики",
        6,
        (TaskSpec(StationKind.FRYER, 2, {"coral_bits": 1}, "обжарить коралловые шарики"),),
    ),
    "kelp_shake": Recipe(
        "Коктейль из ламинарии",
        5,
        (TaskSpec(StationKind.SODA, 1, {"kelp": 1}, "смешать коктейль"),),
    ),
    "sea_dog": Recipe(
        "Морской хот-дог",
        9,
        (
            TaskSpec(StationKind.GRILL, 2, {"sausage": 1}, "обжарить сосиску"),
            TaskSpec(StationKind.ASSEMBLY, 1, {"bun": 1}, "собрать хот-дог"),
        ),
    ),
}


@dataclass
class Order:
    order_id: str
    customer: str
    table: int
    items: list[str]
    created_tick: int
    deadline: int
    priority: int = 0
    status: OrderStatus = OrderStatus.NEW
    assignee: str | None = None
    tasks: list[TaskSpec] = field(default_factory=list)
    price: int = 0
    served_tick: int | None = None
    tip: int = 0
    announced: bool = False

    @property
    def items_label(self) -> str:
        return ", ".join(DISH_LABELS.get(item, item) for item in self.items)

    @property
    def is_open(self) -> bool:
        return self.status not in (OrderStatus.SERVED, OrderStatus.CANCELLED)


@dataclass
class Station:
    station_id: str
    kind: StationKind
    occupant: str | None = None
    busy_until: int = 0
    broken: bool = False

    @property
    def is_free(self) -> bool:
        return self.occupant is None and not self.broken


class Inventory:
    def __init__(self, stock: dict[str, int]) -> None:
        self.initial = dict(stock)
        self.stock = dict(stock)

    def has(self, needs: dict[str, int]) -> bool:
        return all(self.stock.get(item, 0) >= amount for item, amount in needs.items())

    def consume(self, needs: dict[str, int]) -> bool:
        if not self.has(needs):
            return False
        for item, amount in needs.items():
            self.stock[item] -= amount
        return True

    def levels(self) -> list[dict[str, object]]:
        return [
            {
                "item": item,
                "label": INGREDIENT_LABELS.get(item, item),
                "qty": qty,
            }
            for item, qty in sorted(self.stock.items())
        ]


def build_order_tasks(items: list[str]) -> tuple[list[TaskSpec], int]:
    tasks: list[TaskSpec] = []
    price = 0
    for item in items:
        recipe = RECIPES[item]
        tasks.extend(recipe.steps)
        price += recipe.price
    return tasks, price
