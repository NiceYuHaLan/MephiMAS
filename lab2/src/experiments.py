"""Эксперименты: сравнение механизмов распределения на наборе сценариев."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .simulation import Simulation

COLUMNS = [
    "scenario",
    "mechanism",
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
    "throughput",
    "gini_workload",
    "jain_workload",
    "tasks_completed",
]


def run_single(scenario: str, mechanism: str, max_ticks: int | None = None) -> dict:
    simulation = Simulation(scenario, mechanism=mechanism)
    try:
        metrics = simulation.run(max_ticks=max_ticks)
    finally:
        simulation.close()
    row = {"scenario": scenario, "mechanism": mechanism}
    for key in COLUMNS:
        if key in metrics:
            row[key] = metrics[key]
    return row


def run_compare(
    scenarios: list[str],
    mechanisms: list[str],
    out_dir: str | Path = "results",
    max_ticks: int | None = None,
    verbose: bool = True,
) -> list[dict]:
    rows: list[dict] = []
    for scenario in scenarios:
        for mechanism in mechanisms:
            row = run_single(scenario, mechanism, max_ticks=max_ticks)
            rows.append(row)
            if verbose:
                print(
                    f"{row['scenario']:>14} | {row['mechanism']:>12} | "
                    f"подано {row['orders_served']:>2}/{row['orders_total'] if 'orders_total' in row else '?'} "
                    f"| makespan {row['makespan']:>3} | сообщ {row['messages_total']:>3} "
                    f"| протокол {row['coordination_messages']:>3} | $/заказ {row['coordination_cost']:>5} "
                    f"| назн {row['assignment_latency_avg']:>4}"
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
        "подано",
        "makespan",
        "ждали ср",
        "опозд",
        "назнач ср",
        "сообщ",
        "протокол",
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
                f"{row.get('orders_served', 0)}/{row.get('orders_total', '?')}",
                str(row.get("makespan", "")),
                str(row.get("avg_wait", "")),
                str(row.get("late_orders", "")),
                str(row.get("assignment_latency_avg", "")),
                str(row.get("messages_total", "")),
                str(row.get("coordination_messages", "")),
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
