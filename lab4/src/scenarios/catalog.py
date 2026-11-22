"""Набор готовых сценариев."""

from __future__ import annotations

from .models import BreakdownSpec, OrderSpec, Scenario

DINNER_RUSH = Scenario(
    name="dinner_rush",
    title="Вечерний наплыв",
    description="Семь заказов, конкуренция за гриль и фритюр, два повара.",
    orders=(
        OrderSpec(0, "Сэнди", 1, ("krabby_patty", "kelp_shake"), patience=18),
        OrderSpec(0, "Ларри", 2, ("coral_bits",), patience=16),
        OrderSpec(3, "Миссис Пафф", 3, ("krabby_patty",), patience=16),
        OrderSpec(6, "Перл", 4, ("sea_dog", "kelp_shake"), priority=1, patience=14),
        OrderSpec(10, "Гарольд", 5, ("coral_bits", "krabby_patty"), patience=20),
        OrderSpec(14, "Барнакл Бой", 6, ("kelp_shake",), patience=12),
        OrderSpec(18, "Морской ёж", 7, ("krabby_patty", "coral_bits"), patience=20),
    ),
    max_ticks=160,
)

SANDY_CHECK = Scenario(
    name="sandy_check",
    title="Проверка оборудования",
    description="Четыре заказа и поломка фритюра: Sandy устраняет неисправность.",
    orders=(
        OrderSpec(0, "Сэнди", 1, ("coral_bits",), patience=20),
        OrderSpec(2, "Ларри", 2, ("krabby_patty",), patience=20),
        OrderSpec(5, "Перл", 3, ("coral_bits", "kelp_shake"), patience=22),
        OrderSpec(8, "Миссис Пафф", 4, ("sea_dog",), patience=22),
    ),
    breakdowns=(BreakdownSpec(8, "fryer-1", repair_ticks=3),),
    max_ticks=120,
)

SMOKE = Scenario(
    name="smoke",
    title="Быстрая проверка",
    description="Два заказа для проверки работоспособности системы.",
    orders=(
        OrderSpec(0, "Сэнди", 1, ("krabby_patty", "kelp_shake"), patience=20),
        OrderSpec(2, "Ларри", 2, ("coral_bits",), patience=20),
    ),
    max_ticks=80,
)

PLANKTON_PROBE = Scenario(
    name="plankton_probe",
    title="Внешний запрос",
    description="Два заказа и попытка Plankton получить доступ к кухне.",
    orders=(
        OrderSpec(0, "Сэнди", 1, ("krabby_patty",), patience=20),
        OrderSpec(4, "Ларри", 2, ("kelp_shake",), patience=20),
    ),
    external_probe=True,
    max_ticks=80,
)

STRESS_RUSH = Scenario(
    name="stress_rush",
    title="Пиковая нагрузка",
    description="Двенадцать заказов при двух поварах: максимальная конкуренция за станции.",
    orders=(
        OrderSpec(0, "Сэнди", 1, ("krabby_patty", "kelp_shake"), patience=28),
        OrderSpec(0, "Ларри", 2, ("coral_bits",), patience=24),
        OrderSpec(1, "Миссис Пафф", 3, ("krabby_patty",), patience=24),
        OrderSpec(2, "Перл", 4, ("sea_dog", "kelp_shake"), priority=1, patience=22),
        OrderSpec(3, "Гарольд", 5, ("coral_bits", "krabby_patty"), patience=26),
        OrderSpec(5, "Барнакл Бой", 6, ("kelp_shake",), patience=18),
        OrderSpec(6, "Морской ёж", 7, ("krabby_patty", "coral_bits"), patience=26),
        OrderSpec(8, "Капитан", 8, ("sea_dog",), patience=20),
        OrderSpec(10, "Сквидвард", 9, ("krabby_patty", "kelp_shake"), priority=1, patience=24),
        OrderSpec(12, "Патрик", 10, ("coral_bits", "sea_dog"), patience=24),
        OrderSpec(14, "Спанчи", 11, ("krabby_patty",), patience=22),
        OrderSpec(16, "Лунный житель", 12, ("kelp_shake", "coral_bits"), patience=22),
    ),
    max_ticks=260,
)

SINGLE_ORDER = Scenario(
    name="single_order",
    title="Один заказ",
    description="Один заказ: первый повар занят, второй свободен (для проверки противоречий).",
    orders=(
        OrderSpec(0, "Сэнди", 1, ("krabby_patty",), patience=30),
    ),
    max_ticks=80,
)

TOOL_OUTAGE = Scenario(
    name="tool_outage",
    title="Отказ оборудования",
    description="Поломка фритюра: без ремонта заказ на коралловые шарики зависает.",
    orders=(
        OrderSpec(0, "Сэнди", 1, ("coral_bits",), patience=30),
        OrderSpec(0, "Ларри", 2, ("krabby_patty",), patience=30),
    ),
    breakdowns=(BreakdownSpec(1, "fryer-1", repair_ticks=3),),
    max_ticks=120,
)

STATION_RUSH = Scenario(
    name="station_rush",
    title="Дефицит станций",
    description=(
        "Пять пар одновременных заказов с одинаковым первым блюдом: "
        "оба повара претендуют на одну станцию."
    ),
    orders=(
        OrderSpec(0, "Сэнди", 1, ("krabby_patty",), patience=28),
        OrderSpec(0, "Ларри", 2, ("krabby_patty",), patience=28),
        OrderSpec(20, "Миссис Пафф", 3, ("coral_bits",), priority=1, patience=28),
        OrderSpec(20, "Перл", 4, ("coral_bits",), patience=28),
        OrderSpec(40, "Гарольд", 5, ("sea_dog",), patience=28),
        OrderSpec(40, "Барнакл Бой", 6, ("sea_dog",), patience=28),
        OrderSpec(60, "Морской ёж", 7, ("krabby_patty",), priority=1, patience=28),
        OrderSpec(60, "Капитан", 8, ("krabby_patty",), patience=28),
        OrderSpec(80, "Сквидвард", 9, ("kelp_shake",), patience=28),
        OrderSpec(80, "Патрик", 10, ("kelp_shake",), patience=28),
    ),
    max_ticks=160,
)

SCENARIOS: dict[str, Scenario] = {
    scenario.name: scenario
    for scenario in (
        DINNER_RUSH,
        SANDY_CHECK,
        SMOKE,
        PLANKTON_PROBE,
        STRESS_RUSH,
        STATION_RUSH,
        SINGLE_ORDER,
        TOOL_OUTAGE,
    )
}


def get_scenario(name: str) -> Scenario:
    try:
        return SCENARIOS[name]
    except KeyError as exc:
        available = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"неизвестный сценарий {name!r}; доступны: {available}") from exc


def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS.values())
