"""CLI-запуск симуляции кухни."""

from __future__ import annotations

import argparse
import json
import sys

from .scenarios.catalog import list_scenarios
from .simulation import Simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m src.main",
        description="Многоагентная кухня «Красти Крабс»: симуляция и метрики.",
    )
    parser.add_argument(
        "--scenario",
        default="dinner_rush",
        help="имя сценария (по умолчанию dinner_rush)",
    )
    parser.add_argument("--max-ticks", type=int, default=None, help="предел тиков")
    parser.add_argument("--trace", default=None, help="путь для JSONL-трассы")
    parser.add_argument(
        "--json", action="store_true", help="вывести итоговый снимок в JSON"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="не печатать прогресс по тикам"
    )
    parser.add_argument(
        "--list", action="store_true", help="показать доступные сценарии"
    )
    return parser


def print_scenarios() -> None:
    for scenario in list_scenarios():
        count = len(scenario.orders)
        print(f"{scenario.name:>12}  {scenario.title} — заказов: {count}")


def progress(env) -> None:
    served = sum(1 for order in env.orders.values() if order.status.value == "served")
    states = " ".join(f"{agent.id}={agent.state}" for agent in env.agents)
    print(f"[t={env.tick:>3}] подано {served}/{len(env.orders)}  {states}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        print_scenarios()
        return 0

    try:
        simulation = Simulation(args.scenario, trace_path=args.trace)
    except ValueError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 2

    data = simulation.snapshot()
    if not args.json:
        print(f"Сценарий: {data['scenario']['title']} ({args.scenario})")
        print(data["scenario"]["description"])

    on_tick = None if args.quiet or args.json else progress
    metrics = simulation.run(max_ticks=args.max_ticks, on_tick=on_tick)
    simulation.close()

    if args.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"Итог: тик {simulation.env.tick}")
        print(
            f"Заказы: подано {metrics['orders_served']}, "
            f"отменено {metrics['orders_cancelled']}, "
            f"открыто {metrics['orders_open']}"
        )
        print(
            f"Время: makespan={metrics['makespan']}, "
            f"среднее ожидание={metrics['avg_wait']}, "
            f"опозданий={metrics['late_orders']}"
        )
        print(
            f"Экономика: выручка={metrics['revenue']}, "
            f"чаевые={metrics['tips']}, касса={metrics['treasury']}"
        )
        print(
            f"Коммуникация: сообщений={metrics['messages_total']}, "
            f"по перформативам={metrics['messages_by_performative']}"
        )
        print(
            f"Нагрузка: {metrics['workload']}, "
            f"Gini={metrics['gini_workload']}, Jain={metrics['jain_workload']}"
        )
    return 0 if metrics["orders_open"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
