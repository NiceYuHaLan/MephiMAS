# Лабораторная работа №2 — Исследование механизмов распределения задач и координации

Многоагентная кухня «Красти Крабс» с тремя взаимозаменяемыми механизмами
распределения заказов и инструментами экспериментального сравнения.

## Что нового относительно lab1

- Слой механизмов распределения (`src/mechanisms/`) с общим интерфейсом.
- Три механизма: **central**, **contract_net**, **auction**.
- Метрики координации: `coordination_messages`, `coordination_cost`,
  `assignment_latency_*`, `coordination_spend`, `throughput`.
- Режим сравнения `--compare` с экспортом CSV/JSON в `results/`.
- Стресс-сценарий `stress_rush` (12 заказов).
- Web-UI с переключателем механизма.

## Структура

```text
lab2/
├── README.md
├── REPORT.pdf           # отчёт в PDF
├── results/             # compare.csv / compare.json
├── docs/                # диаграмма механизмов (dot + svg)
├── src/
│   ├── main.py          # CLI: симуляция и --compare
│   ├── experiments.py   # матрица сценарии × механизмы, экспорт
│   ├── simulation.py    # сборка сцены с выбором механизма
│   ├── core/            # сообщения, шина, трасса
│   ├── domain/          # заказы, станции, среда
│   ├── agents/          # агенты (понимают все три протокола)
│   ├── mechanisms/      # base / central / contract_net / auction
│   ├── metrics/         # метрики, включая координационные
│   ├── scenarios/       # сценарии, включая stress_rush
│   └── ui/              # web-интерфейс
└── tests/               # unittest, включая test_mechanisms.py
```

## Механизмы

| Имя | Протокол | Правило выбора |
|---|---|---|
| `central` | `REQUEST → AGREE/REFUSE` | фиксированный приоритет поваров |
| `contract_net` | `CFP → PROPOSE → ACCEPT/REFUSE` | максимум score = мастерство − загрузка |
| `auction` | `CFP → PROPOSE → ACCEPT/REFUSE` | минимум цены = 1 + загрузка, платёж по второй цене (Викри) |

Выделение станций во всех режимах централизовано (Krabs) — переменной
эксперимента является именно распределение задач (заказов).

## Запуск

Требуется Python 3.10+ (проверено на 3.14), внешних зависимостей нет.

```bash
cd lab2

# список сценариев и механизмов
python3 -m src.main --list

# одна симуляция
python3 -m src.main --scenario dinner_rush --mechanism central
python3 -m src.main --scenario stress_rush --mechanism contract_net --quiet
python3 -m src.main --scenario smoke --mechanism auction --json

# сравнение механизмов (результаты в results/)
python3 -m src.main --compare
python3 -m src.main --compare \
  --scenarios dinner_rush,stress_rush \
  --mechanisms central,contract_net,auction \
  --out results
```

Веб-интерфейс:

```bash
python3 -m src.ui.web --scenario dinner_rush --mechanism contract_net
# затем http://127.0.0.1:8000/ — селектор «Механизм» переключает режим
```

## Сценарии

| Имя | Описание |
|---|---|
| `smoke` | быстрая проверка, 2 заказа |
| `dinner_rush` | 7 заказов, конкуренция за станции |
| `sandy_check` | поломка и ремонт фритюра |
| `plankton_probe` | внешний запрос, отказ Krabs |
| `stress_rush` | 12 заказов при двух поварах |

## Проверка

```bash
python3 -m unittest discover -s tests -t . -v
python3 -m compileall -q src tests
```

## Отчёт

`REPORT.pdf` — итоговый отчёт по лабораторной работе.

Для диаграммы протоколов при необходимости пересоберите SVG:

```bash
dot -Tsvg docs/mechanisms.dot -o docs/mechanisms.svg
```
