"""Эксперименты: сравнение механизмов распределения на наборе сценариев."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .security import ATTACK_SCENARIOS, list_attacks
from .simulation import Simulation

SECURITY_COLUMNS = [
    "attack",
    "defense",
    "attacks_injected",
    "attacks_blocked",
    "auth_failures",
    "integrity_failures",
    "replay_blocked",
    "authorization_denied",
    "provenance_denied",
    "consistency_denied",
    "cycle_blocked",
    "audit_failures",
    "lease_expiries",
    "fallback_repairs",
    "reassignments",
    "phantom_served",
    "double_serve",
    "double_assignment",
    "cycle_events",
    "lost_orders",
    "failures_total",
    "integrity_score",
    "false_positives",
]

COLUMNS = [
    "scenario",
    "mechanism",
    "conflict",
    "orders_total",
    "orders_served",
    "orders_cancelled",
    "orders_open",
    "makespan",
    "avg_wait",
    "max_wait",
    "late_orders",
    "assignment_latency_avg",
    "assignment_latency_max",
    "messages_total",
    "coordination_messages",
    "coordination_cost",
    "coordination_spend",
    "conflict_messages",
    "conflict_events",
    "contention_ticks",
    "negotiation_rounds",
    "agreements",
    "yields",
    "sanctions",
    "station_wait_avg",
    "station_wait_max",
    "reputation_mean",
    "throughput",
    "gini_workload",
    "jain_workload",
    "tasks_completed",
    *SECURITY_COLUMNS,
]


def run_single(
    scenario: str,
    mechanism: str = "central",
    conflict: str = "fcfs",
    max_ticks: int | None = None,
    attack: str | None = None,
    defense: bool = False,
) -> dict:
    simulation = Simulation(
        scenario,
        mechanism=mechanism,
        conflict=conflict,
        attack=attack,
        defense=defense,
    )
    try:
        metrics = simulation.run(max_ticks=max_ticks)
    finally:
        simulation.close()
    row = {
        "scenario": scenario,
        "mechanism": mechanism,
        "conflict": conflict,
        "attack": attack or "",
        "defense": int(defense),
    }
    for key in COLUMNS:
        if key in metrics:
            row[key] = metrics[key]
    return row


def run_compare(
    scenarios: list[str],
    mechanisms: list[str],
    conflicts: list[str] | None = None,
    out_dir: str | Path = "results",
    max_ticks: int | None = None,
    verbose: bool = True,
) -> list[dict]:
    rows: list[dict] = []
    for scenario in scenarios:
        for mechanism in mechanisms:
            for conflict in conflicts or ["fcfs"]:
                row = run_single(scenario, mechanism, conflict, max_ticks=max_ticks)
                rows.append(row)
                if verbose:
                    print(
                        f"{row['scenario']:>14} | {row['mechanism']:>12} | {row['conflict']:>12} | "
                        f"подано {row['orders_served']:>2}/{row['orders_total'] if 'orders_total' in row else '?'} "
                        f"| makespan {row['makespan']:>3} | сообщ {row['messages_total']:>3} "
                        f"| конфл {row.get('conflict_events', 0):>2} "
                        f"| переговоры {row.get('negotiation_rounds', 0):>2} "
                        f"| уступки {row.get('agreements', 0):>1}/"
                        f"санкции {row.get('sanctions', 0):>1} "
                        f"| опозд {row['late_orders']:>2}"
                    )
    export(rows, out_dir)
    if verbose:
        print()
        print(render_table(rows))
        print(f"\nРезультаты сохранены в {out_dir}/compare.csv и {out_dir}/compare.json")
    return rows


def export(rows: list[dict], out_dir: str | Path) -> None:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    fields = [column for column in COLUMNS if any(column in row for row in rows)]
    with (target / "compare.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (target / "compare.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def render_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    headers = [
        "сценарий",
        "механизм",
        "конфликт",
        "подано",
        "makespan",
        "ждали ср",
        "опозд",
        "назн ср",
        "сообщ",
        "протокол",
        "конфл",
        "переговоры",
        "уступки",
        "санкции",
        "$/заказ",
        "платежи",
        "Gini",
    ]
    table_rows: list[list[str]] = []
    for row in rows:
        table_rows.append(
            [
                str(row.get("scenario", "")),
                str(row.get("mechanism", "")),
                str(row.get("conflict", "")),
                f"{row.get('orders_served', 0)}/{row.get('orders_total', '?')}",
                str(row.get("makespan", "")),
                str(row.get("avg_wait", "")),
                str(row.get("late_orders", "")),
                str(row.get("assignment_latency_avg", "")),
                str(row.get("messages_total", "")),
                str(row.get("coordination_messages", "")),
                str(row.get("conflict_events", "")),
                str(row.get("negotiation_rounds", "")),
                str(row.get("agreements", "")),
                str(row.get("sanctions", "")),
                str(row.get("coordination_cost", "")),
                str(row.get("coordination_spend", "")),
                str(row.get("gini_workload", "")),
            ]
        )
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in table_rows))
        for index in range(len(headers))
    ]
    lines = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    for row in table_rows:
        lines.append(
            "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
        )
    return "\n".join(lines)


def run_attack_suite(
    attacks: list[str] | None = None,
    out_dir: str | Path = "results",
    verbose: bool = True,
) -> list[dict]:
    """Диверсионный анализ: каждая атака без защиты и с защитой."""
    names = attacks or [attack.name for attack in list_attacks()]
    rows: list[dict] = []
    for name in names:
        scenario = ATTACK_SCENARIOS.get(name, "dinner_rush")
        control = run_single(scenario, attack=None, defense=True)
        control["false_positives"] = int(control.get("attacks_blocked", 0))
        control["attack"] = "(контроль)"
        rows.append(control)
        for defense in (False, True):
            row = run_single(scenario, attack=name, defense=defense)
            row["false_positives"] = 0
            rows.append(row)
            if verbose:
                print(
                    f"{name:>22} | {scenario:>12} | защита {int(defense)} | "
                    f"подано {row.get('orders_served', 0)}/{row.get('orders_total', 0)} "
                    f"| отказы {row.get('failures_total', 0):>2} "
                    f"| блок {row.get('attacks_blocked', 0):>2} "
                    f"| конфл {row.get('cycle_events', 0):>2} "
                    f"| makespan {row.get('makespan', 0):>3}"
                )
    export_suite(rows, out_dir)
    if verbose:
        print()
        print(render_security_table(rows))
        print(f"\nРезультаты сохранены в {out_dir}/attacks.csv и {out_dir}/attacks.json")
    return rows


def export_suite(rows: list[dict], out_dir: str | Path) -> None:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    fields = [column for column in COLUMNS if any(column in row for row in rows)]
    with (target / "attacks.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (target / "attacks.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def render_security_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    headers = [
        "атака",
        "сценарий",
        "защ",
        "подано",
        "отказы",
        "фантом",
        "двойн.подача",
        "двойн.назн",
        "циклы",
        "потери",
        "блок",
        "впрыск",
        "makespan",
    ]
    table_rows: list[list[str]] = []
    for row in rows:
        table_rows.append(
            [
                str(row.get("attack", "")),
                str(row.get("scenario", "")),
                str(row.get("defense", "")),
                f"{row.get('orders_served', 0)}/{row.get('orders_total', '?')}",
                str(row.get("failures_total", 0)),
                str(row.get("phantom_served", 0)),
                str(row.get("double_serve", 0)),
                str(row.get("double_assignment", 0)),
                str(row.get("cycle_events", 0)),
                str(row.get("lost_orders", 0)),
                str(row.get("attacks_blocked", 0)),
                str(row.get("attacks_injected", 0)),
                str(row.get("makespan", "")),
            ]
        )
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in table_rows))
        for index in range(len(headers))
    ]
    lines = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    for row in table_rows:
        lines.append(
            "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
        )
    return "\n".join(lines)
