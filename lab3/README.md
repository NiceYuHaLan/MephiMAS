# Лабораторная работа №3 — Механизм переговоров и разрешения конфликтов

Многоагентная кухня «Красти Крабс»: дефицит станций, конкурирующие
заявки поваров и три режима их разрешения — очередь, арбитраж и
переговоры с уступками.

## Что нового относительно lab2

- Слой разрешения конфликтов (`src/conflict/`) с общим интерфейсом.
- Три режима: **fcfs** (очередь, до), **arbitration** (правила
  приоритезации), **negotiation** (переговоры, уступки, санкции).
- Протокол конфликта: `CFP station_conflict → PROPOSE claim_response
  → agreement / sanction / arbitration`.
- Репутация поваров и приоритетные кредиты, ограничение диапазона.
- Санкции за нечестные позиции в переговорах (жадный Patrick).
- Сценарии `station_rush` и `deadline_rush`: дефицитные станции и
  дедлайны с приоритетами.
- Метрики конфликта: `conflict_events`, `negotiation_rounds`,
  `agreements`, `yields`, `sanctions`, `station_wait_*`, `reputation*`.
- CLI `--conflict` / `--conflicts`, Web-UI с селектором режима.

## Структура

```text
lab3/
├── README.md
├── REPORT.pdf           # отчёт в PDF
├── results/             # compare.csv / compare.json
├── docs/                # диаграмма протокола конфликта (dot + svg)
├── src/
│   ├── main.py          # CLI: симуляция, --compare, --conflict
│   ├── experiments.py   # матрица сценарии × механизмы × конфликт
│   ├── simulation.py    # сборка сцены с выбором режима конфликта
│   ├── core/            # сообщения, шина, трасса
│   ├── domain/          # заказы, станции, среда (env.conflict)
│   ├── agents/          # агенты (включая ответы на CFP конфликта)
│   ├── mechanisms/      # base / central / contract_net / auction
│   ├── conflict/        # base / fcfs / arbitration / negotiation
│   ├── metrics/         # метрики, включая метрики конфликта
│   ├── scenarios/       # сценарии, включая station_rush
│   └── ui/              # web-интерфейс
└── tests/               # unittest, включая test_conflict.py
```

## Режимы разрешения конфликтов

| Имя | Протокол | Правило |
|---|---|---|
| `fcfs` | без обмена (как в lab2) | очередь по порядку подачи |
| `arbitration` | без обмена | максимум силы заявки (приоритет, срочность, репутация, кредит, загрузка) |
| `negotiation` | `CFP → PROPOSE → решение` | проигравший уступает (соглашение, кредит) или отказывается (санкция при избыточном запасе) → арбитраж по силе |

Сила заявки:

```text
score = 2·priority + 2/(1+max(0,slack)) + 0.5·reputation
        + 0.5·credit − 0.25·load
```

Пороги: `YIELD_SLACK=6`, `STARVE_LIMIT=12`, `CREDIT_CAP=2`,
репутация ограничена `[0, 2]`. Механизм распределения задач во всех
экспериментах фиксируется `central` — переменной является конфликт.

## Запуск

Требуется Python 3.10+ (проверено на 3.14), внешних зависимостей нет.

```bash
cd lab3

# список сценариев, механизмов и режимов конфликта
python3 -m src.main --list

# одна симуляция
python3 -m src.main --scenario station_rush --conflict negotiation
python3 -m src.main --scenario station_rush --conflict arbitration --quiet
python3 -m src.main --scenario smoke --conflict fcfs --json

# сравнение режимов (результаты в results/)
python3 -m src.main --compare --mechanisms central \
  --scenarios station_rush,dinner_rush,stress_rush \
  --conflicts fcfs,negotiation,arbitration --out results
```

Веб-интерфейс:

```bash
python3 -m src.ui.web --scenario station_rush --conflict negotiation
# затем http://127.0.0.1:8000/ — селектор «Конфликт» переключает режим
```

## Сценарии

| Имя | Описание |
|---|---|
| `smoke` | быстрая проверка, 2 заказа |
| `dinner_rush` | 7 заказов (сравнение с lab2) |
| `sandy_check` | поломка и ремонт фритюра |
| `plankton_probe` | внешний запрос, отказ Krabs |
| `stress_rush` | 12 заказов при двух поварах |
| `station_rush` | 5 пар одновременных заказов на одну станцию |
| `deadline_rush` | Дедлайны и приоритеты: две заявки на одну станцию |

## Результаты (scenario `deadline_rush`)

Для новой сценарии показано, что переговоры не дают преимущества:

```text
deadline_rush | central | fcfs        | makespan=19, late=2
deadline_rush | central | negotiation  | makespan=21, late=2
deadline_rush | central | arbitration | makespan=19, late=2
```

Переговоры увеличивают makespan на 2 такта по сравнению с `fcfs`/`arbitration`
без улучшения количества опозданий; это подтверждает вывод о невыгодности
добавления переговорного протокола в сценарий с избыточными дедлайнами.

Этот сценарий добавлен как дополнительная проверка после сборки итогового `REPORT.pdf`;
в `REPORT.pdf` он не входит, результаты воспроизводятся отдельными запусками
`--scenario deadline_rush --conflict ...`.

## Проверка

```bash
python3 -m unittest discover -s tests -t . -v
python3 -m compileall -q src tests
```

## Отчёт

`REPORT.pdf` — итоговый отчёт по лабораторной работе.

Для диаграммы протокола при необходимости пересоберите SVG:

```bash
dot -Tsvg docs/conflict.dot -o docs/conflict.svg
```
