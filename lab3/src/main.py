"""CLI-запуск симуляции и сравнения механизмов распределения."""

from __future__ import annotations

import argparse
import json
import sys

from .conflict import list_resolvers
from .experiments import run_compare
from .mechanisms import list_mechanisms
from .scenarios.catalog import list_scenarios
from .simulation import Simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m src.main",
        description="Многоагентная кухня «Красти Крабс»: симуляция, механизмы, сравнение.",
    )
    parser.add_argument(
        "--scenario",
        default="dinner_rush",
        help="имя сценария (по умолчанию dinner_rush)",
    )
    parser.add_argument(
        "--mechanism",
        default="central",
        help="механизм распределения: central | contract_net | auction",
    )
    parser.add_argument(
        "--conflict",
        default="fcfs",
        help="режим разрешения конфликтов: fcfs | negotiation | arbitration",
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
        "--list", action="store_true", help="показать доступные сценарии и механизмы"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="сравнить механизмы на выбранных сценариях",
    )
    parser.add_argument(
        "--scenarios",
        default="smoke,dinner_rush,sandy_check,stress_rush",
        help="сценарии для --compare через запятую",
    )
    parser.add_argument(
        "--mechanisms",
        default="central,contract_net,auction",
        help="механизмы для --compare через запятую",
    )
    parser.add_argument(
        "--conflicts",
        default="fcfs,negotiation,arbitration",
        help="режимы конфликта для --compare через запятую",
    )
    parser.add_argument(
        "--out",
        default="results",
        help="каталог для CSV/JSON результатов сравнения",
    )
    return parser


def print_catalog() -> None:
    print("Сценарии:")
    for scenario in list_scenarios():
        count = len(scenario.orders)
        print(f"  {scenario.name:>14}  {scenario.title} — заказов: {count}")
    print("Механизмы:")
    for mechanism in list_mechanisms():
        print(f"  {mechanism.name:>14}  {mechanism.label}")
    print("Режимы конфликта:")
    for resolver in list_resolvers():
        print(f"  {resolver.name:>14}  {resolver.label}")


def progress(env) -> None:
    served = sum(1 for order in env.orders.values() if order.status.value == "served")
    states = " ".join(f"{agent.id}={agent.state}" for agent in env.agents)
    print(f"[t={env.tick:>3}] подано {served}/{len(env.orders)}  {states}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        print_catalog()
        return 0

    if args.compare:
        scenarios = [name.strip() for name in args.scenarios.split(",") if name.strip()]
        mechanisms = [name.strip() for name in args.mechanisms.split(",") if name.strip()]
        conflicts = [name.strip() for name in args.conflicts.split(",") if name.strip()]
        rows = run_compare(scenarios, mechanisms, conflicts, out_dir=args.out)
        return 0 if all(row["orders_open"] == 0 for row in rows) else 1

    try:
        simulation = Simulation(
            args.scenario,
            trace_path=args.trace,
            mechanism=args.mechanism,
            conflict=args.conflict,
        )
    except ValueError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 2

    data = simulation.snapshot()
    if not args.json:
        print(f"Сценарий: {data['scenario']['title']} ({args.scenario})")
        print(data["scenario"]["description"])
        print(f"Механизм: {data['mechanism']['label']} ({args.mechanism})")
        print(f"Конфликт: {data['conflict']['label']} ({args.conflict})")

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
            f"ср. ожидание={metrics['avg_wait']}, "
            f"опозданий={metrics['late_orders']}, "
            f"назначение={metrics['assignment_latency_avg']}"
        )
        print(
            f"Координация: сообщений={metrics['messages_total']}, "
            f"протокол={metrics['coordination_messages']}, "
            f"стоимость/заказ={metrics['coordination_cost']}, "
            f"платежи={metrics['coordination_spend']}"
        )
        print(
            f"Конфликт: событий={metrics['conflict_events']}, "
            f"переговоров={metrics['negotiation_rounds']}, "
            f"уступок={metrics['agreements']}, санкций={metrics['sanctions']}, "
            f"сообщений={metrics['conflict_messages']}, "
            f"ожидание станции ср/макс={metrics['station_wait_avg']}/{metrics['station_wait_max']}"
        )
        print(
            f"Экономика: выручка={metrics['revenue']}, "
            f"чаевые={metrics['tips']}, касса={metrics['treasury']}"
        )
        print(
            f"Нагрузка: {metrics['workload']}, "
            f"Gini={metrics['gini_workload']}, Jain={metrics['jain_workload']}"
        )
    return 0 if metrics["orders_open"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
