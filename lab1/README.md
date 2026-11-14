# Кухня Красти Крабс

## Структура проекта

```text
lab1/
├── README.md
├── docs/
│   ├── roles.dot
│   ├── roles.svg
│   ├── communication.dot
│   └── communication.svg
├── src/
│   ├── main.py          # CLI-запуск сценариев
│   ├── simulation.py    # сборка и цикл симуляции
│   ├── core/            # сообщения и шина
│   ├── domain/          # заказы, станции, инвентарь, среда
│   ├── agents/          # агенты и их поведение
│   ├── mechanisms/      # механизмы координации
│   ├── metrics/         # сбор метрик
│   ├── scenarios/       # сценарии
│   └── ui/              # веб-интерфейс и статические файлы
└── tests/               # unittest-тесты
```

## Запуск

Требуется Python 3.10+ (проверено на 3.14), внешних зависимостей нет.

```bash
cd lab1

python3 -m src.main --list
python3 -m src.main --scenario dinner_rush
python3 -m src.main --scenario sandy_check --json
python3 -m src.main --scenario smoke
```

Веб-интерфейс:

```bash
python3 -m src.ui.web --scenario dinner_rush
```

После запуска откройте <http://127.0.0.1:8000/>. Остановка — `Ctrl+C`.

Параметры веб-сервера:

```bash
python3 -m src.ui.web --host 0.0.0.0 --port 8080 --scenario sandy_check
python3 -m src.ui.web --scenario plankton_probe --autostart --interval 0.4
```

`--autostart` сразу запускает симуляцию, `--interval` задаёт секунды между тиками.

Доступные сценарии:

| Имя | Описание |
|---|---|
| `dinner_rush` | семь заказов, конкуренция за гриль и фритюр, два повара |
| `sandy_check` | поломка `fryer-1` и ремонт силами Sandy |
| `plankton_probe` | запрос Plankton и отказ Krabs |
| `smoke` | быстрая проверка работоспособности |

## Проверка

```bash
python3 -m unittest discover -s tests -t . -v
python3 -m compileall -q src tests
```
